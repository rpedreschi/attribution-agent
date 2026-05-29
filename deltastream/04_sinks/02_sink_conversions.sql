-- Sink funnel-stage transitions into ClickHouse attribution.conversions.
--
-- Two sources of funnel events:
--   * Salesforce opportunity stage changes  -> sql / opp_created / closed_won / closed_lost
--   * HubSpot lifecycle changes              -> conversation / mql
-- Both normalized to the conversions shape. Joins only; no aggregation.

-- Salesforce opportunity transitions.
INSERT INTO clickhouse_sink."attribution"."conversions"
SELECT
    o."event_time"                                   AS "event_time",
    ''                                               AS "user_id",
    o."account_id"                                   AS "account_id",
    CAST(NULL AS VARCHAR)                            AS "contact_id",
    CASE o."stage_to"
        WHEN 'ClosedWon'  THEN 'closed_won'
        WHEN 'ClosedLost' THEN 'closed_lost'
        WHEN 'SQL'        THEN 'sql'
        ELSE 'opp_created'
    END                                              AS "event_type",
    o."opportunity_id"                               AS "opportunity_id",
    o."stage_from"                                   AS "stage_from",
    o."stage_to"                                     AS "stage_to",
    CASE WHEN o."stage_to" = 'ClosedWon' THEN o."amount" ELSE 0 END AS "revenue",
    o."deal_size"                                    AS "deal_size",
    'Outbound SDR'                                   AS "program_category",
    'salesforce'                                     AS "source_system"
FROM sf_opportunities o;

-- HubSpot lifecycle transitions (conversation + MQL).
INSERT INTO clickhouse_sink."attribution"."conversions"
SELECT
    h."event_time"                                   AS "event_time",
    h."vid"                                          AS "user_id",
    c."account_id"                                   AS "account_id",
    c."contact_id"                                   AS "contact_id",
    CASE h."lifecycle_to"
        WHEN 'mql' THEN 'mql'
        ELSE 'conversation'
    END                                              AS "event_type",
    CAST(NULL AS VARCHAR)                            AS "opportunity_id",
    h."lifecycle_from"                               AS "stage_from",
    h."lifecycle_to"                                 AS "stage_to",
    0                                                AS "revenue",
    ''                                               AS "deal_size",
    'Email Nurture'                                  AS "program_category",
    'hubspot'                                        AS "source_system"
FROM hubspot_events h
JOIN sf_contacts c
    ON h."email" = c."email"
WHERE h."event_type" = 'lifecycle_change'
  AND h."lifecycle_to" IN ('mql', 'sql', 'opportunity');
