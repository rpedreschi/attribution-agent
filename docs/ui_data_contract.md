# UI data contract — the live board view

The dashboard UI binds to **one JSON document** produced from the live pipeline,
so the front-end never queries DeltaStream directly. Generate it with:

```bash
# one-shot file (sample data, no infra):
python -m attribution_agent.api.board_view --source sample --out out/board.json

# live, served for local UI dev (rebuilds each request, permissive CORS):
python -m attribution_agent.api.board_view --source mcp --serve 8787
#   -> http://localhost:8787/board.json
```

`--source sample` runs on the canonical offline dataset; `--source mcp` reads the
live DeltaStream views. Both emit the identical shape, so build against `sample`
and flip to `mcp` for the real demo.

**Honesty markers.** Anything the pipeline can't measure truthfully today carries
`"illustrative": true` (or `*_illustrative`). The UI should badge those, not pass
them off as measured. Everything else is real pipeline output.

---

## Top-level shape

```jsonc
{
  "meta": { … },              // header chrome
  "live_board": { … },        // screen 1
  "model_compare": { … },     // screen 2
  "reallocation_agent": { … },// screen 3
  "decision_ledger": [ … ]    // screen 4
}
```

## meta (header)
| field | type | note |
|---|---|---|
| `customer` | string | e.g. "Acme Cloud" |
| `period_label` | string | e.g. "2026-Q1 to date" |
| `recomputed_at` | ISO datetime | drives "recomputed Ns ago" |
| `events_per_sec` | int | ⚠ `events_per_sec_illustrative:true` — not measured |
| `window` | string | `period_to_date` (the "Last 30 days" filter is not yet windowed — see gaps) |
| `sources_streaming` | int | source count |
| `environment` | string | "production" |

## live_board (screen 1)
- **`kpis[]`** — `{key,label,value,format,delta_pct,delta_label,subtext}`. Four keys:
  `sourced_pipeline`, `influenced` (subtext "held separate, never summed" — it is
  intentionally larger than sourced and never added to it), `blended_cac`
  (`subtext:"driven by <channel>"`), `cac_payback_months`. `format` ∈
  `currency|months`. `delta_pct` is null when there's no prior snapshot.
- **`what_changed[]`** — `{kind,title,body,real}`. `kind` ∈ `drift|new|low_confidence`.
  `real:true` cards are computed live (share-of-model slip, too-thin-to-attribute,
  the biggest channel mover vs your last look). Day-scale trend cards ("CPL +34%
  over 6 days") need windowed history — see gaps.
- **`money_by_channel[]`** — `{channel,revenue,share}`, sorted desc. The bar list.

## model_compare (screen 2)
- **`models`** / **`model_labels`** — the 3 models and their display names
  (`last_touch→"Last touch"`, `linear→"W-shaped"`, `time_decay→"Data-driven"`).
- **`credit_by_channel[]`** — `{channel, shares:{last_touch,linear,time_decay},
  spread_pts, status}`. `shares` are fractions summing to ~1.0 per model;
  `spread_pts` is the max−min disagreement in points; `status` ∈
  `agree|disagree|thin` (drives the "Spread 14 pts" / "Models agree" /
  "Not enough data" badges).
- **`credit_by_campaign[]`** — per-campaign spend/revenue/ROI (single figure; no
  3-model split at campaign grain yet).
- **`incrementality_tests`** — ⚠ `illustrative:true`, empty `tests[]`. Roadmap.

## reallocation_agent (screen 3)
- **`recommendations[]`** — `{id,title,action,channel,current_spend,delta,
  proposed_spend,expected_revenue_impact,confidence,rationale,basis[],
  reversible_days,status}`. `confidence` ∈ `high|low`; `basis[]` is the
  "Show the math" source references; `status:"pending"`.
- **`autonomy`** — `{level,max_level,weekly_cap,match_rate:{matched,of},note}`.
  `match_rate` is computed from the decision ledger (approvals / decisions).

## decision_ledger (screen 4)
Array of `{ts,event,actor,result}`, newest-relevant first. `actor` ∈
`AGENT|SYSTEM|HUMAN`. AGENT/SYSTEM rows mirror what the agent just observed
(drift detected, recommendation issued); HUMAN rows come from the durable
`out/decisions.jsonl` approval log.

---

## What's real vs. what needs backend work

**Real today (bind directly):** all KPIs (incl. sourced-vs-influenced), the money
bar, the 3-model credit split + spread/agree/thin, recommendations + confidence +
basis, autonomy + match-rate, the ledger, the share-of-model slip and
too-thin-to-attribute cards, and Export board pack (the existing xlsx).

**Needs new materialized views (time-series) — the main gap:** a real "Last 30
days" window filter and the day-scale "what changed" cards ("CPL +34% over 6
days", week-over-week first-touch). The current MVs are current-state snapshots;
these need windowed MVs. The `board_view` snapshot store (`out/board_snapshots.jsonl`)
already gives *session-level* deltas ("moved since your last look") as a bridge.

**Net-new features (design, not just a query):** keyword-level granularity,
incrementality/holdout tests, and the autonomy-level *promotion* flow.
