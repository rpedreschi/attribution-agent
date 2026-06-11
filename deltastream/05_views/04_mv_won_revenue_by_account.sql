-- mv_won_revenue_by_account: closed-won revenue and close time per account.
-- The numerator the agent distributes across channels using the touch
-- distribution. Summed across accounts it is the total attributed revenue.

CREATE MATERIALIZED VIEW mv_won_revenue_by_account AS
SELECT
    "account_id",
    SUM("revenue")    AS "revenue",
    MAX("event_time") AS "close_time"
FROM conversions
WHERE "event_type" = 'closed_won'
GROUP BY "account_id";
