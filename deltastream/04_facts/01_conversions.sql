-- Unified `conversions` stream: the B2B funnel-stage transitions, normalized
-- from Salesforce opportunity changes and HubSpot lifecycle changes. Feeds the
-- funnel + won-revenue materialized views in 05_views.

CREATE STREAM conversions (
    "event_time"       TIMESTAMP,
    "account_id"       VARCHAR,
    "contact_id"       VARCHAR,
    "event_type"       VARCHAR,    -- conversation | mql | sql | opp_created | closed_won | closed_lost
    "opportunity_id"   VARCHAR,
    "revenue"          DOUBLE,
    "deal_size"        VARCHAR,
    "program_category" VARCHAR
) WITH (
    'topic' = 'attribution.conversions',
    'store' = 'confluent_cloud',
    'value.format' = 'json',
    'timestamp' = 'event_time'
);

-- Salesforce opportunity transitions.
INSERT INTO conversions
SELECT
    o."event_time", o."account_id", CAST(NULL AS VARCHAR) AS "contact_id",
    CASE o."stage_to"
        WHEN 'ClosedWon'  THEN 'closed_won'
        WHEN 'ClosedLost' THEN 'closed_lost'
        WHEN 'SQL'        THEN 'sql'
        ELSE 'opp_created'
    END AS "event_type",
    o."opportunity_id",
    CASE WHEN o."stage_to" = 'ClosedWon' THEN o."amount" ELSE 0 END AS "revenue",
    o."deal_size", 'Outbound SDR' AS "program_category"
FROM sf_opportunities o;

-- HubSpot lifecycle transitions (conversation + MQL).
INSERT INTO conversions
SELECT
    h."event_time", c."account_id", c."contact_id",
    CASE h."lifecycle_to" WHEN 'mql' THEN 'mql' ELSE 'conversation' END AS "event_type",
    CAST(NULL AS VARCHAR) AS "opportunity_id", CAST(0 AS DOUBLE) AS "revenue",
    '' AS "deal_size", 'Email Nurture' AS "program_category"
FROM hubspot_events h
JOIN sf_contacts c ON h."email" = c."email"
WHERE h."event_type" = 'lifecycle_change'
  AND h."lifecycle_to" IN ('mql', 'sql', 'opportunity');
