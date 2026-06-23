-- mv_share_of_model: per buyer query, the brand's standing in the LLM answer
-- space across all probes in the live window. mention_rate (mentions/probes) and
-- avg_rank are the signals the agent reads — when a model update drops the brand
-- out of an answer, mention_rate falls and avg_rank climbs toward 99 (unranked).
--
-- Source streams read from the 'latest' offset, so this view reflects the probes
-- emitted since the queries started — i.e. the live session — which is exactly
-- the "right now" picture the agent needs (an all-time average would dilute it).

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_share_of_model" AS
SELECT
    "buyer_query",
    COUNT(*)                              AS "probes",
    SUM("mentioned")                      AS "mentions",
    SUM("cited")                          AS "citations",
    MIN("brand_rank")                     AS "best_rank",
    AVG(CAST("brand_rank" AS DOUBLE))     AS "avg_rank",
    MAX("event_time")                     AS "last_checked"
FROM "share_of_model"
GROUP BY "buyer_query";
