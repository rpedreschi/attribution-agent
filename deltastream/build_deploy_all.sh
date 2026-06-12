#!/usr/bin/env bash
# Regenerate deltastream/deploy_all.sql — every deltastream/ statement
# concatenated in deploy order, for one-shot testing. Run from the repo root:
#   bash deltastream/build_deploy_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."

FILES=(
  deltastream/00_stores.sql
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

{
  echo "-- =============================================================================="
  echo "-- deploy_all.sql — GENERATED, every deltastream/ statement in deploy order."
  echo "--"
  echo "-- Convenience bundle for testing: run this one file instead of opening each"
  echo "-- folder. Regenerate with deltastream/build_deploy_all.sh after editing any"
  echo "-- source file — do not hand-edit this file."
  echo "--"
  echo "-- Prereqs: the demo_confluent store exists (default), datagen has published to"
  echo "-- the src.* topics, and you run with a DDL-capable role. The repeated"
  echo "-- USE DATABASE/SCHEMA headers are harmless."
  echo "-- =============================================================================="
  for f in "${FILES[@]}"; do
    echo
    echo "-- ############################################################################"
    echo "-- ## $f"
    echo "-- ############################################################################"
    echo
    cat "$f"
  done
} > "$OUT"

echo "wrote $OUT ($(wc -l < "$OUT") lines)"
