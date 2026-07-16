-- mv_touch_timeline: resolved touches per channel per 1-minute window (per-channel
-- activity trend). TUMBLE over the touchpoints stream.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_touch_timeline" AS
SELECT
    "channel",
    window_start AS "bucket",
    COUNT(*)     AS "touches"
FROM TUMBLE("touchpoints", SIZE 1 MINUTE)
WHERE "account_id" IS NOT NULL
GROUP BY "channel", window_start, window_end;
