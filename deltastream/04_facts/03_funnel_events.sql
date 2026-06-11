-- `funnel_events`: touches + conversion stages normalized to (program_category,
-- stage) rows so the funnel materialized view is a single GROUP BY. Touches come
-- from the touchpoints stream; the other stages from the conversions stream.

CREATE STREAM funnel_events (
    "event_time"       TIMESTAMP,
    "program_category" VARCHAR,
    "stage"            VARCHAR
) WITH (
    'topic' = 'attribution.funnel_events',
    'store' = 'confluent_cloud',
    'value.format' = 'json',
    'timestamp' = 'event_time'
);

INSERT INTO funnel_events
SELECT "event_time", "program_category", 'touch' AS "stage"
FROM touchpoints;

INSERT INTO funnel_events
SELECT "event_time", "program_category", "event_type" AS "stage"
FROM conversions
WHERE "event_type" IN ('conversation', 'mql', 'sql', 'opp_created', 'closed_won');
