# DeltaStream Marketing Attribution Agent

Real-time, multi-touch B2B marketing attribution plus an agent that recommends
budget reallocations — delivered as a weekly spreadsheet (the artifact CMOs
already live in), not a dashboard.

Positioned as **"Bizible but better"**: same attribution category, but the
numbers are real-time and the budget recommendation is trustworthy. The wedge is
the attribution pain at the $50M–$250M B2B inflection, where CMOs have to defend
marketing spend to the board and can't trust the numbers.

> **Phase 0 demo.** This repo is the buildable demo: schema, deterministic mock
> data, DeltaStream SQL, ClickHouse views, the agent, and the spreadsheet
> generator. The agent's *recommendation* engine is the genuinely agentic piece;
> reporting and observation-writing are honestly-framed scheduled LLM jobs.

## Pipeline

```
6 source APIs → Kafka → DeltaStream (identity resolution) → ClickHouse → Agent → .xlsx board pack
```

See [`docs/reference_architecture.md`](docs/reference_architecture.md) for the
full diagram and the identity-resolution and attribution-model details.

## Repo layout

```
clickhouse/
  01_tables/        marketing_touchpoints, conversions, campaign_spend, accounts
  02_views/         won-journeys + 3 attribution models, by-channel, funnel, cac_roi
deltastream/
  00_stores.sql     Kafka source + ClickHouse sink stores
  01_streams/       CREATE STREAM from each source topic
  02_changelogs/    Salesforce CDC changelogs (the identity spine)
  03_identity/      anon → known resolution, normalized resolved touchpoints
  04_sinks/         INSERT INTO ClickHouse
src/attribution_agent/
  config.py         YAML + env settings
  sample_data.py    canonical Acme Cloud figures (the demo source of truth)
  mock_generator/   deterministic events → Kafka (or JSONL in --dry-run)
  agent/            guardrails, ClickHouse client, reporting, observations,
                    recommendations, AgentCore runtime
  spreadsheet/      openpyxl six-sheet board pack
docs/               reference architecture + demo script
tests/              tie-out, guardrail, and end-to-end tests
```

## Quickstart (no infrastructure)

The deterministic sample path needs no Kafka/DeltaStream/ClickHouse/Bedrock:

```bash
pip install -e .

# Build the board pack from the canonical Acme Cloud dataset:
python -m attribution_agent.spreadsheet
# → out/acme_cloud_attribution_2026-Q1.xlsx

# Inspect the agent's JSON output (observations + recommendations):
python -m attribution_agent.agent.runtime

# Generate source events to JSONL files (no broker required):
python -m attribution_agent.mock_generator --dry-run --out-dir events

# Run the tests:
pytest
```

Without AWS credentials the observation/recommendation rationale falls back to
deterministic, number-grounded templates, so the artifact is always produced.

## Running against live infrastructure

1. **Configure.** Copy `config/settings.example.yaml` to `config/settings.yaml`
   and fill in Kafka, ClickHouse, and Bedrock/AgentCore details. Secrets can be
   supplied via `${ENV_VAR}` references or matching environment variables.

2. **Create the ClickHouse schema**, then the views:
   ```bash
   for f in clickhouse/01_tables/*.sql clickhouse/02_views/*.sql; do
     clickhouse-client --queries-file "$f"   # or your CH client of choice
   done
   ```

3. **Deploy the DeltaStream jobs** in order: `00_stores.sql`, `01_streams/`,
   `02_changelogs/`, `03_identity/`, `04_sinks/`.

4. **Publish source events** (the mock generator stands in for the real APIs):
   ```bash
   python -m attribution_agent.mock_generator
   ```

5. **Generate the board pack from live data:**
   ```bash
   python -m attribution_agent.spreadsheet --source clickhouse
   ```

6. **Deploy the agent** to Bedrock AgentCore using
   `attribution_agent.agent.runtime:agent_entrypoint` (the module exposes an
   AgentCore `app` when the `bedrock_agentcore` SDK is installed).

## Agent guardrails (v1)

- Agent recommends, **human approves** — no autonomous spend changes.
- Reallocation capped at **±20%** of current channel spend per week.
- Channels with **<30 conversions** in the trailing 90 days are excluded.
- **Brand and Events** are excluded from agent autonomy entirely.
- Every recommendation is logged with rationale and source-data references.

## Internal consistency

`src/attribution_agent/sample_data.py` is the canonical demo dataset and asserts
its own invariants (`python -m attribution_agent.sample_data`): all three
attribution models sum to **$4.28M**, attributed deals sum to **36**, spend sums
to **$1.9M**, and the funnel rolls up to the same totals. The six spreadsheet
sheets therefore tie out by construction.

## The artifact

[`DeltaStream_Attribution_Agent_Sample_Output.xlsx`](DeltaStream_Attribution_Agent_Sample_Output.xlsx)
is the generated sample board pack. Six sheets: Executive Summary, Attribution
by Channel, Attribution by Campaign, Funnel Metrics, CAC and ROI, Data &
Assumptions.
