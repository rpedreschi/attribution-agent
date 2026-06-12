-- mv_spend_by_channel: trailing spend per channel. Exposed over MCP as the
-- denominator for the agent's CAC and ROI math.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_spend_by_channel" AS
SELECT
    "channel",
    "program_category",
    SUM("spend_amount") AS "spend"
FROM "spend"
GROUP BY "channel", "program_category";
