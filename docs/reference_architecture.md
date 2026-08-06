# Reference Architecture

The DeltaStream Marketing Attribution Agent delivers real-time multi-touch
attribution and a budget-reallocation agent. First-party marketing events and an
**AI answer-engine visibility feed (Profound, or our own probe service)** land in
Kafka; DeltaStream resolves identity and maintains materialized views; and an
agent/dashboard reads those views **over MCP**, exporting the board pack to Excel.

The AI-visibility signal is where we **integrate rather than reinvent**: Profound
already probes ChatGPT / Perplexity / Gemini at scale for brand mention, citation,
and rank. We ingest that feed into the same stream and **join it to first-party
revenue** — the correlation ("you're slipping in the answer → here's the pipeline
at risk") is the differentiator, not the probing.

```
 First-party marketing data                    AI answer-engine visibility
 ─ Local datagen (six source APIs, JSON)        ─ Profound API   (or our own probe
   Salesforce · HubSpot · GA4 · LinkedIn           service): probes ChatGPT /
   Ads · Google Ads · Outreach                     Perplexity / Gemini for the
        │                                           buyer queries → mention /
        │                                           citation / rank / competitor
        │                                                │
        └───────────────────┬─────────────────────────────┘
                            ▼
             ┌──────────────────────────┐
             │     WarpStream (Kafka)     │   SASL_SSL
             └──────────────────────────┘
                            │   CREATE STREAM / CREATE CHANGELOG
                            ▼
 ┌────────────────────────────────────────────────────┐
 │                   DeltaStream (SQL)                  │
 │  • CREATE STREAM from each Kafka topic               │
 │  • Identity resolution via CHANGELOG joins           │
 │      anon web user_id → contact → account            │
 │  • Unified touchpoints / conversions / spend         │
 │  • CREATE MATERIALIZED VIEW (continuously updated)    │
 │      mv_spend_by_channel                              │
 │      mv_funnel_by_category                            │
 │      mv_channel_touch_distribution                    │
 │      mv_won_revenue_by_account                        │
 │      mv_share_of_model      ← Profound / probe stream │
 │      mv_*_timeline (per-minute)                       │
 │  • MVs auto-exposed over MCP to the token's role      │
 └────────────────────────────────────────────────────┘
                            │   DeltaStream MCP endpoint (Bearer token)
                            ▼
 ┌────────────────────────────────────────────────────┐
 │     Agent / dashboard (MCP client + Claude)          │
 │  • discovers + calls the MV tools                    │
 │  • 3 attribution models from the per-account touch   │
 │    distribution + won revenue                        │
 │  • joins share-of-model (Profound) to pipeline       │
 │  • recommendations (guardrailed, human-approved)     │
 └────────────────────────────────────────────────────┘
                            │
                            ▼
 Live board  +  Excel board pack (.xlsx, six sheets) — the CMO artifacts
```

## Why DeltaStream MVs over MCP

DeltaStream natively exposes any materialized view the API token's role can
`SELECT` as an **MCP tool** — no glue server to build. We removed ClickHouse from
the stack we manage (DeltaStream uses it internally to back MVs). The agent is a
plain MCP client: it discovers the MV tools, calls them, and reasons over live
state. This matches DeltaStream's positioning as a real-time context engine for
agents.

## AI-visibility: integrate Profound, don't reinvent it

Answer-engine visibility — brand mention, citation, and rank across ChatGPT,
Perplexity, and Gemini — is its own product category. **Profound** (and peers like
Peec and Athena) already run the probing at scale, with the sampling methodology
that makes it a valid population benchmark rather than one personalized session.
We do **not** rebuild that. Profound (or a comparable tracker, or a lightweight
in-house probe service) is a **data source**: its share-of-model signal is
published to Kafka and lands in `mv_share_of_model` next to the first-party
marketing streams.

The differentiator is the **join**. A standalone visibility tool reports a
mention rate and stops — it has no access to your CRM, identity graph, or revenue.
On the DeltaStream spine that same signal sits beside attributed pipeline, so a
drop in share-of-model can be correlated to the AI-referred pipeline at risk.
Visibility is an input; the revenue correlation is the product.

## Division of labor: streaming vs. agent

Full per-touch journey reconstruction with normalized window functions is
impractical in streaming SQL. So the split is deliberate:

- **DeltaStream** maintains the live aggregated *context*: spend per channel,
  the funnel counts, **per-account channel touch distribution** (touch count +
  most-recent touch time per channel), **won revenue per account**, and
  **share of model** — the brand's live standing in LLM answers (mention rate,
  citation rate, rank) for the buyer queries that matter, ingested from **Profound
  (or our own probe service)**. It is the leading indicator for the **AEO / LLM**
  channel: answer-engine-influenced deals you earn through content/PR rather than a
  dial-able media buy, so the agent tracks visibility and joins it to pipeline
  instead of reallocating it like ad spend.
- **The agent** does the final attribution arithmetic from that context
  (`reporting._attribution_from_context`):

  | Model       | Computed as                                              |
  |-------------|----------------------------------------------------------|
  | Last touch  | channel with the most recent touch gets 100%             |
  | Linear      | revenue split by each channel's share of touch count     |
  | Time decay  | recency-weighted (channel's latest touch vs close), 7-day half-life, normalized per account |

  All three distribute the same closed-won revenue. The **model-agreement
  coefficient** (avg. pairwise correlation of channel shares) shows the CMO how
  much the model choice changes the budget answer.

## Identity resolution

Anonymous GA4 traffic carries only a `user_id`. A HubSpot form submission
carries that web cookie (`web_user_id`) plus an email; joining the email to the
Salesforce contacts CDC changelog yields `web_user_id → contact_id → account_id`,
materialized as the `web_identity_map` changelog. GA4 touches temporal-join that
map to attach an account.

## Exposing the views

DeltaStream auto-exposes every materialized view an API token's role can
`SELECT` as an MCP tool — no extra DDL. The agent sends
`Authorization: Bearer <token>` to the MCP endpoint and discovers the MVs as
tools (`<database>_<schema>_<mv>`). To scope the agent down in a real
deployment, mint a least-privilege role that can SELECT only these four MVs and
bind the token to it; for the demo, any token that can read them works.

## Agent guardrails (v1)

- Agent recommends, human approves — no autonomous spend changes (the CLI
  `approve`/`reject` commands log every decision to `out/decisions.jsonl`).
- Reallocation capped at ±20% of current channel spend per week.
- Channels with fewer than `min_conversions_trailing_90d` (default 3) trailing
  won deals are excluded as too thin to act on.
- Brand and Events are excluded from agent autonomy entirely. **AEO / LLM** is
  excluded too — its spend is content/PR to *earn* placement, not a dial-able media
  buy, so the agent doesn't reallocate it like ad budget and watches **share of
  model** (the Profound feed) instead.
- Every recommendation is logged with rationale and source-data references.
