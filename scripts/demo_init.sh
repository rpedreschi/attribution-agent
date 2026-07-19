#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Load credentials from .env if present (see .env.example).
[ -f .env ] && set -a && . ./.env && set +a

# One-time setup for a NEW DeltaStream instance: create the Kafka store and the
# attribution database. Run this once after moving instances, then use
# demo_up.sh for every rebuild. Idempotent — safe to re-run ("already exists" is
# ignored). Kafka connection is read from the same config as the app (env vars
# or config/settings.yaml), so you only set credentials in one place.

: "${DSQL_BIN:?set DSQL_BIN, e.g. export DSQL_BIN=../../dscliv2}"
: "${DS_SERVER:?set DS_SERVER, e.g. export DS_SERVER=https://api-mizaz8.deltastream.io/v2}"
: "${DS_TOKEN:?set DS_TOKEN to your DeltaStream API token}"
STORE_NAME="${STORE_NAME:-demo_warpstream}"   # must match 'store' in the DDL

cfg() { python -c "from attribution_agent.config import load_settings as L; print(getattr(L().kafka,'$1') or '')"; }
KBOOT="$(cfg bootstrap_servers)"
KUSER="$(cfg sasl_username)"
KPASS="$(cfg sasl_password)"
[ -n "$KBOOT" ] && [ -n "$KUSER" ] && [ -n "$KPASS" ] || {
  echo "Kafka bootstrap/key/secret not set — put them in env (KAFKA_*) or config/settings.yaml"; exit 1; }

# If your DeltaStream version's CREATE STORE syntax differs, this is the one
# statement to edit.
echo "==> creating store \"$STORE_NAME\" -> $KBOOT"
"$DSQL_BIN" --server "$DS_SERVER" -c "CREATE STORE \"$STORE_NAME\" WITH (
  'type' = KAFKA,
  'kafka.sasl.hash_function' = PLAIN,
  'uris' = '$KBOOT',
  'kafka.sasl.username' = '$KUSER',
  'kafka.sasl.password' = '$KPASS'
);" || echo "   (CREATE STORE returned non-zero — likely already exists; continuing)"

echo "==> creating the attribution database"
python scripts/run_sql.py deltastream/00_stores.sql --keep-going --cli "$DSQL_BIN" --server "$DS_SERVER"

echo "==> init complete. Next: bash scripts/demo_up.sh"
