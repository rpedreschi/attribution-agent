"""Continuous, live event generation for Acme Cloud.

Where `Generator` emits a fixed Q1 backfill in one shot, `LiveGenerator`
behaves like a real source system: on every tick it emits a trickle of *new*
events stamped at the current wall-clock time, so the DeltaStream materialized
views keep refreshing and the agent always sees fresh context.

Each journey is a compressed multi-touch path: an anonymous web touch becomes a
known contact (via a form fill), progresses through the funnel, and closes won
or lost - all within ``journey_seconds`` of wall-clock, so a closed_won and the
channel credit it earns are observable during a live demo instead of 60 days
later. Channel mix for last-touch is weighted by ``CHANNELS.attributed_deals``
so the live stream drifts toward the same shape as the backfill.

Live ids carry an ``L`` infix (``001ACL00001``) so they never collide with the
batch backfill's ids if both are pointed at the same topics.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from .. import sample_data as sd
from . import schemas
from .schemas import Event

_INDUSTRIES = ["Software", "Financial Services", "Healthcare", "Retail", "Manufacturing"]
_REGIONS = ["NA", "EMEA", "APAC", "LATAM"]
_DEVICES = ["desktop", "mobile", "tablet"]
_BAND_TO_SIZE = {"1-10M": "SMB", "10-50M": "MidMarket", "50M+": "Enterprise"}

# Same touch routing as the batch generator: which source system a channel's
# touch lands in.
_TOUCH_SOURCE = {
    "Paid Search": "ga4",
    "Paid Social": "ga4",
    "Organic/Web": "ga4",
    "Brand": "ga4",
    "AI Assistant": "ga4",
    "Events": "hubspot_form",
    "Email Nurture": "hubspot_email",
    "Outbound SDR": "outreach",
}

# Buyer-intent prompts we probe across the assistants for "share of model", each
# with its baseline rank and the competitor that tends to top the answer. The
# last one is the query that drops out mid-stream (see som_degrade_seconds).
_SOM_QUERIES: list[tuple[str, int, str]] = [
    ("best cloud cost optimization platform", 1, "CloudZero"),
    ("FinOps tools for enterprise",           2, "Apptio Cloudability"),
    ("how to reduce our AWS bill",            3, "Vantage"),
    ("Acme Cloud alternatives",               2, "Densify"),
    ("cloud cost anomaly detection",          2, "Kubecost"),     # drops out mid-stream
]
_SOM_DROP_QUERY = "cloud cost anomaly detection"
_SOM_ASSISTANTS = ["chatgpt", "perplexity", "gemini"]

_AD_CAMPAIGNS = {
    "Paid Social": ["ABM Tier 1 - Sponsored", "ABM Tier 2 - InMail", "Retargeting - Display"],
    "Paid Search": ["Brand Search - Acme", "Competitor Conquest",
                    "Solution Keywords - Cloud", "Generic Keywords - Broad"],
}

# Ad spend (Paid Search + Paid Social) as a fraction of attributed revenue, from
# sample_data. Live spend is emitted at this ratio of the revenue closing each
# tick — so blended ROI stays realistic and mv_spend_by_channel is continuously
# populated, instead of the old once-per-day batch a 'latest'-offset query misses.
SPEND_RATIO = (sd.channel_by_name("Paid Search").spend
               + sd.channel_by_name("Paid Social").spend) / sd.TOTAL_ATTRIBUTED_REVENUE


class _Journey:
    """An in-flight account with a queue of (scheduled_time, event) pairs."""

    __slots__ = ("account_id", "pending")

    def __init__(self, account_id: str, pending: list[tuple[datetime, Event]]) -> None:
        self.account_id = account_id
        self.pending = sorted(pending, key=lambda p: p[0])

    def due(self, now: datetime) -> list[Event]:
        out: list[Event] = []
        while self.pending and self.pending[0][0] <= now:
            out.append(self.pending.pop(0)[1])
        return out

    @property
    def done(self) -> bool:
        return not self.pending


class LiveGenerator:
    """Stateful generator driven one ``tick(now)`` at a time."""

    def __init__(self, *, seed: int = 42, journey_seconds: float = 180.0,
                 new_journey_rate: float = 0.15, ambient_per_tick: int = 2,
                 som_degrade_seconds: float = 120.0, max_journeys: int = 12,
                 max_concurrent: int = 0,
                 scenario: bool = False, slip_at: float | None = None) -> None:
        self.rng = random.Random(seed)
        self.journey_seconds = journey_seconds
        self.new_journey_rate = new_journey_rate
        self.ambient_per_tick = ambient_per_tick
        # After this many seconds of streaming, the designated buyer query drops
        # out of the LLM answers — the live "you slipped out of the answer" beat.
        # In scenario mode the slip is driven by a beat (timer or on-cue) instead.
        self.scenario = scenario
        self.slip_at = slip_at if slip_at is not None else (90.0 if scenario else som_degrade_seconds)
        self.som_degrade_seconds = self.slip_at
        # Two ways to keep the headline believable:
        #  * max_concurrent (preferred): cap how many journeys are IN FLIGHT at once
        #    (0 = off). New journeys keep spawning as old ones close, so revenue
        #    climbs gently and continuously for the whole call instead of plateauing
        #    — the closing RATE is bounded, not the lifetime total. Over a demo-length
        #    session the total stays sane; only an all-day run would balloon.
        #  * max_journeys: a hard lifetime cap on NEW journeys (0 = unlimited). Totals
        #    plateau once it's hit. Kept for back-compat / a fixed ceiling.
        # If both are set, max_concurrent governs spawning and max_journeys still
        # caps the lifetime total.
        self.max_journeys = max_journeys
        self.max_concurrent = max_concurrent
        self._spawned = 0
        self._seq = 0
        self._inflight: list[_Journey] = []
        self._channels = [c.name for c in sd.CHANNELS]
        self._weights = [c.attributed_deals for c in sd.CHANNELS]
        self._som_t0: datetime | None = None
        self._som_seq = 0
        # --- scenario / director state --------------------------------------
        # A wall-clock zero captured on the first tick, an ordered list of story
        # beats, a "slipped" latch the share-of-model slice reads, and a cue queue
        # the CLI drains to narrate each beat as it lands.
        self._t0: datetime | None = None
        self._slipped = False
        self.cues: list[str] = []
        self._beats = self._build_beats() if scenario else []
        self._beat_i = 0

    # -- scenario beats ------------------------------------------------------

    def _build_beats(self) -> list[dict]:
        """The demo story, as an ordered list of beats. Each fires when its `at`
        offset (seconds) is reached — or immediately when nudged by fire_next_beat
        (the on-cue path). `spawn` front-loads short won deals so revenue visibly
        ticks; `slip` latches the AI-answer drop; `cue` is the narration line."""
        beats = [
            {"name": "baseline", "at": 0.0, "spawn": 2, "spawn_seconds": 30.0,
             "cue": "Baseline is live — the full channel mix is loaded. Watch the tiles: "
                    "deals are closing on the stream right now, and every number "
                    "recomputes as each closed-won lands. Nothing here waits for a nightly job."},
            {"name": "revenue", "at": 35.0, "spawn": 0,
             "cue": "There — the sourced-pipeline tile and the money-by-channel bars just "
                    "moved. That's the stream recomputing attribution live, not a dashboard "
                    "someone refreshed last night."},
            {"name": "slip", "at": self.slip_at, "spawn": 0, "slip": True,
             "cue": "WATCH THIS — you just slipped out of the AI answer. \"cloud cost anomaly "
                    "detection\" dropped out of ChatGPT, Perplexity, and Gemini: mention rate "
                    "falling, rank gone. The DRIFT card is firing on the board. No ad platform "
                    "and no last-touch dashboard will ever show you this — your best-ROI "
                    "channel is leaking, and today you'd only find out next quarter when the "
                    "pipeline dried up."},
            {"name": "agent", "at": self.slip_at + 25.0, "spawn": 0,
             "cue": "And the agent already caught it — logged to the decision ledger, "
                    "share-of-model flagged as the leading indicator. Notice it does NOT "
                    "propose a budget move: you can't buy an LLM's recommendation. It acts "
                    "where it has a lever and watches where it doesn't. That restraint is the point."},
        ]
        # Fire in time order (the sequential runner and on-cue path both walk the
        # list in order); ascending `at` keeps timer and story order aligned.
        return sorted(beats, key=lambda b: b["at"])

    def _do_beat(self, beat: dict, now: datetime) -> None:
        for _ in range(beat.get("spawn", 0)):
            self._spawn_now(now, seconds=beat.get("spawn_seconds"), won=True)
        if beat.get("slip"):
            self._slipped = True
        self.cues.append(beat["cue"])

    def _run_beats(self, now: datetime, elapsed: float) -> None:
        while self._beat_i < len(self._beats) and self._beats[self._beat_i]["at"] <= elapsed:
            self._do_beat(self._beats[self._beat_i], now)
            self._beat_i += 1

    def fire_next_beat(self, now: datetime | None = None) -> bool:
        """Fire the next un-fired beat right now (the on-cue 'watch this' path).
        Returns False if the story is already exhausted."""
        if self._beat_i >= len(self._beats):
            return False
        self._do_beat(self._beats[self._beat_i], now or datetime.utcnow())
        self._beat_i += 1
        return True

    def _spawn_now(self, now: datetime, **kw) -> None:
        """Spawn a journey immediately if under the cap (used by beats)."""
        if self._under_cap():
            self._inflight.append(self._spawn(now, **kw))
            self._spawned += 1

    def _under_cap(self) -> bool:
        """Whether a new journey may spawn. max_concurrent bounds in-flight journeys
        (a gentle, continuous closing rate); max_journeys bounds the lifetime total
        (a hard plateau). Both apply when both are set."""
        if self.max_journeys > 0 and self._spawned >= self.max_journeys:
            return False
        if self.max_concurrent > 0 and len(self._inflight) >= self.max_concurrent:
            return False
        return True

    @property
    def inflight(self) -> int:
        return len(self._inflight)

    # -- per-channel touch (mirrors Generator._touch_events) -----------------

    def _touch(self, acct: dict, channel: str, when: datetime) -> list[Event]:
        kind = _TOUCH_SOURCE[channel]
        web_id = f"web-{acct['account_id']}"
        if kind == "ga4" and channel == "AI Assistant":
            src = self.rng.choice(["chatgpt", "perplexity", "gemini"])
            return [schemas.ga4_event(
                web_id, f"sess-{acct['account_id']}-{when:%j%H%M}", "page_view",
                "https://acme.cloud/solutions", self.rng.choice(_DEVICES),
                src, "ai-referral", "AI Assistant Campaign", when)]
        if kind == "ga4":
            utm = {"Paid Search": ("google", "cpc"), "Paid Social": ("linkedin", "paid-social"),
                   "Organic/Web": ("google", "organic"), "Brand": ("direct", "brand")}[channel]
            return [schemas.ga4_event(
                web_id, f"sess-{acct['account_id']}-{when:%j%H%M}", "page_view",
                "https://acme.cloud/solutions", self.rng.choice(_DEVICES),
                utm[0], utm[1], f"{channel} Campaign", when)]
        if kind == "hubspot_form":
            return [schemas.hubspot_form(
                acct["contact_id"], web_id, acct["email"], "Field Event Registration",
                f"{channel} Campaign", "event", when)]
        if kind == "hubspot_email":
            return [schemas.hubspot_email(
                acct["contact_id"], acct["email"],
                self.rng.choice(["email_open", "email_click"]), "Nurture - Product Trial", when)]
        if kind == "outreach":
            return [schemas.outreach_activity(
                f"prosp-{acct['account_id']}", acct["email"], acct["contact_id"],
                self.rng.choice(["dial", "conversation", "reply"]),
                "SDR Outbound - Enterprise", f"sdr{self.rng.randint(1, 8)}", when)]
        return []

    # -- spawning a new journey ----------------------------------------------

    def _spawn(self, now: datetime, *, seconds: float | None = None,
               primary: str | None = None, won: bool | None = None) -> _Journey:
        self._seq += 1
        n = self._seq
        aid, cid, oid = f"001ACL{n:05d}", f"003CTL{n:05d}", f"006OPL{n:05d}"
        web_id = f"web-{aid}"
        email = f"buyer@liveco{n}.com"
        name = f"LiveCo {n:04d}"
        band = self.rng.choice(["1-10M", "10-50M", "50M+"])
        size = _BAND_TO_SIZE[band]
        region = self.rng.choice(_REGIONS)
        industry = self.rng.choice(_INDUSTRIES)
        amount = self.rng.choice([45_000, 90_000, 140_000, 280_000])
        if primary is None:
            primary = self.rng.choices(self._channels, weights=self._weights, k=1)[0]
        support = self.rng.sample(
            [c for c in self._channels if c != primary], k=self.rng.randint(2, 4))
        journey = support + [primary]          # primary lands last (last touch)
        if won is None:
            won = self.rng.random() < 0.62
        span = seconds if seconds is not None else self.journey_seconds
        dur = timedelta(seconds=span * self.rng.uniform(0.7, 1.3))
        acct = {"account_id": aid, "contact_id": cid, "email": email}

        sched: list[tuple[datetime, Event]] = []

        def at(frac: float, ev: Event) -> None:
            sched.append((now + dur * frac, ev))

        # Identity spine: account + contact appear as a fresh lead.
        at(0.0, schemas.sf_account(aid, name, industry, self.rng.randint(50, 8000),
                                   band, region, is_customer=False, updated=now))
        at(0.0, schemas.sf_contact(cid, email, aid, "Lead", name.split()[0], now))
        # Anon -> known bridge: a form fill ties the web id to the contact.
        at(0.18, schemas.hubspot_form(cid, web_id, email, "Demo Request",
                                      f"{primary} Campaign", "web", now))
        # Multi-touch journey across channels (primary closest to close).
        njourney = len(journey)
        for i, channel in enumerate(journey):
            frac = 0.1 + 0.8 * (i / njourney) + self.rng.uniform(-0.03, 0.03)
            for ev in self._touch(acct, channel, now + dur * max(frac, 0.0)):
                at(max(frac, 0.0), ev)
        # Funnel stage transitions, tagged with the journey's source channel.
        at(0.30, schemas.hubspot_lifecycle(cid, email, "subscriber", "lead", now, primary))
        at(0.45, schemas.hubspot_lifecycle(cid, email, "lead", "mql", now, primary))
        at(0.60, schemas.sf_opportunity(oid, aid, "MQL", "SQL", amount, size, now, primary))
        at(0.78, schemas.sf_opportunity(oid, aid, "SQL", "Discovery", amount, size, now, primary))
        if won:
            at(1.0, schemas.sf_opportunity(oid, aid, "Negotiation", "ClosedWon",
                                           amount, size, now, primary))
            at(1.0, schemas.sf_account(aid, name, industry, self.rng.randint(50, 8000),
                                       band, region, is_customer=True, updated=now))
        else:
            at(1.0, schemas.sf_opportunity(oid, aid, "Discovery", "ClosedLost",
                                           amount, size, now, primary))

        # Stamp each scheduled event with its own wall-clock time so the payload
        # timestamp matches when it is actually published.
        return _Journey(aid, [(t, self._restamp(ev, t)) for t, ev in sched])

    @staticmethod
    def _restamp(ev: Event, when: datetime) -> Event:
        """Rewrite an event's timestamp field to ``when`` (set at spawn with a
        placeholder ``now``)."""
        topic_key, payload = ev
        ts = schemas._ts(when)
        payload = dict(payload)
        for field in ("event_time", "updated_at"):
            if field in payload:
                payload[field] = ts
        return (topic_key, payload)

    # -- ambient noise + spend -----------------------------------------------

    def _ambient(self, now: datetime) -> list[Event]:
        f = self.rng.choice(sd.FUNNEL)
        anon = f"anon-{f.program_category[:2]}-{self.rng.randint(0, 9_999_999)}"
        return [schemas.ga4_event(
            anon, f"sess-{anon}", "page_view", "https://acme.cloud/",
            self.rng.choice(_DEVICES), "google", "organic",
            f"{f.program_category} Campaign", now)]

    def _spend_slice(self, ad_spend: float, now: datetime) -> list[Event]:
        """One tick of ad spend, split across the two platforms (by their
        sample-data spend share) and a random campaign each, dated today."""
        events: list[Event] = []
        day = now.strftime("%Y-%m-%d")
        ps = sd.channel_by_name("Paid Search").spend
        psoc = sd.channel_by_name("Paid Social").spend
        total = ps + psoc
        for ch_name, builder, share in (
            ("Paid Search", schemas.google_spend, ps / total),
            ("Paid Social", schemas.linkedin_spend, psoc / total),
        ):
            spend = ad_spend * share
            campaign = self.rng.choice(_AD_CAMPAIGNS[ch_name])
            impr = int(spend * self.rng.uniform(20, 60))
            clicks = int(impr * self.rng.uniform(0.01, 0.04))
            events.append(builder(day, campaign, round(spend, 2), impr, clicks, now))
        return events

    def _cost_slice(self, won_rev: float, now: datetime) -> list[Event]:
        """Loaded cost for the non-ad channels (finance export -> channel_cost),
        proportional to revenue at each channel's sample spend ratio, so every
        channel — not just the two ad platforms — shows CAC/ROI in the demo."""
        events: list[Event] = []
        day = now.strftime("%Y-%m-%d")
        for ch in sd.CHANNELS:
            if ch.name in ("Paid Social", "Paid Search", "Events"):
                continue
            cost = max(won_rev * (ch.spend / sd.TOTAL_ATTRIBUTED_REVENUE), 50.0)
            events.append(schemas.channel_cost(day, ch.name, round(cost, 2), now))
        return events

    def _share_of_model_slice(self, now: datetime) -> list[Event]:
        """One probe per buyer query this tick (rotating which assistant we asked),
        recording the brand's standing in the answer. The designated drop query
        falls out of the answers after ``som_degrade_seconds`` — so a live
        ``aishare`` watch shows the slip happen, the way a model update would."""
        if self._som_t0 is None:
            self._som_t0 = now
        elapsed = (now - self._som_t0).total_seconds()
        assistant = _SOM_ASSISTANTS[self._som_seq % len(_SOM_ASSISTANTS)]
        self._som_seq += 1
        events: list[Event] = []
        for query, base_rank, competitor in _SOM_QUERIES:
            dropped = query == _SOM_DROP_QUERY and (self._slipped or elapsed >= self.som_degrade_seconds)
            if dropped:
                mentioned, cited, rank, sentiment = False, False, 99, "absent"
            else:
                mentioned = True
                rank = max(1, base_rank + self.rng.choice([-1, 0, 0, 1]))
                cited = self.rng.random() < (0.8 if rank <= 2 else 0.5)
                sentiment = "positive" if rank <= 2 else "neutral"
            events.append(schemas.share_of_model(
                now, query, assistant, mentioned, cited, rank, competitor, sentiment))
        return events

    # -- the tick ------------------------------------------------------------

    def tick(self, now: datetime | None = None) -> list[Event]:
        """Advance one step and return the events that fire at ``now``."""
        now = now or datetime.utcnow()
        events: list[Event] = []

        # Scenario mode: fire any story beats now due (they may spawn deals, latch
        # the AI-answer slip, and queue narration cues for the CLI to print).
        if self._t0 is None:
            self._t0 = now
        if self.scenario:
            self._run_beats(now, (now - self._t0).total_seconds())

        if self._under_cap() and self.rng.random() < self.new_journey_rate:
            self._inflight.append(self._spawn(now))
            self._spawned += 1

        still: list[_Journey] = []
        for j in self._inflight:
            events += j.due(now)
            if not j.done:
                still.append(j)
        self._inflight = still

        for _ in range(self.ambient_per_tick):
            events += self._ambient(now)

        # Continuous ad spend that tracks the revenue closing this tick (plus a
        # small floor so it always flows), instead of one batch per day — which a
        # 'latest'-offset stream query would miss, leaving mv_spend_by_channel empty.
        won_rev = sum(p.get("amount", 0) for k, p in events
                      if k == "salesforce_opportunities" and p.get("stage_to") == "ClosedWon")
        events += self._spend_slice(max(won_rev * SPEND_RATIO, 500.0), now)
        events += self._cost_slice(won_rev, now)
        events += self._share_of_model_slice(now)

        return events
