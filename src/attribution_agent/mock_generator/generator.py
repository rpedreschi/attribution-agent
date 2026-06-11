"""Deterministic event generation for Acme Cloud.

Produces a coherent, seeded stream of source events:

  * Salesforce accounts + contacts (the identity spine) and opportunity stage
    transitions (sql / opp_created / closed_won / closed_lost).
  * HubSpot form submissions (the anonymous->known bridge), lifecycle changes
    (conversation / mql), and email engagement.
  * GA4 anonymous web touches.
  * Outreach SDR activity.
  * LinkedIn / Google Ads daily spend.

Volumes are pinned to sample_data.FUNNEL and sample_data.CHANNELS so the events
roll up to the same 36 closed-won deals, 142 opportunities, and per-channel
spend that the board pack reports. Every closed-won account is given a real
multi-touch journey across channels ending before its close date, so the
DeltaStream materialized views have real journeys to credit.

NOTE: the published sample workbook reads canonical figures from `sample_data`
directly (exact tie-out); a live run through Kafka -> DeltaStream -> the agent
reproduces these aggregates closely but not to the penny, because attribution
credit depends on the randomized journey shapes generated here.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from .. import sample_data as sd
from . import schemas
from .schemas import Event

SEED = 42
PERIOD_START = datetime(2026, 1, 1)
PERIOD_END = datetime(2026, 3, 31)
PERIOD_DAYS = (PERIOD_END - PERIOD_START).days

_INDUSTRIES = ["Software", "Financial Services", "Healthcare", "Retail", "Manufacturing"]
_REGIONS = ["NA", "EMEA", "APAC", "LATAM"]
_DEVICES = ["desktop", "mobile", "tablet"]
_DEAL_BANDS = [("Enterprise", "50M+"), ("MidMarket", "10-50M"), ("SMB", "1-10M")]

# Channels that produce web/SDR/email *touch* events (i.e. land in
# marketing_touchpoints). Brand and Events influence journeys but, in v1, their
# touches are modeled as GA4/branded sessions and field-event form fills.
_TOUCH_SOURCE = {
    "Paid Search": "ga4",
    "Paid Social": "ga4",
    "Organic/Web": "ga4",
    "Brand": "ga4",
    "Events": "hubspot_form",
    "Email Nurture": "hubspot_email",
    "Outbound SDR": "outreach",
}


class Generator:
    def __init__(self, seed: int = SEED) -> None:
        self.rng = random.Random(seed)
        self._account_seq = 0
        self._contact_seq = 0
        self._opp_seq = 0

    # -- helpers -------------------------------------------------------------

    def _rand_dt(self, start: datetime, end: datetime) -> datetime:
        span = max(int((end - start).total_seconds()), 1)
        return start + timedelta(seconds=self.rng.randint(0, span))

    def _new_account_id(self) -> str:
        self._account_seq += 1
        return f"001AC{self._account_seq:05d}"

    def _new_contact_id(self) -> str:
        self._contact_seq += 1
        return f"003CT{self._contact_seq:05d}"

    def _new_opp_id(self) -> str:
        self._opp_seq += 1
        return f"006OP{self._opp_seq:05d}"

    def _deal_amounts(self) -> list[tuple[int, str, str]]:
        """36 (amount, deal_size, arr_band) tuples summing to TOTAL_ATTRIBUTED_REVENUE."""
        # Weight by band: a few Enterprise anchors, a midmarket body, SMB tail.
        plan = [_DEAL_BANDS[0]] * 6 + [_DEAL_BANDS[1]] * 18 + [_DEAL_BANDS[2]] * 12
        self.rng.shuffle(plan)
        weights = []
        for size, _ in plan:
            base = {"Enterprise": 280_000, "MidMarket": 110_000, "SMB": 45_000}[size]
            weights.append(base * self.rng.uniform(0.7, 1.4))
        scale = sd.TOTAL_ATTRIBUTED_REVENUE / sum(weights)
        amounts = [round(w * scale) for w in weights]
        amounts[-1] += sd.TOTAL_ATTRIBUTED_REVENUE - sum(amounts)  # fix rounding drift
        return [(amt, size, band) for amt, (size, band) in zip(amounts, plan)]

    # -- accounts ------------------------------------------------------------

    def emit_accounts_and_contacts(self, won_accounts: list[dict], other_count: int) -> list[Event]:
        events: list[Event] = []
        # Won customer accounts.
        for acct in won_accounts:
            events.append(schemas.sf_account(
                acct["account_id"], acct["name"], acct["industry"],
                acct["employees"], acct["arr_band"], acct["region"],
                is_customer=True, updated=acct["close_dt"]))
            events.append(schemas.sf_contact(
                acct["contact_id"], acct["email"], acct["account_id"],
                "Buyer", acct["name"].split()[0], acct["close_dt"] - timedelta(days=60)))
        # Non-customer accounts (open opps / leads).
        for i in range(other_count):
            aid = self._new_account_id()
            cid = self._new_contact_id()
            name = f"Prospect {i+1:03d} Inc"
            updated = self._rand_dt(PERIOD_START, PERIOD_END)
            events.append(schemas.sf_account(
                aid, name, self.rng.choice(_INDUSTRIES),
                self.rng.randint(50, 5000), self.rng.choice(["1-10M", "10-50M", "50M+"]),
                self.rng.choice(_REGIONS), is_customer=False, updated=updated))
            events.append(schemas.sf_contact(
                cid, f"buyer{i+1}@prospect{i+1}.com", aid, "Lead", name.split()[0],
                updated - timedelta(days=10)))
        return events

    def build_won_accounts(self) -> list[dict]:
        """Create the 36 won accounts, each tagged with the channel that gets
        last-touch credit, distributed per CHANNELS.attributed_deals."""
        deals = self._deal_amounts()
        # Channel assignment list per attributed_deals.
        channel_slots: list[str] = []
        for ch in sd.CHANNELS:
            channel_slots.extend([ch.name] * ch.attributed_deals)
        self.rng.shuffle(channel_slots)
        accounts = []
        for (amount, size, band), primary_channel in zip(deals, channel_slots):
            close_dt = self._rand_dt(PERIOD_START + timedelta(days=20), PERIOD_END)
            aid = self._new_account_id()
            cid = self._new_contact_id()
            slug = f"customer{len(accounts)+1}"
            accounts.append({
                "account_id": aid, "contact_id": cid,
                "name": f"Customer {len(accounts)+1:02d} Corp",
                "email": f"buyer@{slug}.com", "industry": self.rng.choice(_INDUSTRIES),
                "employees": self.rng.randint(200, 8000), "arr_band": band,
                "region": self.rng.choice(_REGIONS), "amount": amount,
                "deal_size": size, "primary_channel": primary_channel,
                "close_dt": close_dt,
            })
        return accounts

    # -- journeys + funnel ---------------------------------------------------

    def emit_won_journeys(self, won_accounts: list[dict]) -> list[Event]:
        """For each won account emit a multi-touch journey + the funnel-stage
        transitions culminating in closed_won."""
        events: list[Event] = []
        all_channels = [c.name for c in sd.CHANNELS]
        for acct in won_accounts:
            close = acct["close_dt"]
            # Journey: 2-5 supporting channels plus the primary (last touch).
            support = self.rng.sample(
                [c for c in all_channels if c != acct["primary_channel"]],
                k=self.rng.randint(2, 4))
            journey = support + [acct["primary_channel"]]
            start = close - timedelta(days=self.rng.randint(25, 80))
            n = len(journey)
            for i, channel in enumerate(journey):
                # Spread touches; primary lands last (closest to close).
                t = start + (close - start) * (i / n) + timedelta(hours=self.rng.randint(0, 12))
                events.extend(self._touch_events(acct, channel, t))
            # Funnel stage transitions for this account.
            events.extend(self._funnel_transitions(acct))
        return events

    def _touch_events(self, acct: dict, channel: str, when: datetime) -> list[Event]:
        kind = _TOUCH_SOURCE[channel]
        web_id = f"web-{acct['account_id']}"
        if kind == "ga4":
            utm = {"Paid Search": ("google", "cpc"), "Paid Social": ("linkedin", "paid-social"),
                   "Organic/Web": ("google", "organic"), "Brand": ("direct", "brand")}[channel]
            return [schemas.ga4_event(
                web_id, f"sess-{acct['account_id']}-{when:%j%H}", "page_view",
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
                "SDR Outbound - Enterprise", f"sdr{self.rng.randint(1,8)}", when)]
        return []

    def _funnel_transitions(self, acct: dict) -> list[Event]:
        close = acct["close_dt"]
        cid, email, aid = acct["contact_id"], acct["email"], acct["account_id"]
        opp_id = self._new_opp_id()
        t_conv = close - timedelta(days=self.rng.randint(45, 70))
        t_mql = close - timedelta(days=self.rng.randint(30, 44))
        t_sql = close - timedelta(days=self.rng.randint(18, 29))
        t_opp = close - timedelta(days=self.rng.randint(8, 17))
        return [
            schemas.hubspot_lifecycle(cid, email, "subscriber", "lead", t_conv),
            schemas.hubspot_lifecycle(cid, email, "lead", "mql", t_mql),
            schemas.sf_opportunity(opp_id, aid, "MQL", "SQL", acct["amount"], acct["deal_size"], t_sql),
            schemas.sf_opportunity(opp_id, aid, "SQL", "Discovery", acct["amount"], acct["deal_size"], t_opp),
            schemas.sf_opportunity(opp_id, aid, "Negotiation", "ClosedWon", acct["amount"], acct["deal_size"], close),
        ]

    def emit_open_opportunities(self, count: int) -> list[Event]:
        """Opportunities that reached opp_created but are still open or lost,
        bringing the opportunity count to TOTAL_OPPORTUNITIES."""
        events: list[Event] = []
        for _ in range(count):
            aid = self._new_account_id()
            opp_id = self._new_opp_id()
            amount = self.rng.choice([45_000, 90_000, 140_000, 280_000])
            size = self.rng.choice(["SMB", "MidMarket", "Enterprise"])
            t_opp = self._rand_dt(PERIOD_START, PERIOD_END - timedelta(days=5))
            stage_to = self.rng.choice(["Discovery", "ClosedLost"])
            events.append(schemas.sf_opportunity(
                opp_id, aid, "SQL", stage_to, amount, size, t_opp))
        return events

    def emit_ambient_touches(self) -> list[Event]:
        """Anonymous / non-converting touches to reach the per-channel touch
        totals in FUNNEL. These never resolve to an account."""
        events: list[Event] = []
        # Won journeys already emitted ~5 touches each; subtract a rough baseline.
        produced_baseline = sd.TOTAL_WON_DEALS * 4
        for f in sd.FUNNEL:
            remaining = max(f.touches - produced_baseline // len(sd.FUNNEL), 0)
            for i in range(remaining):
                when = self._rand_dt(PERIOD_START, PERIOD_END)
                anon = f"anon-{f.program_category[:2]}-{i}"
                events.append(schemas.ga4_event(
                    anon, f"sess-{anon}", "page_view", "https://acme.cloud/",
                    self.rng.choice(_DEVICES), "google", "organic",
                    f"{f.program_category} Campaign", when))
        return events

    def emit_spend(self) -> list[Event]:
        """Daily spend for the two ad platforms. Non-ad channel cost is loaded
        as its own Kafka topic by finance/manual export and is not emitted here."""
        events: list[Event] = []
        for ch_name, builder, campaigns in (
            ("Paid Social", schemas.linkedin_spend,
             ["ABM Tier 1 - Sponsored", "ABM Tier 2 - InMail", "Retargeting - Display"]),
            ("Paid Search", schemas.google_spend,
             ["Brand Search - Acme", "Competitor Conquest", "Solution Keywords - Cloud",
              "Generic Keywords - Broad"]),
        ):
            ch = sd.channel_by_name(ch_name)
            daily = ch.spend / (PERIOD_DAYS + 1)
            for d in range(PERIOD_DAYS + 1):
                day = (PERIOD_START + timedelta(days=d)).strftime("%Y-%m-%d")
                campaign = self.rng.choice(campaigns)
                spend = daily * self.rng.uniform(0.6, 1.4) / len(campaigns)
                impr = int(spend * self.rng.uniform(20, 60))
                clicks = int(impr * self.rng.uniform(0.01, 0.04))
                events.append(builder(day, campaign, spend, impr, clicks))
        return events

    # -- orchestration -------------------------------------------------------

    def generate(self) -> list[Event]:
        sd.validate()
        won = self.build_won_accounts()
        other_opps = sd.TOTAL_OPPORTUNITIES - sd.TOTAL_WON_DEALS
        events: list[Event] = []
        events += self.emit_accounts_and_contacts(won, other_count=other_opps + 200)
        events += self.emit_won_journeys(won)
        events += self.emit_open_opportunities(other_opps)
        events += self.emit_ambient_touches()
        events += self.emit_spend()
        return events
