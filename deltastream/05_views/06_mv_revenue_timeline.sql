-- mv_revenue_timeline: won revenue + deal count per 1-minute tumbling window.
-- Backs the dashboard revenue sparkline + the "revenue pace" what-changed card.
-- Uses TUMBLE (DeltaStream's time-window function) over the conversions stream's
-- designated event_time rowtime.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_revenue_timeline" AS
SELECT
    window_start AS "bucket",
    window_end   AS "bucket_end",
    SUM("revenue") AS "revenue",
    COUNT(*)       AS "deals"
FROM TUMBLE("conversions", SIZE 1 MINUTE)
WHERE "event_type" = 'closed_won'
GROUP BY window_start, window_end;
