"""Canonical Acme Cloud dataset — the single source of truth for the demo.

Every figure the demo reports derives from this module, so the six spreadsheet
sheets tie out by construction:

  * Attribution totals are identical across the three models ($4.28M), because
    each model only *redistributes* the same closed-won revenue across channels.
  * CAC = spend / attributed_deals;  ROI = attributed_revenue / spend;
    payback_months = 12 / ROI  (revenue is ARR).
  * Funnel counts roll up to the same 36 closed-won deals and 142 opportunities
    shown on the CAC/ROI and Executive Summary sheets.

`validate()` asserts these invariants and is exercised by the generators so a
mistaken edit fails loudly instead of shipping an inconsistent board pack.

Acme Cloud: Series C B2B SaaS, ~$180M revenue. Reporting period: 2026-Q1,
trailing-90-day window.
"""
from __future__ import annotations

from dataclasses import dataclass

CUSTOMER_ID = "acme_cloud"
CUSTOMER_NAME = "Acme Cloud"
FISCAL_PERIOD = "2026-Q1"
COMPANY_REVENUE = 180_000_000

# Total closed-won revenue attributed in the period. Identical across all three
# attribution models — they differ only in how they split it across channels.
TOTAL_ATTRIBUTED_REVENUE = 4_280_000
TOTAL_WON_DEALS = 36
TOTAL_OPPORTUNITIES = 142

# Prior-quarter comparators for the Executive Summary QoQ deltas.
PRIOR_ATTRIBUTED_REVENUE = 3_910_000
PRIOR_TOTAL_SPEND = 1_840_000
PRIOR_WON_DEALS = 31


@dataclass(frozen=True)
class Channel:
    name: str
    program_category: str
    spend: int                 # trailing-90d spend / loaded cost
    last_touch_revenue: int
    linear_revenue: int
    time_decay_revenue: int
    attributed_deals: int      # new customers credited (time-decay basis)
    source_system: str         # which of the six APIs produces this channel
    source_platform: str       # spend platform tag in campaign_spend
    agent_eligible: bool       # False => excluded from agent autonomy (Brand/Events)


# Channel economics. Spend sums to $1,900,000; each revenue column sums to
# $4,280,000; attributed_deals sums to 36.
CHANNELS: list[Channel] = [
    Channel("Paid Search",   "Paid Search",   420_000, 1_180_000, 760_000, 980_000, 9, "google_ads",  "google_ads", True),
    Channel("Paid Social",   "Paid Social",   560_000,   560_000, 940_000, 760_000, 7, "linkedin_ads","linkedin",   True),
    Channel("Outbound SDR",  "Outbound SDR",  300_000,   980_000, 640_000, 820_000, 7, "outreach",    "outreach",   True),
    Channel("Email Nurture", "Email Nurture",  50_000,   720_000, 540_000, 640_000, 6, "hubspot",     "hubspot",    True),
    Channel("Events",        "Events",        360_000,   470_000, 720_000, 560_000, 4, "salesforce",  "manual",     False),
    Channel("Organic/Web",   "Organic/Web",    30_000,   250_000, 300_000, 300_000, 2, "ga4",         "manual",     True),
    Channel("Brand",         "Brand",         180_000,   120_000, 380_000, 220_000, 1, "salesforce",  "manual",     False),
]


@dataclass(frozen=True)
class FunnelRow:
    program_category: str
    touches: int
    conversations: int
    mqls: int
    sqls: int
    opps: int
    won: int


# Funnel by program category. Columns roll up to the period totals above.
FUNNEL: list[FunnelRow] = [
    FunnelRow("Paid Search",   12_400, 1_650, 560, 190, 34, 9),
    FunnelRow("Paid Social",   15_800, 1_980, 620, 175, 28, 7),
    FunnelRow("Outbound SDR",   6_200, 1_420, 410, 150, 30, 7),
    FunnelRow("Email Nurture",  7_600,   980, 380, 120, 22, 6),
    FunnelRow("Events",         3_100,   290, 140,  55, 16, 4),
    FunnelRow("Organic/Web",    2_400,    78,  52,  22,  9, 2),
    FunnelRow("Brand",            700,    22,  18,   8,  3, 1),
]

