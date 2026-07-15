-- mv_touch_timeline: resolved touch count per channel, bucketed by minute. Backs
-- the per-channel activity trend (spend-pacing proxy) and the "channel X is
-- rising / became a top first-touch" cards. Reads the same touchpoints stream
-- the attribution views use, so no new source plumbing.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_touch_timeline" AS
SELECT
    "channel",
    FLOOR("event_time" TO MINUTE) AS "bucket",
    COUNT(*)                      AS "touches"
FROM "touchpoints"
WHERE "account_id" IS NOT NULL
GROUP BY "channel", FLOOR("event_time" TO MINUTE);
