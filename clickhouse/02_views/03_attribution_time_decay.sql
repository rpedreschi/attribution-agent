-- attribution_time_decay (refreshable materialized view)
-- Exponential decay with a 7-day half-life: a touch's credit halves for every
-- 7 days it sits before close. Weights are normalized per opportunity so each
-- deal still distributes exactly its own revenue (totals tie to last_touch and
-- linear). This is the model the agent uses for budget decisions.

CREATE MATERIALIZED VIEW IF NOT EXISTS attribution.attribution_time_decay
REFRESH EVERY 15 MINUTE
ENGINE = MergeTree ORDER BY channel
AS
WITH weighted AS
(
    SELECT
        opportunity_id,
        channel,
        program_category,
        revenue,
        pow(2, -1 * days_before_close / 7.0)                                   AS w,
        sum(pow(2, -1 * days_before_close / 7.0)) OVER (PARTITION BY opportunity_id) AS w_total
    FROM attribution.v_won_journeys
)
SELECT
    channel,
    program_category,
    'time_decay'                              AS model,
    sum(revenue * w / w_total)                AS attributed_revenue,
    count(DISTINCT opportunity_id)             AS attributed_deals
FROM weighted
GROUP BY channel, program_category;
