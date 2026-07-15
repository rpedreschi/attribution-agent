-- Unified `conversions` stream: the B2B funnel-stage transitions, normalized
-- from Salesforce opportunity changes and HubSpot lifecycle changes. Feeds the
-- funnel + won-revenue materialized views in 05_views.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE STREAM "conversions" (
    "event_time"       TIMESTAMP,
    "account_id"       VARCHAR,
    "contact_id"       VARCHAR,
    "email"            VARCHAR,
    "event_type"       VARCHAR,    -- conversation | mql | sql | opp_created | closed_won | closed_lost
    "opportunity_id"   VARCHAR,
    "revenue"          DOUBLE,
    "deal_size"        VARCHAR,
    "program_category" VARCHAR
) WITH (
    'topic' = 'rachel_conversions',
    'topic.partitions' = 1,
    'topic.replicas' = 1,
    'store' = 'demo_warpstream',
    'value.format' = 'json',
    'timestamp' = 'event_time'
);

-- Salesforce opportunity transitions.
INSERT INTO "conversions"
SELECT
    o."event_time", o."account_id", CAST(NULL AS VARCHAR) AS "contact_id",
    CAST(NULL AS VARCHAR) AS "email",
    CAST(CASE o."stage_to"
        WHEN 'ClosedWon'  THEN 'closed_won'
        WHEN 'ClosedLost' THEN 'closed_lost'
        WHEN 'SQL'        THEN 'sql'
        ELSE 'opp_created'
    END AS VARCHAR) AS "event_type",
    o."opportunity_id",
    CAST(CASE WHEN o."stage_to" = 'ClosedWon' THEN o."amount" ELSE 0 END AS DOUBLE) AS "revenue",
    o."deal_size", o."program_category"
FROM "sf_opportunities" o;

-- HubSpot lifecycle transitions (conversation + MQL).
INSERT INTO "conversions"
SELECT
    h."event_time", c."account_id", c."contact_id",
    c."email" AS "email",
    CAST(CASE h."lifecycle_to" WHEN 'mql' THEN 'mql' ELSE 'conversation' END AS VARCHAR) AS "event_type",
    CAST(NULL AS VARCHAR) AS "opportunity_id", CAST(0 AS DOUBLE) AS "revenue",
    '' AS "deal_size", h."program_category"
FROM "hubspot_events" h
JOIN "sf_contacts" c ON h."email" = c."email"
WHERE h."event_type" = 'lifecycle_change'
  AND h."lifecycle_to" IN ('mql', 'sql', 'opportunity');
