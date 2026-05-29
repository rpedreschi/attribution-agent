-- attribution_last_touch (refreshable materialized view)
-- 100% of deal revenue to the channel of the final touch before close.
-- Refreshed every 15 minutes — "real-time" relative to a weekly board pack,
-- and the cadence that keeps the agent's recommendations from going stale.

CREATE MATERIALIZED VIEW IF NOT EXISTS attribution.attribution_last_touch
REFRESH EVERY 15 MINUTE
ENGINE = MergeTree ORDER BY channel
AS
SELECT
    channel,
    program_category,
    'last_touch'                       AS model,
    sum(revenue)                       AS attributed_revenue,
    count(DISTINCT opportunity_id)      AS attributed_deals
FROM attribution.v_won_journeys
WHERE touch_time = last_touch_time
GROUP BY channel, program_category;
