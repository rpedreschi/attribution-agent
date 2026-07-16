-- `funnel_events`: touches + conversion stages normalized to (program_category,
-- stage) rows so the funnel materialized view is a single GROUP BY. Touches come
-- from the touchpoints stream; the other stages from the conversions stream.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE STREAM "funnel_events" (
    "event_time"       TIMESTAMP,
    "program_category" VARCHAR,
    "stage"            VARCHAR
) WITH (
    'topic' = 'rachel_funnel_events',
    'topic.partitions' = 1,
    'topic.replicas' = 1,
    'store' = 'demo_warpstream',
    'kafka.properties.request.timeout.ms' = '60000',
    'kafka.properties.delivery.timeout.ms' = '120000',
    'kafka.properties.linger.ms' = '100',
    'kafka.properties.batch.size' = '1048576',
    'value.format' = 'json',
    'timestamp' = 'event_time'
);

INSERT INTO "funnel_events"
SELECT "event_time", "program_category", 'touch' AS "stage"
FROM "touchpoints";

INSERT INTO "funnel_events"
SELECT "event_time", "program_category", "event_type" AS "stage"
FROM "conversions"
WHERE "event_type" IN ('conversation', 'mql', 'sql', 'opp_created', 'closed_won');
