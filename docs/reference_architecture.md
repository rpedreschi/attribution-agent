# Reference Architecture

The DeltaStream Marketing Attribution Agent delivers real-time multi-touch
attribution and a budget-reallocation agent. You run datagen locally, it feeds
Confluent Cloud, DeltaStream resolves identity and maintains materialized views,
and an interactive agent reads those views **over MCP** and exports the board
pack to Excel.

```
 Local datagen (six source APIs, JSON)
   Salesforce · HubSpot · GA4 · LinkedIn Ads · Google Ads · Outreach
        │   producer -> per-source topics
        ▼
 ┌──────────────────────────┐
 │   Confluent Cloud (Kafka) │   SASL_SSL / PLAIN
 └──────────────────────────┘
        │   CREATE STREAM / CREATE CHANGELOG
        ▼
 ┌────────────────────────────────────────────────┐
 │                 DeltaStream (SQL)                │
 │  • CREATE STREAM from each Kafka topic           │
 │  • Identity resolution via CHANGELOG joins       │
 │      anon web user_id → contact → account        │
 │  • Unified touchpoints / conversions / spend     │
 │  • CREATE MATERIALIZED VIEW (continuously updated)│
 │      mv_spend_by_channel                          │
 │      mv_funnel_by_category                        │
 │      mv_channel_touch_distribution                │
 │      mv_won_revenue_by_account                    │
 │      mv_share_of_model  (LLM answer-space)        │
 │  • MVs auto-exposed over MCP to the token's role  │
 └────────────────────────────────────────────────┘
        │   DeltaStream MCP endpoint (Bearer token)
        │   every granted MV is auto-exposed as an MCP tool
        ▼
 ┌────────────────────────────────────────────────┐
 │     Interactive Agent (MCP client + Claude)      │
 │  • discovers + calls the MV tools                │
 │  • computes the 3 attribution models from the    │
 │    per-account touch distribution + won revenue  │
 │  • observations (LLM job)                         │
 │  • recommendations (guardrailed, human-approved)  │
 │  • REPL: explore · approve/reject · ask · export  │
 └────────────────────────────────────────────────┘
        │
        ▼
 Spreadsheet board pack (.xlsx, six sheets) — the CMO artifact
```

## Why DeltaStream MVs over MCP

DeltaStream natively exposes any materialized view the API token's role can
`SELECT` as an **MCP tool** — no glue server to build. We removed ClickHouse from
the stack we manage (DeltaStream uses it internally to back MVs). The agent is a
plain MCP client: it discovers the MV tools, calls them, and reasons over live
state. This matches DeltaStream's positioning as a real-time context engine for
agents.

## Division of labor: streaming vs. agent

Full per-touch journey reconstruction with normalized window functions is
impractical in streaming SQL. So the split is deliberate:

- **DeltaStream** maintains the live aggregated *context*: spend per channel,
  the funnel counts, **per-account channel touch distribution** (touch count +
  most-recent touch time per channel), **won revenue per account**, and
  **share of model** — the brand's live standing in LLM answers (mention rate,
  citation rate, rank) for the buyer queries that matter. The last one is the
  leading indicator for the **AI Assistant** channel: LLM-influenced deals you
  can earn but not buy, so the agent tracks visibility instead of funding it.
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
- Brand and Events are excluded from agent autonomy entirely. **AI Assistant** is
  excluded too — not by policy but by economics: there is no media lever to
  reallocate (you can't buy an LLM recommendation), so the agent flags it as top
  ROI and refuses to fund it, and watches **share of model** instead.
- Every recommendation is logged with rationale and source-data references.
