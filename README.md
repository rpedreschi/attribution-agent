# DeltaStream Marketing Attribution Agent

Real-time, multi-touch B2B marketing attribution plus an agent that recommends
budget reallocations — explored through an interactive CLI and exported as a
weekly spreadsheet (the artifact CMOs already live in).

Positioned as **"Bizible but better"**: same attribution category, but the
numbers are real-time and the budget recommendation is trustworthy. The wedge is
the attribution pain at the $50M–$250M B2B inflection, where CMOs have to defend
marketing spend to the board and can't trust the numbers.

## Pipeline

```
local datagen → Confluent Cloud (Kafka) → DeltaStream (identity resolution
   + materialized views) → DeltaStream MCP endpoint → interactive agent → .xlsx
```

DeltaStream exposes each materialized view the API token's role can `SELECT` as
an **MCP tool**; the agent is a plain MCP client. ClickHouse is no longer part of
the stack we manage. See [`docs/reference_architecture.md`](docs/reference_architecture.md)
for the full diagram, the identity-resolution detail, and the
streaming-vs-agent division of labor.

## Repo layout

```
deltastream/
  00_stores.sql       Confluent Cloud Kafka store
  01_streams/         CREATE STREAM from each source topic
  02_changelogs/      Salesforce CDC changelogs (the identity spine)
  03_identity/        anon → known resolution, unified touchpoints stream
  04_facts/           conversions, spend, funnel_events streams
  05_views/           the 4 materialized views (the MCP context)
  06_mcp/             role + GRANTs + API_TOKEN (exposes the MVs over MCP)
src/attribution_agent/
  config.py           YAML + env settings (Confluent + DeltaStream MCP)
  sample_data.py      canonical Acme Cloud figures (the demo source of truth)
  mock_generator/     deterministic events → Confluent (or JSONL dry-run)
  agent/
    deltastream_mcp.py  MCP client (lists + calls MV tools)
    reporting.py        BoardPackData; from_sample / from_mcp + attribution math
    guardrails.py       ±20% cap, 30-conversion floor, Brand/Events exclusion
    observations.py     scheduled LLM job (prose commentary)
    recommendations.py  the guardrailed reallocation agent
    cli.py              interactive REPL (explore · approve/reject · ask · export)
    runtime.py          AgentCore entrypoint + run_pipeline
  spreadsheet/        openpyxl six-sheet board pack
docs/                 reference architecture + demo script
tests/                tie-out, guardrail, MCP, and end-to-end tests
```

## Quickstart (no infrastructure)

The deterministic sample path needs no Kafka/DeltaStream/Anthropic credentials:

```bash
pip install -e .

# Launch the interactive agent on the sample dataset:
python -m attribution_agent.agent.cli --source sample
#   agent> summary | channels | funnel | cac | recs
#   agent> approve 0 too aggressive      (logged to out/decisions.jsonl)
#   agent> ask which channel has the best payback?
#   agent> export                        (writes the xlsx board pack)

# Or one-shot the board pack:
python -m attribution_agent.spreadsheet         # → out/acme_cloud_attribution_2026-Q1.xlsx

# Generate source events to JSONL (no broker required):
python -m attribution_agent.mock_generator --dry-run --out-dir events

pytest
```

Without an LLM key, observations and the `ask` command fall back to
deterministic, number-grounded templates so the artifact always builds.

## Running the real demo (Confluent + DeltaStream + MCP)

1. **Configure.** Copy `config/settings.example.yaml` to `config/settings.yaml`
   (gitignored) and fill in Confluent, DeltaStream, and Anthropic details — or
   supply them via env vars (`KAFKA_API_KEY`, `KAFKA_API_SECRET`,
   `DELTASTREAM_API_TOKEN`, `ANTHROPIC_API_KEY`). Secrets never go in tracked
   files.

2. **Create topics and publish events** from your machine:
   ```bash
   python -m attribution_agent.mock_generator --create-topics
   ```

3. **Deploy the DeltaStream objects** in order: `00_stores.sql`, `01_streams/`,
   `02_changelogs/`, `03_identity/`, `04_facts/`, `05_views/`, then
   `06_mcp/01_expose_over_mcp.sql`. Copy the API token from the last step into
   `DELTASTREAM_API_TOKEN`.

4. **Check the bring-up** — config, Confluent topics, the live MCP handshake
   (lists the exposed MVs), and the LLM backend, in one command:
   ```bash
   python -m attribution_agent.agent.cli doctor
   ```

5. **Launch the agent against live data:**
   ```bash
   python -m attribution_agent.agent.cli            # auto-detects the MCP token
   #   agent> tools        # lists the MVs exposed over MCP
   #   agent> refresh      # re-pull live state
   ```

6. **(Optional) deploy to Bedrock AgentCore** using
   `attribution_agent.agent.runtime:agent_entrypoint` (set `agent.llm_backend:
   bedrock`); the module exposes an AgentCore `app` when the `bedrock_agentcore`
   SDK is installed.

## Agent guardrails (v1)

- Agent recommends, **human approves** — the CLI logs every `approve`/`reject`
  to `out/decisions.jsonl`. No autonomous spend changes.
- Reallocation capped at **±20%** of current channel spend per week.
- Channels with **<30 conversions** in the trailing 90 days are excluded.
- **Brand and Events** are excluded from agent autonomy entirely.
- Every recommendation carries its rationale and source-data references.

## Internal consistency

`src/attribution_agent/sample_data.py` is the canonical demo dataset and asserts
its own invariants (`python -m attribution_agent.sample_data`): all three
attribution models sum to **$4.28M**, attributed deals sum to **36**, spend sums
to **$1.9M**, and the funnel rolls up to the same totals. The six spreadsheet
sheets tie out by construction.

## The artifact

[`DeltaStream_Attribution_Agent_Sample_Output.xlsx`](DeltaStream_Attribution_Agent_Sample_Output.xlsx)
is the generated sample board pack: Executive Summary, Attribution by Channel,
Attribution by Campaign, Funnel Metrics, CAC and ROI, Data & Assumptions.
