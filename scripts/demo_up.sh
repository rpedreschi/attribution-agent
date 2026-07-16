#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

: "${DSQL_BIN:?set DSQL_BIN, e.g. export DSQL_BIN=../../dscliv2}"
: "${DS_SERVER:?set DS_SERVER, e.g. export DS_SERVER=https://api-mizaz8.deltastream.io/v2}"
: "${DS_TOKEN:?set DS_TOKEN to your DeltaStream API token}"
MAX_JOURNEYS="${MAX_JOURNEYS:-12}"

echo "==> ensuring the attribution database exists"
python scripts/run_sql.py deltastream/00_stores.sql --keep-going --cli "$DSQL_BIN" --server "$DS_SERVER"

echo "==> terminating running queries"
python scripts/terminate_queries.py --cli "$DSQL_BIN" --server "$DS_SERVER"

echo "==> tearing down relations"
python scripts/run_sql.py deltastream/teardown.sql --keep-going --cli "$DSQL_BIN" --server "$DS_SERVER"

echo "==> deploying streams, changelogs, and materialized views"
python scripts/run_sql.py deltastream/deploy_all.sql --keep-going --cli "$DSQL_BIN" --server "$DS_SERVER"

echo "==> streaming data (Ctrl-C to stop; capped at $MAX_JOURNEYS live journeys)"
python -m attribution_agent.mock_generator --stream --backfill --no-ambient \
    --interval "${INTERVAL:-8}" --ambient-per-tick 0 --max-journeys "$MAX_JOURNEYS"
