"""BoardPackData — the assembled, view-agnostic dataset for one weekly report.

`from_sample()` builds it from the canonical Acme Cloud figures (exact tie-out,
used for the demo artifact). `from_mcp()` builds the identical shape from the
live DeltaStream materialized views served over MCP. Everything downstream
(spreadsheet, observations, recommendations) consumes BoardPackData and never
touches the data source.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from statistics import mean

from .. import sample_data as sd
from .deltastream_mcp import DeltaStreamMCPClient, DeltaStreamMCPError


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
class ShareOfModelRow:
    """The brand's standing in LLM answers for one buyer query — the leading
    indicator for the (un-buyable) AI Assistant channel."""
    buyer_query: str
    probes: int
    mentions: int
    citations: int
    best_rank: int
    avg_rank: float

    @property
    def mention_rate(self) -> float:
        return self.mentions / self.probes if self.probes else 0.0

    @property
    def citation_rate(self) -> float:
        return self.citations / self.probes if self.probes else 0.0

    @property
    def status(self) -> str:
        """strong / slipping / at risk — drives the 'you dropped out' flag."""
        if self.mention_rate < 0.35 or self.avg_rank >= 6:
            return "at risk"
        if self.mention_rate < 0.7 or self.avg_rank >= 3.5:
            return "slipping"
        return "strong"


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
    # LLM answer-space visibility (leading indicator for the AI Assistant channel)
    share_of_model: list[ShareOfModelRow] = field(default_factory=list)
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
        share_of_model = [ShareOfModelRow(m.buyer_query, m.probes, m.mentions,
                                          m.citations, m.best_rank, m.avg_rank)
                          for m in sd.SHARE_OF_MODEL]
        return cls(
            customer_name=sd.CUSTOMER_NAME, fiscal_period=sd.FISCAL_PERIOD,
            channels=channels, funnel=funnel, cac_roi=cac_roi, campaigns=campaigns,
            total_attributed=sd.TOTAL_ATTRIBUTED_REVENUE,
            prior_attributed=sd.PRIOR_ATTRIBUTED_REVENUE,
            total_spend=sd.total_spend(), prior_spend=sd.PRIOR_TOTAL_SPEND,
            won_deals=sd.TOTAL_WON_DEALS, prior_won_deals=sd.PRIOR_WON_DEALS,
            share_of_model=share_of_model,
        )

    @classmethod
    def from_mcp(cls, client: DeltaStreamMCPClient, customer_name: str,
                 fiscal_period: str) -> "BoardPackData":
        """Build from the DeltaStream materialized views served over MCP.

        DeltaStream serves the live aggregated context (spend, funnel, per-account
        channel touch distribution, won revenue); the three attribution models are
        computed here from that context — see `_attribution_from_context`.
        """
        spend_rows = client.query_view("spend_by_channel")
        funnel_rows = client.query_view("funnel_by_category")
        dist_rows = client.query_view("channel_touch_distribution")
        won_rows = client.query_view("won_revenue_by_account")
        # share-of-model only populates once the live probe stream runs; tolerate
        # its absence (backfill-only deploys) rather than failing the whole pull.
        try:
            som_rows = client.query_view("share_of_model")
        except DeltaStreamMCPError:
            som_rows = []

        spend_by_channel = {r["channel"]: float(r.get("spend") or 0) for r in spend_rows}
        attr, deals = _attribution_from_context(dist_rows, won_rows)

        all_channels = sorted(set(spend_by_channel) | set(attr))
        channels = [ChannelAttribution(ch, attr.get(ch, _Z).last_touch,
                                       attr.get(ch, _Z).linear, attr.get(ch, _Z).time_decay)
                    for ch in all_channels]
        funnel = [FunnelRow(r["program_category"], int(r.get("touches") or 0),
                            int(r.get("conversations") or 0), int(r.get("mqls") or 0),
                            int(r.get("sqls") or 0), int(r.get("opps") or 0),
                            int(r.get("won") or 0)) for r in funnel_rows]
        cac_roi = [CacRoiRow(ch, spend_by_channel.get(ch, 0.0),
                             attr.get(ch, _Z).time_decay, deals.get(ch, 0))
                   for ch in all_channels]
        # No campaign-level MV in v1; the campaign sheet is populated only in
        # sample mode. Live mode leaves it empty rather than fabricate it.
        campaigns: list[CampaignRow] = []

        share_of_model = _share_of_model_from_rows(som_rows)

        total_attr = sum(c.time_decay for c in channels)
        total_spend = sum(spend_by_channel.values())
        won = len(won_rows) or sum(f.won for f in funnel)
        # Prior-period comparators would come from a windowed re-query in
        # production; the sample comparators stand in for the demo.
        return cls(
            customer_name=customer_name, fiscal_period=fiscal_period,
            channels=channels, funnel=funnel, cac_roi=cac_roi, campaigns=campaigns,
            total_attributed=total_attr, prior_attributed=sd.PRIOR_ATTRIBUTED_REVENUE,
            total_spend=total_spend, prior_spend=sd.PRIOR_TOTAL_SPEND,
            won_deals=won, prior_won_deals=sd.PRIOR_WON_DEALS,
            share_of_model=share_of_model,
        )


@dataclass
class _Attr:
    last_touch: float = 0.0
    linear: float = 0.0
    time_decay: float = 0.0


_Z = _Attr()  # zero sentinel for channels with no attribution


def _share_of_model_from_rows(rows: list[dict]) -> list[ShareOfModelRow]:
    """Map mv_share_of_model rows to ShareOfModelRow, ordered worst-standing
    first so the slipping/at-risk queries surface at the top of the watch."""
    out: list[ShareOfModelRow] = []
    for r in rows:
        probes = int(r.get("probes") or 0)
        mentions = int(r.get("mentions") or 0)
        avg_rank = float(r.get("avg_rank") or 0.0)
        out.append(ShareOfModelRow(
            buyer_query=str(r.get("buyer_query") or ""),
            probes=probes, mentions=mentions,
            citations=int(r.get("citations") or 0),
            best_rank=int(r.get("best_rank") or 99),
            avg_rank=avg_rank,
        ))
    out.sort(key=lambda s: (s.mention_rate, -s.avg_rank))
    return out


def _parse_ts(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        secs = value / 1000 if value > 1e12 else value
        return datetime.utcfromtimestamp(secs)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _attribution_from_context(
    dist_rows: list[dict], won_rows: list[dict],
    half_life_days: float = 7.0,
) -> tuple[dict[str, _Attr], dict[str, int]]:
    """Distribute each account's won revenue across channels under all three
    models, from the per-account channel touch distribution.

    last touch  = the channel with the most recent touch gets 100%
    linear      = revenue split by each channel's share of touch count
    time decay  = recency-weighted (per channel's latest touch vs close), halved
                  every `half_life_days`, normalized per account
    deals       = last-touch credit (new customers per channel, for CAC)
    """
    by_account: dict[str, list[dict]] = {}
    for r in dist_rows:
        by_account.setdefault(r["account_id"], []).append(r)

    attr: dict[str, _Attr] = {}
    deals: dict[str, int] = {}

    def bucket(ch: str) -> _Attr:
        return attr.setdefault(ch, _Attr())

    for won in won_rows:
        acct = won.get("account_id")
        revenue = float(won.get("revenue") or 0)
        rows = by_account.get(acct)
        if not rows or revenue <= 0:
            continue
        close = _parse_ts(won.get("close_time"))
        total_touch = sum(int(r.get("touch_count") or 0) for r in rows) or 1

        # last touch + deal credit
        last_row = max(rows, key=lambda r: _parse_ts(r.get("last_touch_time")) or datetime.min)
        last_ch = last_row["channel"]
        bucket(last_ch).last_touch += revenue
        deals[last_ch] = deals.get(last_ch, 0) + 1

        # linear
        for r in rows:
            bucket(r["channel"]).linear += revenue * int(r.get("touch_count") or 0) / total_touch

        # time decay
        weights: dict[str, float] = {}
        for r in rows:
            touch_t = _parse_ts(r.get("last_touch_time"))
            if close and touch_t:
                days = max((close - touch_t).total_seconds() / 86400, 0)
                weights[r["channel"]] = 2 ** (-days / half_life_days)
            else:
                weights[r["channel"]] = 1.0
        wsum = sum(weights.values()) or 1.0
        for ch, w in weights.items():
            bucket(ch).time_decay += revenue * w / wsum

    return attr, deals


def _pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 2:
        return 1.0
    ma, mb = mean(a), mean(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a) ** 0.5
    vb = sum((y - mb) ** 2 for y in b) ** 0.5
    return cov / (va * vb) if va and vb else 1.0
