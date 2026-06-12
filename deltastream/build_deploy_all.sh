#!/usr/bin/env bash
# Regenerate deltastream/deploy_all.sql — a clean, COMMENT-FREE bundle of every
# stream/changelog/MV statement in deploy order, so it runs/pastes through the
# DeltaStream CLI without the REPL collapsing comments into the statements.
#
# Assumes the `attribution` database already exists (create it once with
# 00_stores.sql). This bundle does NOT create or drop the database — it only
# (re)builds the relations inside it. Run from the repo root:
#   bash deltastream/build_deploy_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# 00_stores.sql is intentionally excluded: it creates the database (one-time),
# which we don't want to repeat on every redeploy.
FILES=(
  deltastream/01_streams/ga4_sessions.sql
  deltastream/01_streams/hubspot_events.sql
  deltastream/01_streams/outreach_activity.sql
  deltastream/01_streams/ads_spend.sql
  deltastream/02_changelogs/salesforce_cdc.sql
  deltastream/03_identity/01_web_identity_map.sql
  deltastream/03_identity/02_touchpoints.sql
  deltastream/04_facts/01_conversions.sql
  deltastream/04_facts/02_spend.sql
  deltastream/04_facts/03_funnel_events.sql
  deltastream/05_views/01_mv_spend_by_channel.sql
  deltastream/05_views/02_mv_funnel_by_category.sql
  deltastream/05_views/03_mv_channel_touch_distribution.sql
  deltastream/05_views/04_mv_won_revenue_by_account.sql
)
OUT=deltastream/deploy_all.sql

# Strip `--` comments and trailing whitespace, squeeze blank lines — leaving pure
# SQL. (Safe here: no `--` or `;` appears inside a string literal in these files.)
strip() { sed 's/--.*$//' "$1" | sed 's/[[:space:]]*$//' | cat -s; }

{
  echo 'USE DATABASE "attribution";'
  echo 'USE SCHEMA "public";'
  for f in "${FILES[@]}"; do
    echo
    strip "$f"
  done
} > "$OUT"

echo "wrote $OUT ($(wc -l < "$OUT") lines, $(grep -c ';' "$OUT") statements)"
