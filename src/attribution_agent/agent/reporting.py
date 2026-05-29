"""BoardPackData — the assembled, view-agnostic dataset for one weekly report.

`from_sample()` builds it from the canonical Acme Cloud figures (exact tie-out,
used for the demo artifact). `from_clickhouse()` builds the identical shape from
the live attribution views. Everything downstream (spreadsheet, observations,
recommendations) consumes BoardPackData and never touches the data source.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean

from .. import sample_data as sd
from .clickhouse_client import ClickHouseClient


@dataclass
class ChannelAttribution:
    channel: str
    last_touch: float
    linear: float
    time_decay: float

    def share(self, total: float, model: str) -> float:
        val = {"last_touch": self.last_touch, "linear": self.linear,
               "time_decay": self.time_decay}[model]
        return val / total if total else 0.0


@dataclass
class FunnelRow:
    program_category: str
    touches: int
    conversations: int
    mqls: int
    sqls: int
    opps: int
    won: int

    @property
    def conversions_total(self) -> int:
        return self.mqls + self.sqls + self.opps + self.won

    def rates(self) -> dict[str, float]:
        def r(num: int, den: int) -> float:
            return num / den if den else 0.0
        return {
            "conv_per_touch": r(self.conversations, self.touches),
            "mql_per_conv": r(self.mqls, self.conversations),
            "sql_per_mql": r(self.sqls, self.mqls),
            "opp_per_sql": r(self.opps, self.sqls),
            "won_per_opp": r(self.won, self.opps),
        }


@dataclass
class CacRoiRow:
    program_category: str
    spend: float
    attributed_revenue: float
    attributed_deals: int

    @property
    def cac(self) -> float | None:
        return self.spend / self.attributed_deals if self.attributed_deals else None

    @property
    def roi(self) -> float | None:
        return self.attributed_revenue / self.spend if self.spend else None

    @property
    def payback_months(self) -> float | None:
        return 12 * self.spend / self.attributed_revenue if self.attributed_revenue else None


@dataclass
class CampaignRow:
    name: str
    channel: str
    spend: float
    attributed_revenue: float
    attributed_deals: int

    @property
    def roi(self) -> float | None:
        return self.attributed_revenue / self.spend if self.spend else None


@dataclass
class BoardPackData:
    customer_name: str
    fiscal_period: str
    channels: list[ChannelAttribution]
    funnel: list[FunnelRow]
    cac_roi: list[CacRoiRow]
    campaigns: list[CampaignRow]
    # period totals / comparators
    total_attributed: float
    prior_attributed: float
    total_spend: float
    prior_spend: float
    won_deals: int
    prior_won_deals: int
    # filled in by the agent layer
    observations: list[str] = field(default_factory=list)
    recommendations: list = field(default_factory=list)

    # ---- derived KPIs -----------------------------------------------------

    @property
    def blended_roi(self) -> float:
        return self.total_attributed / self.total_spend if self.total_spend else 0.0

    @property
    def blended_cac(self) -> float:
        return self.total_spend / self.won_deals if self.won_deals else 0.0

    @property
    def revenue_qoq(self) -> float:
        return (self.total_attributed - self.prior_attributed) / self.prior_attributed

    @property
    def model_agreement(self) -> float:
        """Average pairwise Pearson correlation of the three model share vectors.
        1.0 == the models rank channels identically; lower == they disagree, which
        is exactly where attribution-model choice changes the budget answer."""
        lt = [c.last_touch for c in self.channels]
        ln = [c.linear for c in self.channels]
        td = [c.time_decay for c in self.channels]
        pairs = [(lt, ln), (lt, td), (ln, td)]
        return mean(_pearson(a, b) for a, b in pairs)

    def channel_attr(self, channel: str) -> ChannelAttribution | None:
        return next((c for c in self.channels if c.channel == channel), None)

    def ranked_by_roi(self) -> list[CacRoiRow]:
        return sorted((r for r in self.cac_roi if r.roi is not None),
                      key=lambda r: r.roi, reverse=True)

    # ---- builders ---------------------------------------------------------

    @classmethod
    def from_sample(cls) -> "BoardPackData":
        sd.validate()
        channels = [ChannelAttribution(c.name, c.last_touch_revenue, c.linear_revenue,
                                       c.time_decay_revenue) for c in sd.CHANNELS]
        funnel = [FunnelRow(f.program_category, f.touches, f.conversations, f.mqls,
                            f.sqls, f.opps, f.won) for f in sd.FUNNEL]
        cac_roi = [CacRoiRow(c.program_category, c.spend, c.time_decay_revenue,
                             c.attributed_deals) for c in sd.CHANNELS]
        campaigns = [CampaignRow(c.name, c.channel, c.spend, c.attributed_revenue,
                                 c.attributed_deals) for c in sd.CAMPAIGNS]
        return cls(
            customer_name=sd.CUSTOMER_NAME, fiscal_period=sd.FISCAL_PERIOD,
            channels=channels, funnel=funnel, cac_roi=cac_roi, campaigns=campaigns,
            total_attributed=sd.TOTAL_ATTRIBUTED_REVENUE,
            prior_attributed=sd.PRIOR_ATTRIBUTED_REVENUE,
            total_spend=sd.total_spend(), prior_spend=sd.PRIOR_TOTAL_SPEND,
            won_deals=sd.TOTAL_WON_DEALS, prior_won_deals=sd.PRIOR_WON_DEALS,
        )

    @classmethod
    def from_clickhouse(cls, client: ClickHouseClient, customer_name: str,
                        fiscal_period: str) -> "BoardPackData":
        attr_rows = client.attribution_by_channel()
        channels = [ChannelAttribution(
            r["channel"], float(r["last_touch_revenue"]), float(r["linear_revenue"]),
            float(r["time_decay_revenue"])) for r in attr_rows]
        funnel = [FunnelRow(r["program_category"], int(r["touches"]), int(r["conversations"]),
                            int(r["mqls"]), int(r["sqls"]), int(r["opps"]), int(r["won"]))
                  for r in client.funnel_metrics()]
        cac_roi = [CacRoiRow(r["program_category"], float(r["spend"] or 0),
                             float(r["attributed_revenue"] or 0), int(r["attributed_deals"] or 0))
                   for r in client.cac_roi()]
        campaigns = [CampaignRow(r["campaign"], r["channel"], 0.0,
                                 float(r["attributed_revenue"]), 0)
                     for r in client.top_campaigns(20)]
        total_attr = sum(c.time_decay for c in channels)
        total_spend = sum(r.spend for r in cac_roi)
        won = sum(f.won for f in funnel)
        # Prior-period comparators would come from a second windowed query in
        # production; the sample comparators stand in for the demo.
        return cls(
            customer_name=customer_name, fiscal_period=fiscal_period,
            channels=channels, funnel=funnel, cac_roi=cac_roi, campaigns=campaigns,
            total_attributed=total_attr, prior_attributed=sd.PRIOR_ATTRIBUTED_REVENUE,
            total_spend=total_spend, prior_spend=sd.PRIOR_TOTAL_SPEND,
            won_deals=won, prior_won_deals=sd.PRIOR_WON_DEALS,
        )


def _pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 2:
        return 1.0
    ma, mb = mean(a), mean(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a) ** 0.5
    vb = sum((y - mb) ** 2 for y in b) ** 0.5
    return cov / (va * vb) if va and vb else 1.0
