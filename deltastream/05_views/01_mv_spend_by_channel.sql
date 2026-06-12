-- mv_spend_by_channel: trailing spend per channel. Exposed over MCP as the
-- denominator for the agent's CAC and ROI math.

CREATE MATERIALIZED VIEW "mv_spend_by_channel" AS
SELECT
    "channel",
    "program_category",
    SUM("spend_amount") AS "spend"
FROM "spend"
GROUP BY "channel", "program_category";
