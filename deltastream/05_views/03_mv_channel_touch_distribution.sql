-- mv_channel_touch_distribution: per resolved account, the touch count and most
-- recent touch time on each channel. This is the attribution *context* the agent
-- needs: joined to mv_won_revenue_by_account it lets the agent compute all three
-- models (last touch = channel with the latest touch; linear = touch-count
-- share; time decay = recency-weighted from last_touch_time vs close_time).
--
-- Full per-touch journey reconstruction with normalized window functions is
-- impractical in streaming SQL, so the heavy arithmetic is deliberately pushed
-- to the agent — DeltaStream serves the live aggregated state.

CREATE MATERIALIZED VIEW "mv_channel_touch_distribution" AS
SELECT
    "account_id",
    "channel",
    "program_category",
    COUNT(*)          AS "touch_count",
    MAX("event_time") AS "last_touch_time"
FROM "touchpoints"
WHERE "account_id" IS NOT NULL
GROUP BY "account_id", "channel", "program_category";
