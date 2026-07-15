#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

: "${DSQL_BIN:?set DSQL_BIN, e.g. export DSQL_BIN=../../dscliv2}"
: "${DS_SERVER:?set DS_SERVER, e.g. export DS_SERVER=https://api-mizaz8.deltastream.io/v2}"
: "${DS_TOKEN:?set DS_TOKEN to your DeltaStream API token}"

echo "==> terminating running queries"
python scripts/terminate_queries.py --cli "$DSQL_BIN" --server "$DS_SERVER"

echo "==> tearing down relations (database is kept)"
python scripts/run_sql.py deltastream/teardown.sql --keep-going --cli "$DSQL_BIN" --server "$DS_SERVER"

echo "==> done. relations dropped; the attribution database remains."
