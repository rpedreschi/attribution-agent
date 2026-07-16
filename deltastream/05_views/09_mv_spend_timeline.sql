-- mv_spend_timeline: spend per channel per 1-minute window — spend pacing (and,
-- crossed with mv_touch_timeline, live CPL). TUMBLE over the spend stream.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_spend_timeline" AS
SELECT
    "channel",
    window_start AS "bucket",
    window_end   AS "bucket_end",
    SUM("spend_amount") AS "spend"
FROM TUMBLE("spend", SIZE 1 MINUTE)
GROUP BY "channel", window_start, window_end;
