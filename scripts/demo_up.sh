#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# One command brings the whole demo up: deploy the DeltaStream pipeline, publish
# the Q1 backfill anchor, start the live stream, wait for the views to populate,
# and serve the dashboard. Ctrl-C stops the server AND the background stream.
: "${DSQL_BIN:?set DSQL_BIN, e.g. export DSQL_BIN=../../dscliv2}"
: "${DS_SERVER:?set DS_SERVER, e.g. export DS_SERVER=https://api-mizaz8.deltastream.io/v2}"
: "${DS_TOKEN:?set DS_TOKEN to your DeltaStream API token}"
MAX_JOURNEYS="${MAX_JOURNEYS:-12}"
INTERVAL="${INTERVAL:-8}"
PORT="${PORT:-8787}"

echo "==> ensuring the attribution database exists"
python scripts/run_sql.py deltastream/00_stores.sql --keep-going --cli "$DSQL_BIN" --server "$DS_SERVER"

echo "==> terminating running queries"
python scripts/terminate_queries.py --cli "$DSQL_BIN" --server "$DS_SERVER"

echo "==> tearing down relations"
python scripts/run_sql.py deltastream/teardown.sql --keep-going --cli "$DSQL_BIN" --server "$DS_SERVER"

echo "==> deploying streams, changelogs, and materialized views"
python scripts/run_sql.py deltastream/deploy_all.sql --keep-going --cli "$DSQL_BIN" --server "$DS_SERVER"

# Backfill as its own blocking step, so the 36-deal anchor is fully published
# (and visibly confirmed) before anything reads the views. Streams read from
# 'latest', so this must run AFTER deploy — which it does.
echo "==> publishing the Q1 backfill anchor (36 deals across all channels)"
python -m attribution_agent.mock_generator --no-ambient

# Live trickle on top, in the background. --no-backfill because we just did it.
echo "==> starting the live stream in the background (capped at $MAX_JOURNEYS journeys)"
python -m attribution_agent.mock_generator --stream --no-backfill --no-ambient \
    --interval "$INTERVAL" --ambient-per-tick 0 --max-journeys "$MAX_JOURNEYS" &
STREAM_PID=$!
trap 'echo; echo "==> stopping live stream + server"; kill "$STREAM_PID" 2>/dev/null || true' EXIT INT TERM

echo "==> waiting for the pipeline to populate (won-revenue rows)…"
for i in $(seq 1 30); do
  n="$(python - <<'PY'
try:
    from attribution_agent.config import load_settings
    from attribution_agent.agent.deltastream_mcp import DeltaStreamMCPClient
    c = DeltaStreamMCPClient(load_settings().deltastream)
    print(len(c.query_view("won_revenue_by_account")))
except Exception:
    print(0)
PY
)"
  if [ "${n:-0}" -gt 0 ]; then echo "    ready — $n won accounts in the views"; break; fi
  echo "    not ready yet (${i}/30); sleeping 10s"; sleep 10
done

echo "==> serving the dashboard at http://localhost:$PORT/  (Ctrl-C to stop everything)"
python -m attribution_agent.api.board_view --source mcp --serve "$PORT"
