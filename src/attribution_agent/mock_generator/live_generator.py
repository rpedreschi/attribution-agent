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
    "Events": "hubspot_form",
    "Email Nurture": "hubspot_email",
    "Outbound SDR": "outreach",
}

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
                 new_journey_rate: float = 0.15, ambient_per_tick: int = 2) -> None:
        self.rng = random.Random(seed)
        self.journey_seconds = journey_seconds
        self.new_journey_rate = new_journey_rate
        self.ambient_per_tick = ambient_per_tick
        self._seq = 0
        self._inflight: list[_Journey] = []
        self._channels = [c.name for c in sd.CHANNELS]
        self._weights = [c.attributed_deals for c in sd.CHANNELS]

    @property
    def inflight(self) -> int:
        return len(self._inflight)

    # -- per-channel touch (mirrors Generator._touch_events) -----------------

    def _touch(self, acct: dict, channel: str, when: datetime) -> list[Event]:
        kind = _TOUCH_SOURCE[channel]
        web_id = f"web-{acct['account_id']}"
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

    def _spawn(self, now: datetime) -> _Journey:
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
        primary = self.rng.choices(self._channels, weights=self._weights, k=1)[0]
        support = self.rng.sample(
            [c for c in self._channels if c != primary], k=self.rng.randint(2, 4))
        journey = support + [primary]          # primary lands last (last touch)
        won = self.rng.random() < 0.62
        dur = timedelta(seconds=self.journey_seconds * self.rng.uniform(0.7, 1.3))
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
        # Funnel stage transitions.
        at(0.30, schemas.hubspot_lifecycle(cid, email, "subscriber", "lead", now))
        at(0.45, schemas.hubspot_lifecycle(cid, email, "lead", "mql", now))
        at(0.60, schemas.sf_opportunity(oid, aid, "MQL", "SQL", amount, size, now))
        at(0.78, schemas.sf_opportunity(oid, aid, "SQL", "Discovery", amount, size, now))
        if won:
            at(1.0, schemas.sf_opportunity(oid, aid, "Negotiation", "ClosedWon",
                                           amount, size, now))
            at(1.0, schemas.sf_account(aid, name, industry, self.rng.randint(50, 8000),
                                       band, region, is_customer=True, updated=now))
        else:
            at(1.0, schemas.sf_opportunity(oid, aid, "Discovery", "ClosedLost",
                                           amount, size, now))

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
            events.append(builder(day, campaign, round(spend, 2), impr, clicks))
        return events

    # -- the tick ------------------------------------------------------------

    def tick(self, now: datetime | None = None) -> list[Event]:
        """Advance one step and return the events that fire at ``now``."""
        now = now or datetime.utcnow()
        events: list[Event] = []

        if self.rng.random() < self.new_journey_rate:
            self._inflight.append(self._spawn(now))

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

        return events
