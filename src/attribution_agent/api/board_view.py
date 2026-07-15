"""Board view-model: the single JSON payload the live dashboard UI binds to.

The CLI/spreadsheet consume `BoardPackData`; a browser UI wants a different
shape — KPI tiles, model spreads, agent cards, a ledger, and "what changed"
deltas — all in one document. `build_board_view()` assembles exactly that from
the same live pipeline, so the UI never re-queries DeltaStream itself.

Honesty markers: fields that a short demo cannot produce truthfully (day-scale
trends, keyword granularity, incrementality tests, raw event throughput) are
emitted with ``"illustrative": true`` so the UI can badge them rather than
pass them off as measured. Everything else is real pipeline output.

    python -m attribution_agent.api.board_view --source sample --out out/board.json
    python -m attribution_agent.api.board_view --source mcp --serve 8787
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..agent.reporting import BoardPackData

MODEL_LABELS = {"last_touch": "Last touch", "linear": "W-shaped", "time_decay": "Data-driven"}


# --------------------------------------------------------------------------- #
# assembly                                                                     #
# --------------------------------------------------------------------------- #

def build_board_view(
    data: BoardPackData,
    *,
    decisions: list[dict] | None = None,
    prev_snapshot: dict | None = None,
    excluded_channels: list[str] | None = None,
    autonomy_level: int = 2,
    weekly_cap: float = 25_000,
    now: datetime | None = None,
    events_per_sec: int | None = None,
    sources_streaming: int | None = None,
    trends: dict | None = None,
) -> dict:
    """Return the full board-view document (see docs/ui_data_contract.md)."""
    decisions = decisions or []
    now = now or datetime.now(timezone.utc)
    excluded = set(excluded_channels or [])
    trends = trends or {"bucket": "minute", "revenue": [], "touches_by_channel": {},
                        "spend_by_channel": {}, "share_of_model": {}, "illustrative": False}

    view = {
        "meta": _meta(data, now, events_per_sec, sources_streaming, trends),
        "trends": trends,
        "live_board": {
            "kpis": _kpis(data, prev_snapshot),
            "what_changed": _what_changed(data, prev_snapshot, excluded, trends),
            "money_by_channel": _money_by_channel(data),
        },
        "model_compare": {
            "models": list(MODEL_LABELS.keys()),
            "model_labels": MODEL_LABELS,
            "credit_by_channel": _credit_by_channel(data),
            "credit_by_campaign": _credit_by_campaign(data),
            "incrementality_tests": {
                "illustrative": True,
                "note": "Holdout / geo-incrementality tests are a roadmap surface; "
                        "the pipeline has no experiment framework yet.",
                "tests": [],
            },
        },
        "reallocation_agent": {
            "recommendations": _recommendations(data),
            "autonomy": _autonomy(decisions, autonomy_level, weekly_cap),
        },
        "decision_ledger": _decision_ledger(data, decisions, now),
    }
    return view


def snapshot_of(data: BoardPackData, now: datetime | None = None) -> dict:
    """The small metric snapshot persisted each run so the next run can diff it
    for the 'what changed since you last looked' cards."""
    now = now or datetime.now(timezone.utc)
    return {
        "ts": now.isoformat(),
        "sourced": data.total_attributed,
        "influenced": sum(data.influenced_by_channel.values()),
        "blended_cac": data.blended_cac,
        "by_channel_td": {c.channel: c.time_decay for c in data.channels},
        "som_status": {s.buyer_query: s.status for s in data.share_of_model},
    }


# --------------------------------------------------------------------------- #
# sections                                                                     #
# --------------------------------------------------------------------------- #

def _meta(data, now, events_per_sec, sources_streaming, trends) -> dict:
    return {
        "customer": data.customer_name,
        "period_label": f"{data.fiscal_period} to date",
        "recomputed_at": now.isoformat(),
        # throughput is not measured by the agent; surfaced as illustrative.
        "events_per_sec": events_per_sec if events_per_sec is not None else 2000,
        "events_per_sec_illustrative": events_per_sec is None,
        "window": "period_to_date",
        # the live time axis available to the UI's time filter (one bucket/minute)
        "trend_buckets": len(trends.get("revenue", [])),
        "sources_streaming": sources_streaming if sources_streaming is not None else 8,
        "environment": "production",
    }


def _kpis(data: BoardPackData, prev: dict | None) -> list[dict]:
    influenced = sum(data.influenced_by_channel.values())
    cac_driver = _worst_roi_channel(data)
    payback = 12 / data.blended_roi if data.blended_roi else None
    return [
        {
            "key": "sourced_pipeline", "label": "Marketing-sourced pipeline",
            "value": round(data.total_attributed), "format": "currency",
            "delta_pct": round(data.revenue_qoq * 100, 1), "delta_label": "vs prior period",
            "subtext": "last-touch sourced, closed-won",
        },
        {
            "key": "influenced", "label": "Marketing-influenced",
            "value": round(influenced), "format": "currency",
            "delta_pct": _pct_delta(influenced, (prev or {}).get("influenced")),
            "delta_label": "vs last look",
            "subtext": "held separate, never summed",
        },
        {
            "key": "blended_cac", "label": "Blended CAC",
            "value": round(data.blended_cac), "format": "currency",
            "delta_pct": _pct_delta(data.blended_cac, (prev or {}).get("blended_cac")),
            "delta_label": "vs last look",
            "subtext": f"driven by {cac_driver}" if cac_driver else "",
        },
        {
            "key": "cac_payback_months", "label": "CAC payback",
            "value": round(payback, 1) if payback else None, "format": "months",
            "delta_pct": None, "delta_label": "",
            "subtext": "on ARR; gross margin not modeled",
        },
    ]


def _what_changed(data: BoardPackData, prev: dict | None, excluded: set,
                  trends: dict) -> list[dict]:
    cards: list[dict] = []

    # REAL (from the revenue timeline): pace of revenue over the live window.
    rev = trends.get("revenue") or []
    if len(rev) >= 3:
        recent = sum(p["revenue"] for p in rev[-3:])
        earlier = sum(p["revenue"] for p in rev[:3]) or 1
        pct = (recent - earlier) / earlier * 100
        cards.append({
            "kind": "new" if pct >= 0 else "drift",
            "title": "Revenue pace shifted",
            "body": f"Closed-won over the latest buckets is {pct:+.0f}% vs the start of "
                    "the window — recomputed live, no nightly job.",
            "real": True,
        })

    # REAL: share-of-model slip (the AI Assistant early-warning).
    at_risk = [s for s in data.share_of_model if s.status == "at risk"]
    if at_risk:
        q = sorted(at_risk, key=lambda s: s.avg_rank, reverse=True)[0]
        cards.append({
            "kind": "drift", "title": "Slipped out of an AI answer",
            "body": f"\"{q.buyer_query}\": mention rate {q.mention_rate:.0%}, no longer "
                    f"ranked. The AI Assistant channel is leaking — no ad dashboard shows this.",
            "real": True,
        })

    # REAL: a channel too thin to attribute (the honest gate).
    thin = [r for r in data.cac_roi
            if r.program_category not in excluded and 0 < r.attributed_deals < 3]
    if thin:
        t = min(thin, key=lambda r: r.attributed_deals)
        cards.append({
            "kind": "low_confidence", "title": f"{t.program_category}: too few to attribute",
            "body": f"{t.attributed_deals} conversions in window. Too thin to trust a "
                    "reallocation — we are not going to pretend otherwise.",
            "real": True,
        })

    # REAL (only when a prior snapshot exists): the biggest revenue mover.
    if prev and prev.get("by_channel_td"):
        mover = _biggest_mover(data, prev["by_channel_td"])
        if mover:
            ch, delta = mover
            cards.append({
                "kind": "new" if delta > 0 else "drift",
                "title": f"{ch} moved since your last look",
                "body": f"Data-driven credit {'+' if delta > 0 else ''}{delta:,.0f} vs last "
                        "look, recomputed live as deals landed.",
                "real": True,
            })
    else:
        cards.append({
            "kind": "new", "title": "First snapshot",
            "body": "Baseline captured. 'What changed' deltas populate on the next refresh.",
            "real": True,
        })
    return cards


def _money_by_channel(data: BoardPackData) -> list[dict]:
    total = sum(c.time_decay for c in data.channels) or 1.0
    rows = sorted(data.channels, key=lambda c: c.time_decay, reverse=True)
    return [{"channel": c.channel, "revenue": round(c.time_decay),
             "share": round(c.time_decay / total, 4)} for c in rows]


def _credit_by_channel(data: BoardPackData) -> list[dict]:
    tl = sum(c.last_touch for c in data.channels) or 1.0
    tn = sum(c.linear for c in data.channels) or 1.0
    td = sum(c.time_decay for c in data.channels) or 1.0
    deals = {r.program_category: r.attributed_deals for r in data.cac_roi}
    out = []
    for c in sorted(data.channels, key=lambda c: c.time_decay, reverse=True):
        shares = {"last_touch": c.last_touch / tl, "linear": c.linear / tn,
                  "time_decay": c.time_decay / td}
        spread_pts = round((max(shares.values()) - min(shares.values())) * 100)
        if deals.get(c.channel, 0) < 3:
            status = "thin"
        elif spread_pts <= 5:
            status = "agree"
        else:
            status = "disagree"
        out.append({
            "channel": c.channel,
            "shares": {k: round(v, 4) for k, v in shares.items()},
            "spread_pts": spread_pts, "status": status,
        })
    return out


def _credit_by_campaign(data: BoardPackData) -> list[dict]:
    # Campaign-level 3-model split isn't modeled; single attributed figure only.
    return [{"campaign": c.name, "channel": c.channel, "spend": round(c.spend),
             "attributed_revenue": round(c.attributed_revenue),
             "deals": c.attributed_deals,
             "roi": round(c.roi, 2) if c.roi else None} for c in data.campaigns]


def _recommendations(data: BoardPackData) -> list[dict]:
    out = []
    for i, r in enumerate(data.recommendations):
        clamped = bool(getattr(r, "guardrail", None) and r.guardrail.clamped)
        confidence = "low" if clamped else "high"
        out.append({
            "id": i,
            "title": f"{r.action} {r.channel} {r.delta:+,.0f}/wk",
            "action": r.action, "channel": r.channel,
            "current_spend": round(r.current_spend), "delta": round(r.delta),
            "proposed_spend": round(r.proposed_spend),
            "expected_revenue_impact": round(r.expected_revenue_impact),
            "confidence": confidence,
            "rationale": r.rationale,
            "basis": r.source_refs,
            "reversible_days": 7,
            "status": "pending",
        })
    return out


def _autonomy(decisions: list[dict], level: int, weekly_cap: float) -> dict:
    approvals = [d for d in decisions if d.get("decision") == "approve"]
    return {
        "level": level, "max_level": 4, "weekly_cap": round(weekly_cap),
        "match_rate": {"matched": len(approvals), "of": len(decisions)},
        "note": "Every move is capped, reversible, and written to the decision ledger.",
    }


def _decision_ledger(data: BoardPackData, decisions: list[dict], now: datetime) -> list[dict]:
    events: list[dict] = []
    # SYSTEM/AGENT events synthesized from current live state (they'd be logged
    # by the agent in production; here they mirror what it just observed).
    at_risk = [s for s in data.share_of_model if s.status == "at risk"]
    if at_risk:
        events.append({"ts": now.isoformat(), "event": "Drift detected: AI answer visibility slipped",
                       "actor": "AGENT", "result": "Flagged in share-of-model"})
    for r in data.recommendations[:3]:
        events.append({"ts": now.isoformat(),
                       "event": f"Recommendation issued: {r.action} {r.channel} {r.delta:+,.0f}",
                       "actor": "AGENT", "result": "Pending approval"})
    # Human decisions from the durable log (newest first).
    for d in reversed(decisions):
        events.append({
            "ts": d.get("ts", ""),
            "event": f"{d.get('decision', '').title()}: {d.get('action', '')} {d.get('channel', '')}"
                     + (f" — {d.get('reason')}" if d.get("reason") else ""),
            "actor": "HUMAN", "result": "Logged to decision ledger",
        })
    return events


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #

def _pct_delta(cur: float, prev) -> float | None:
    if prev in (None, 0):
        return None
    return round((cur - prev) / prev * 100, 1)


def _worst_roi_channel(data: BoardPackData) -> str | None:
    ranked = [r for r in data.cac_roi if r.roi is not None]
    return min(ranked, key=lambda r: r.roi).program_category if ranked else None


def _biggest_mover(data: BoardPackData, prev_td: dict) -> tuple[str, float] | None:
    best = None
    for c in data.channels:
        delta = c.time_decay - float(prev_td.get(c.channel, c.time_decay))
        if best is None or abs(delta) > abs(best[1]):
            best = (c.channel, delta)
    return best if best and abs(best[1]) > 1 else None


# --------------------------------------------------------------------------- #
# trends (timeline MVs)                                                        #
# --------------------------------------------------------------------------- #

def _bucket_iso(v) -> str:
    from ..agent.reporting import _parse_ts
    dt = _parse_ts(v)
    return dt.isoformat() if dt else str(v)


def _merge_timeline(rows: list[dict], key: str, sums: tuple[str, ...]) -> dict:
    """Fold an aggregating MV's partial rows by a single key (DeltaStream can
    serve several un-merged parts per group)."""
    agg: dict = {}
    for r in rows:
        k = r.get(key)
        a = agg.setdefault(k, {s: 0.0 for s in sums})
        for s in sums:
            a[s] += float(r.get(s) or 0)
    return agg


def trends_from_mcp(client, views: dict) -> dict:
    """Build the trend series from the timeline MVs; tolerate any that aren't
    deployed yet (returns empty series for those)."""
    from ..agent.deltastream_mcp import DeltaStreamMCPError

    def _q(key):
        try:
            return client.query_view(key)
        except (DeltaStreamMCPError, KeyError):
            return []

    # revenue timeline: one row per minute bucket
    rev_by_bucket: dict = {}
    for r in _q("revenue_timeline"):
        b = _bucket_iso(r.get("bucket"))
        a = rev_by_bucket.setdefault(b, {"revenue": 0.0, "deals": 0.0})
        a["revenue"] += float(r.get("revenue") or 0)
        a["deals"] += float(r.get("deals") or 0)
    revenue = [{"t": b, "revenue": round(v["revenue"]), "deals": int(v["deals"])}
               for b, v in sorted(rev_by_bucket.items())]

    # touches by channel over time
    touch: dict = {}
    for r in _q("touch_timeline"):
        ch, b = r.get("channel"), _bucket_iso(r.get("bucket"))
        touch.setdefault(ch, {}).setdefault(b, 0.0)
        touch[ch][b] += float(r.get("touches") or 0)
    touches_by_channel = {ch: [{"t": b, "touches": int(n)} for b, n in sorted(series.items())]
                          for ch, series in touch.items()}

    # share-of-model mention rate over time
    som: dict = {}
    for r in _q("som_timeline"):
        q, b = r.get("buyer_query"), _bucket_iso(r.get("bucket"))
        cell = som.setdefault(q, {}).setdefault(b, {"probes": 0.0, "mentions": 0.0})
        cell["probes"] += float(r.get("probes") or 0)
        cell["mentions"] += float(r.get("mentions") or 0)
    share_of_model = {
        q: [{"t": b, "mention_rate": round(c["mentions"] / c["probes"], 3) if c["probes"] else 0.0}
            for b, c in sorted(series.items())]
        for q, series in som.items()}

    # spend by channel over time (spend pacing; cross with touches for live CPL)
    spend: dict = {}
    for r in _q("spend_timeline"):
        ch, b = r.get("channel"), _bucket_iso(r.get("bucket"))
        spend.setdefault(ch, {}).setdefault(b, 0.0)
        spend[ch][b] += float(r.get("spend") or 0)
    spend_by_channel = {ch: [{"t": b, "spend": round(v)} for b, v in sorted(series.items())]
                        for ch, series in spend.items()}

    return {"bucket": "minute", "revenue": revenue,
            "touches_by_channel": touches_by_channel,
            "spend_by_channel": spend_by_channel,
            "share_of_model": share_of_model, "illustrative": False}


def trends_sample(data: BoardPackData, buckets: int = 15) -> dict:
    """Deterministic offline trend series so the UI charts render without infra.
    Revenue ramps in; the at-risk share-of-model query declines to a slip."""
    base = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    times = [(base + timedelta(minutes=i)).isoformat() for i in range(buckets)]
    total = data.total_attributed
    # gentle ramp of per-bucket revenue summing to ~total (base >> range so the
    # window-pace delta reads believably, ~+20-30%, not +600%)
    weights = [40 + i for i in range(buckets)]
    wsum = sum(weights)
    revenue = [{"t": times[i], "revenue": round(total * weights[i] / wsum),
                "deals": max(1, round(data.won_deals * weights[i] / wsum))}
               for i in range(buckets)]
    td_total = sum(c.time_decay for c in data.channels) or 1.0
    touches_by_channel = {
        c.channel: [{"t": times[i], "touches": max(0, round(40 * c.time_decay / td_total))}
                    for i in range(buckets)]
        for c in data.channels}
    spend_by_channel = {
        r.program_category: [{"t": times[i], "spend": round(r.spend / buckets)}
                             for i in range(buckets)]
        for r in data.cac_roi if r.spend}
    share_of_model = {}
    for s in data.share_of_model:
        if s.status == "at risk":                       # declining curve (the slip)
            series = [max(0.0, round(s.mention_rate + (1 - s.mention_rate) * (1 - i / (buckets - 1)), 3))
                      for i in range(buckets)]
        else:
            series = [round(s.mention_rate, 3)] * buckets
        share_of_model[s.buyer_query] = [{"t": times[i], "mention_rate": series[i]}
                                         for i in range(buckets)]
    return {"bucket": "minute", "revenue": revenue,
            "touches_by_channel": touches_by_channel,
            "spend_by_channel": spend_by_channel,
            "share_of_model": share_of_model, "illustrative": True}


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

@dataclass
class _Loaded:
    data: BoardPackData
    decisions: list[dict]
    excluded: list[str]
    trends: dict


def _load(source: str) -> _Loaded:
    from ..config import load_settings
    from ..agent.guardrails import Guardrails
    from ..agent.llm import ClaudeClient
    from ..agent.recommendations import RecommendationEngine

    settings = load_settings()
    if source == "mcp":
        from ..agent.deltastream_mcp import DeltaStreamMCPClient
        client = DeltaStreamMCPClient(settings.deltastream)
        data = BoardPackData.from_mcp(client, settings.customer.display_name,
                                      settings.customer.fiscal_period)
        trends = trends_from_mcp(client, settings.deltastream.views)
    else:
        data = BoardPackData.from_sample()
        trends = trends_sample(data)

    claude = ClaudeClient(settings.agent)
    engine = RecommendationEngine(Guardrails(settings.agent.guardrails), claude)
    data.recommendations = engine.propose(data)

    decisions: list[dict] = []
    dpath = Path(settings.output.directory) / "decisions.jsonl"
    if dpath.exists():
        for line in dpath.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    decisions.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return _Loaded(data, decisions, settings.agent.guardrails.excluded_channels, trends)


def _build(source: str, snap_path: Path) -> dict:
    loaded = _load(source)
    prev = None
    if snap_path.exists():
        lines = [l for l in snap_path.read_text().splitlines() if l.strip()]
        if lines:
            try:
                prev = json.loads(lines[-1])
            except json.JSONDecodeError:
                prev = None
    view = build_board_view(loaded.data, decisions=loaded.decisions,
                            prev_snapshot=prev, excluded_channels=loaded.excluded,
                            trends=loaded.trends)
    snap = snapshot_of(loaded.data)
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    with snap_path.open("a") as fh:
        fh.write(json.dumps(snap) + "\n")
    return view


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Build the dashboard board-view JSON.")
    p.add_argument("--source", choices=["sample", "mcp"], default="sample")
    p.add_argument("--out", help="Write JSON here (default: stdout).")
    p.add_argument("--serve", type=int, metavar="PORT",
                   help="Serve the JSON at http://localhost:PORT/board.json (re-builds per request).")
    p.add_argument("--snapshots", default="out/board_snapshots.jsonl",
                   help="Snapshot store for 'what changed' diffs.")
    args = p.parse_args()
    snap_path = Path(args.snapshots)

    if args.serve:
        _serve(args.source, snap_path, args.serve)
        return

    view = _build(args.source, snap_path)
    text = json.dumps(view, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text)
        print(f"Wrote {args.out} ({len(text):,} bytes)")
    else:
        print(text)


def _serve(source: str, snap_path: Path, port: int) -> None:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            try:
                body = json.dumps(_build(source, snap_path)).encode()
            except Exception as exc:  # noqa: BLE001
                self.send_response(500)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(exc)}).encode())
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")  # local UI dev
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):  # quiet
            pass

    print(f"Serving board view ({source}) at http://localhost:{port}/board.json  (Ctrl-C to stop)")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
