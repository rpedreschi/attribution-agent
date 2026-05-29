-- attribution_linear (refreshable materialized view)
-- Equal credit (revenue / touch_count) to every touch in the journey.

CREATE MATERIALIZED VIEW IF NOT EXISTS attribution.attribution_linear
REFRESH EVERY 15 MINUTE
ENGINE = MergeTree ORDER BY channel
AS
SELECT
    channel,
    program_category,
    'linear'                                          AS model,
    sum(revenue / touch_count)                        AS attributed_revenue,
    count(DISTINCT opportunity_id)                     AS attributed_deals
FROM attribution.v_won_journeys
GROUP BY channel, program_category;
