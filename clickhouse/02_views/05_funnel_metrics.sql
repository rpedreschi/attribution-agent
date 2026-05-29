-- funnel_metrics (refreshable materialized view)
-- Funnel counts by program category across the full B2B funnel:
-- touch -> conversation -> MQL -> SQL -> opp -> won.
-- Each stage is a distinct event_type in the conversions table; touches come
-- from marketing_touchpoints. Feeds the "Funnel Metrics" sheet, and the
-- stage-to-stage conversion rates the agent reasons over.

CREATE MATERIALIZED VIEW IF NOT EXISTS attribution.funnel_metrics
REFRESH EVERY 15 MINUTE
ENGINE = MergeTree ORDER BY program_category
AS
SELECT
    program_category,
    countIf(stage = 'touch')         AS touches,
    countIf(stage = 'conversation')  AS conversations,
    countIf(stage = 'mql')           AS mqls,
    countIf(stage = 'sql')           AS sqls,
    countIf(stage = 'opp_created')   AS opps,
    countIf(stage = 'closed_won')    AS won
FROM
(
    SELECT program_category, 'touch' AS stage
    FROM attribution.marketing_touchpoints
    UNION ALL
    SELECT program_category, event_type AS stage
    FROM attribution.conversions
    WHERE event_type IN ('conversation', 'mql', 'sql', 'opp_created', 'closed_won')
)
GROUP BY program_category
ORDER BY won DESC;
