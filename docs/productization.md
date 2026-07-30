# Attribution Agent — demo → production

For the DeltaStream engineering team. This maps what the demo does today to what
a real product needs, and where the actual work is. The demo is deliberately
honest about its shortcuts; this is the list of them.

## The shape stays the same

The architecture is the pitch, and it survives productization:

```
sources → Kafka → DeltaStream (identity resolution + MVs) → MCP → agent → decisions
                         └────────── ClickHouse-backed rollups ──────────┘
```

**DeltaStream does the stateful heavy lifting** (identity stitching, continuous
aggregation); the **LLM only reasons over pre-aggregated context**. Keep that
separation — it's what makes this tractable. The agent should never see raw
events or do its own aggregation.

## What's real vs. faked today

| Area | Demo | Production needs |
|---|---|---|
| Ingestion | Synthetic generator → WarpStream | Real connectors (SF CDC, HubSpot, GA4, LinkedIn/Google Ads, Outreach); schema registry; dedup; DLQs |
| Identity resolution | One `web_identity_map` changelog, deterministic cookie→form→contact→account | A real identity graph (below) |
| Attribution | 3 heuristics computed in Python from the touch distribution | Push into DeltaStream/ClickHouse; add trained models; windowed lookback |
| Share of model | Simulated probe events | A real probe-ingestion service that queries the assistants |
| Prior-period / QoQ | Hardcoded constants (`sd.PRIOR_*`) | Real windowed MVs (trailing 90d, QoQ) |
| Recommendations | One-shot engine, ROI-vs-blended, guardrails in config | Backtested/uplift-based, validated, RBAC approval |
| Actuation | Proposes only; ledger is a JSONL file | Write-back to ad platforms with rollback; durable, immutable ledger |
| Serving | One process rebuilds `board.json` per poll (runs the LLM every 5s) | Decoupled read API + cached agent reasoning |
| Tenancy | Single org, one token | Multi-tenant isolation + row-level security |

## Where the real work is

### 1. Identity resolution (the hard, stateful part — and our differentiator)
The demo stitches one cookie → one form-fill → one contact → one account with a
temporal join. Reality is messy: many cookies per person, cross-device, multiple
contacts per account, email changes, B2B account matching, and cookieless /
consent-gated traffic. The nasty case is **retroactive stitching** — the form
fill that reveals identity often lands days after the anonymous touches, so you
need late-data handling / reprocessing so those earlier touches get their
account, not dropped. This is where most production effort goes, and it's exactly
what streaming SQL + a well-modeled identity graph should own.

### 2. Attribution: move the compute down, then make it real
- **Scale:** today `_attribution_from_context` pulls per-account touch rows to the
  agent and computes models in Python. That doesn't scale to millions of
  accounts — push the model computation into DeltaStream/ClickHouse (the
  aggregation belongs in the data plane).
- **Real models:** last-touch / linear / time-decay are heuristics. A "data-driven"
  model means Markov or Shapley trained on historical conversion paths; the UI
  labels ("W-shaped", "Data-driven") are aspirational today.
- **Incrementality:** the demo stubs holdout/geo tests as `illustrative: true`.
  Real lift measurement (holdouts, geo experiments) is a separate build and the
  honest basis for spend decisions.

### 3. Share of model: build the probe pipeline
The whole AI-visibility feed is simulated. Production is a scheduled service that
actually queries ChatGPT / Perplexity / Gemini for the buyer-query set, parses
each answer for **mention / citation / rank / cited-URL**, normalizes, and
publishes to Kafka — then the same MV pattern takes over. The hard parts: API
cost and rate limits, answer volatility across model updates, reliable structured
extraction from free-text answers, and capturing *which URL* was cited. Keep it
strictly separate from click attribution — it's a visibility signal, not revenue.

### 4. Windowing and "what changed"
Prior-period comparators are hardcoded and the timeline MVs are per-minute
(compressed for the demo). Production needs real windowed aggregations (trailing
90d, QoQ) and durable snapshotting for the deltas. This also resolves the
table-vs-trend mismatch we hit: make the standings a trailing-window rate so the
table and the trend's right edge agree by construction.

### 5. The agent: decouple, validate, actuate
- **Decouple reasoning from serving.** The board server reruns the recommendation
  engine (an LLM call) on every dashboard poll. Split it: an event-driven agent
  that recomputes on new data and caches decisions; a cheap read API for the UI.
- **Validate recommendations.** "ROI above/below blended" is a starting point;
  production wants backtesting, uplift/confidence, and guardrails as a real policy
  engine (per-channel budget rules, approval workflow, RBAC).
- **Actuation + audit.** Today it only proposes. Writing changes back to the ad
  platforms needs idempotency, reversibility, and an immutable ledger in a real
  store (not `out/decisions.jsonl`) for finance/compliance. Pin model versions so
  a recommendation is reproducible and explainable.

### 6. Multi-tenancy, serving, ops
Per-customer data isolation and row-level security on the MVs; token/audience
management at scale. Replace 5s polling with push (SSE/websockets). And treat the
demo's `validate()` invariants (all three models distribute the same total; spend
and deal counts reconcile) as **production data-quality monitors** — attribution
reconciliation is a real, checkable invariant.

## Suggested phasing

1. **Real feed + real identity.** Live connectors, production identity graph with
   retroactive stitching, attribution computed in DeltaStream/ClickHouse.
2. **Real signals.** Share-of-model probe service; windowed comparators; decouple
   the agent from serving; durable ledger.
3. **Close the loop.** Trained attribution + incrementality; write-back actuation
   with rollback; leveled autonomy; multi-tenancy.

## The honest one-liner for the team

*It's a working reference architecture for "LLM reasons over live streaming
context," not a product. The streaming/identity/aggregation spine is real and the
right shape; the data is synthetic, the attribution and share-of-model are
heuristic/simulated, and there's no actuation yet. Productizing is mostly (1) real
identity resolution at scale and (2) real signal feeds — the DeltaStream layer is
already doing the part that's genuinely hard.*
