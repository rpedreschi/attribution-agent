-- mv_som_timeline: share-of-model probes + mentions per buyer query per 1-minute
-- window — the AI-answer slip as a live curve. TUMBLE over share_of_model.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_som_timeline" AS
SELECT
    "buyer_query",
    window_start AS "bucket",
    window_end   AS "bucket_end",
    COUNT(*)         AS "probes",
    SUM("mentioned") AS "mentions"
FROM TUMBLE("share_of_model", SIZE 1 MINUTE)
GROUP BY "buyer_query", window_start, window_end;
