-- mv_revenue_timeline: won revenue + deal count bucketed by minute. This is the
-- time axis the dashboard needs — the "revenue is moving" sparkline and the real
-- "what changed since you last looked" deltas — maintained continuously instead
-- of a windowed re-query. Buckets are 1 minute so a live demo shows a trend
-- within minutes (production would bucket by day); source streams read from
-- 'latest', so the series reflects the live session.
--
-- NOTE: FLOOR(<timestamp> TO MINUTE) is the time-bucket expression; validate it
-- on your DeltaStream version during bring-up (same as every statement here).

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_revenue_timeline" AS
SELECT
    FLOOR("event_time" TO MINUTE) AS "bucket",
    SUM("revenue")                AS "revenue",
    COUNT(*)                      AS "deals"
FROM "conversions"
WHERE "event_type" = 'closed_won'
GROUP BY FLOOR("event_time" TO MINUTE);
