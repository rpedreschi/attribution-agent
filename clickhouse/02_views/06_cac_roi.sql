-- cac_roi (refreshable materialized view)
-- Per program category: trailing spend, attributed revenue (time-decay, the
-- decision model), attributed deals, CAC, ROI multiple, and payback period in
-- months (assuming revenue is ARR). Feeds the "CAC and ROI" sheet.
--
-- CAC = spend / new customers (attributed_deals).
-- ROI = attributed_revenue / spend.
-- Payback (months) = spend / (attributed ARR / 12) = 12 / ROI.

CREATE MATERIALIZED VIEW IF NOT EXISTS attribution.cac_roi
REFRESH EVERY 15 MINUTE
ENGINE = MergeTree ORDER BY program_category
AS
WITH
    spend AS
    (
        SELECT program_category, sum(spend_amount) AS spend_amount
        FROM attribution.campaign_spend
        GROUP BY program_category
    ),
    attr AS
    (
        SELECT program_category,
               sum(attributed_revenue) AS attributed_revenue,
               max(attributed_deals)   AS attributed_deals
        FROM attribution.attribution_time_decay
        GROUP BY program_category
    )
SELECT
    coalesce(s.program_category, a.program_category)                       AS program_category,
    s.spend_amount                                                         AS spend,
    a.attributed_revenue                                                   AS attributed_revenue,
    a.attributed_deals                                                     AS attributed_deals,
    if(a.attributed_deals > 0, round(s.spend_amount / a.attributed_deals, 2), NULL) AS cac,
    if(s.spend_amount > 0, round(a.attributed_revenue / s.spend_amount, 2), NULL)   AS roi_multiple,
    if(a.attributed_revenue > 0, round(12 * s.spend_amount / a.attributed_revenue, 1), NULL) AS payback_months
FROM spend AS s
FULL OUTER JOIN attr AS a ON a.program_category = s.program_category
ORDER BY roi_multiple DESC;
