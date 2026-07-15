-- mv_spend_timeline: spend per channel bucketed by minute — the real spend-pacing
-- signal (and, crossed with mv_touch_timeline, a live CPL). Now possible because
-- the spend feed carries event_time (see 02_spend.sql). Live spend fires every
-- tick, so this fills minute-by-minute during a demo.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_spend_timeline" AS
SELECT
    "channel",
    FLOOR("event_time" TO MINUTE) AS "bucket",
    SUM("spend_amount")           AS "spend"
FROM "spend"
GROUP BY "channel", FLOOR("event_time" TO MINUTE);
