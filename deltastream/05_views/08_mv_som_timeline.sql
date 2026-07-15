-- mv_som_timeline: share-of-model probes + mentions per buyer query, bucketed by
-- minute. Turns the AI answer-space slip into a real *curve* — the dashboard can
-- draw mention-rate declining as a model update drops the brand out of the
-- answer, instead of only the current snapshot.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_som_timeline" AS
SELECT
    "buyer_query",
    FLOOR("event_time" TO MINUTE) AS "bucket",
    COUNT(*)                      AS "probes",
    SUM("mentioned")              AS "mentions"
FROM "share_of_model"
GROUP BY "buyer_query", FLOOR("event_time" TO MINUTE);