# Top campaigns by attributed revenue (time-decay), for the Campaign sheet.
@dataclass(frozen=True)
class Campaign:
    name: str
    channel: str
    spend: int
    attributed_revenue: int
    attributed_deals: int


CAMPAIGNS: list[Campaign] = [
    Campaign("Brand Search - Acme",        "Paid Search",   95_000, 410_000, 4),
    Campaign("Competitor Conquest",        "Paid Search",  130_000, 320_000, 3),
    Campaign("ABM Tier 1 - Sponsored",     "Paid Social",  210_000, 300_000, 3),
    Campaign("SDR Outbound - Enterprise",  "Outbound SDR", 140_000, 380_000, 3),
    Campaign("Nurture - Product Trial",    "Email Nurture", 18_000, 290_000, 3),
    Campaign("Solution Keywords - Cloud",  "Paid Search",  120_000, 250_000, 2),
    Campaign("ABM Tier 2 - InMail",        "Paid Social",  150_000, 240_000, 2),
    Campaign("SDR Outbound - MidMarket",   "Outbound SDR", 100_000, 240_000, 2),
    Campaign("Field Event - SaaStr",       "Events",       180_000, 250_000, 2),
    Campaign("Webinar Series - Q1",        "Events",        90_000, 180_000, 1),
    Campaign("Nurture - Re-engagement",    "Email Nurture", 14_000, 190_000, 2),
    Campaign("Retargeting - Display",      "Paid Social",   85_000, 130_000, 1),
    Campaign("Organic - Content Hub",      "Organic/Web",   18_000, 170_000, 1),
    Campaign("Generic Keywords - Broad",   "Paid Search",   75_000,  85_000, 0),
    Campaign("Brand Awareness - Video",    "Brand",        110_000, 130_000, 1),
    Campaign("Organic - Comparison Pages", "Organic/Web",   12_000, 130_000, 1),
    Campaign("Executive Roundtable",       "Events",        90_000, 130_000, 1),
    Campaign("Brand - Podcast Sponsor",    "Brand",         70_000,  90_000, 0),
    Campaign("SDR Outbound - SMB",         "Outbound SDR",  60_000, 200_000, 2),
    Campaign("Nurture - Onboarding",       "Email Nurture", 18_000, 160_000, 1),
]


def total_spend() -> int:
    return sum(c.spend for c in CHANNELS)


def channel_by_name(name: str) -> Channel:
    return next(c for c in CHANNELS if c.name == name)


def revenue_for_model(model: str) -> dict[str, int]:
    """Map channel -> attributed revenue for 'last_touch'|'linear'|'time_decay'."""
    field = {
        "last_touch": "last_touch_revenue",
        "linear": "linear_revenue",
        "time_decay": "time_decay_revenue",
    }[model]
    return {c.name: getattr(c, field) for c in CHANNELS}


def validate() -> None:
    """Assert the internal-consistency invariants; raise AssertionError if broken."""
    for model in ("last_touch", "linear", "time_decay"):
        total = sum(revenue_for_model(model).values())
        assert total == TOTAL_ATTRIBUTED_REVENUE, (
            f"{model} attribution sums to {total:,}, expected {TOTAL_ATTRIBUTED_REVENUE:,}"
        )

    assert sum(c.attributed_deals for c in CHANNELS) == TOTAL_WON_DEALS
    assert total_spend() == 1_900_000

    assert sum(f.won for f in FUNNEL) == TOTAL_WON_DEALS
    assert sum(f.opps for f in FUNNEL) == TOTAL_OPPORTUNITIES

    # Funnel must be monotonically non-increasing down each row.
    for f in FUNNEL:
        stages = [f.touches, f.conversations, f.mqls, f.sqls, f.opps, f.won]
        assert stages == sorted(stages, reverse=True), f"non-monotone funnel: {f.program_category}"

    # Every channel has a funnel row and vice versa.
    assert {c.program_category for c in CHANNELS} == {f.program_category for f in FUNNEL}


if __name__ == "__main__":
    validate()
    print(f"sample_data OK: {len(CHANNELS)} channels, "
          f"${TOTAL_ATTRIBUTED_REVENUE:,} attributed, {TOTAL_WON_DEALS} deals, "
          f"${total_spend():,} spend.")
