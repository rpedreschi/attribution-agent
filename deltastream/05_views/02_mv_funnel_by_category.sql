-- mv_funnel_by_category: the B2B funnel counts per program category, in one
-- pivoted row each. touch -> conversation -> MQL -> SQL -> opp -> won.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_funnel_by_category" AS
SELECT
    "program_category",
    COUNT(CASE WHEN "stage" = 'touch'        THEN 1 END) AS "touches",
    COUNT(CASE WHEN "stage" = 'conversation' THEN 1 END) AS "conversations",
    COUNT(CASE WHEN "stage" = 'mql'          THEN 1 END) AS "mqls",
    COUNT(CASE WHEN "stage" = 'sql'          THEN 1 END) AS "sqls",
    COUNT(CASE WHEN "stage" = 'opp_created'  THEN 1 END) AS "opps",
    COUNT(CASE WHEN "stage" = 'closed_won'   THEN 1 END) AS "won"
FROM "funnel_events"
GROUP BY "program_category";
