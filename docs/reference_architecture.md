# Reference Architecture

The DeltaStream Marketing Attribution Agent delivers real-time multi-touch
attribution and a budget-reallocation agent. The output is a weekly spreadsheet
— the artifact CMOs already live in — not a dashboard.

```
 Source systems (6 APIs)
   Salesforce · HubSpot · GA4 · LinkedIn Ads · Google Ads · Outreach
        │   events published as JSON to per-source Kafka topics
        ▼
 ┌─────────────┐
 │    Kafka    │  event bus (Confluent Cloud / MSK / self-hosted)
 └─────────────┘
        │   CREATE STREAM / CREATE CHANGELOG
        ▼
 ┌──────────────────────────────────────────────┐
 │              DeltaStream (SQL)                 │
 │  • CREATE STREAM from each Kafka topic         │
 │  • Identity resolution via CHANGELOG joins     │
 │      anon web user_id → contact → account      │
 │  • Normalize to the touchpoint / conversion    │
 │    shapes, then INSERT INTO ClickHouse         │
 └──────────────────────────────────────────────┘
        │   INSERT INTO clickhouse_sink
        ▼
 ┌──────────────────────────────────────────────┐
 │                 ClickHouse                     │
 │  Tables: marketing_touchpoints · conversions   │
 │          campaign_spend · accounts             │
 │  Refreshable MVs (15 min):                      │
 │   attribution_last_touch / _linear / _time_decay│
 │   funnel_metrics · cac_roi                       │
 └──────────────────────────────────────────────┘
        │   queried by the agent layer
        ▼
 ┌──────────────────────────────────────────────┐
 │      Agent (AWS Bedrock AgentCore + Claude)    │
 │  1. reporting       → BoardPackData             │
 │  2. observations    → prose commentary (LLM job)│
 │  3. recommendations → guardrailed reallocations │
 │                       (the actual agent)        │
 └──────────────────────────────────────────────┘
        │
        ▼
 Spreadsheet board pack (.xlsx, six sheets) — the CMO artifact
```

## Why this split

- **DeltaStream** owns ingestion, identity resolution, and stream-to-table
  transformation. Flink under the hood, exposed as SQL.
- **ClickHouse** owns the analytical attribution queries. The three models are
  refreshable materialized views so the numbers are never more than ~15 minutes
  stale — that freshness is the moat, because batch attribution produces
  *confidently wrong* recommendations.
- **AgentCore** wraps the agent (Runtime, Policy, Observability, Evaluations).
  Claude (via Bedrock) writes observations and recommendation rationale; the
  reallocation math itself is deterministic and auditable.

## Identity resolution

Anonymous GA4 web traffic carries only a `user_id` (the GA4 client id). A
HubSpot form submission carries both that web cookie (`web_user_id`) and an
email; joining the email to the Salesforce contacts CDC changelog yields
`web_user_id → contact_id → account_id`, materialized as the `web_identity_map`
changelog. GA4 touches then temporal-join that map to attach an account; once an
account is attached, all of its touches — past anonymous and future known —
roll up to the right deal. This is the B2B extension to the published
e-commerce-shaped attribution pattern.

## Attribution models

All three distribute the **same** closed-won revenue; they differ only in how
credit is spread across a journey's touches:

| Model       | Credit rule                                   |
|-------------|-----------------------------------------------|
| Last touch  | 100% to the final touch before close          |
| Linear      | Equal credit (revenue / touch count)          |
| Time decay  | Exponential, 7-day half-life, normalized/opp  |

The **model-agreement coefficient** (average pairwise correlation of the three
channel-share vectors) tells the CMO how much the model choice matters. Low
agreement is exactly where a single-model vendor would mislead.

## Agent guardrails (v1)

- Agent recommends, human approves — no autonomous spend changes.
- Reallocation capped at ±20% of current channel spend per week.
- Channels with <30 conversions in the trailing 90 days are excluded.
- Brand and Events are excluded from agent autonomy entirely.
- Every recommendation is logged with rationale and source-data references.
