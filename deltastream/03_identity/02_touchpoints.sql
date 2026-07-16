-- Identity resolution, stage 2: one unified `touchpoints` stream that all
-- touch-producing sources feed, with account_id/contact_id attached.
--
-- GA4 web traffic temporal-joins web_identity_map on user_id (NULL while still
-- anonymous). Outreach and HubSpot touches resolve through sf_contacts on email.
-- The three INSERT INTO statements run as continuous queries into the same
-- backing topic, so the materialized views in 05_views read a single stream.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE STREAM "touchpoints" (
    "event_time"       TIMESTAMP,
    "user_id"          VARCHAR,
    "web_user_id"      VARCHAR,
    "account_id"       VARCHAR,
    "contact_id"       VARCHAR,
    "email"            VARCHAR,
    "session_id"       VARCHAR,
    "channel"          VARCHAR,
    "program_category" VARCHAR,
    "campaign"         VARCHAR,
    "source"           VARCHAR,
    "source_system"    VARCHAR
) WITH (
    'topic' = 'rachel_touchpoints',
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

-- Resolved web touches. GA4 carries paid + organic traffic, so derive the
-- channel from utm_medium (cpc -> Paid Search, paid-social -> Paid Social,
-- brand -> Brand) rather than labelling everything Organic/Web — otherwise the
-- paid channels get spend but no attributed revenue.
INSERT INTO "touchpoints"
SELECT
    g."event_time", g."user_id", m."web_user_id" AS "web_user_id",
    m."account_id", m."contact_id",
    m."email" AS "email", g."session_id",
    CAST(CASE g."utm_medium"
        WHEN 'cpc'          THEN 'Paid Search'
        WHEN 'paid-social'  THEN 'Paid Social'
        WHEN 'brand'        THEN 'Brand'
        WHEN 'ai-referral'  THEN 'AI Assistant'
        ELSE 'Organic/Web'
    END AS VARCHAR) AS "channel",
    CAST(CASE g."utm_medium"
        WHEN 'cpc'          THEN 'Paid Search'
        WHEN 'paid-social'  THEN 'Paid Social'
        WHEN 'brand'        THEN 'Brand'
        WHEN 'ai-referral'  THEN 'AI Assistant'
        ELSE 'Organic/Web'
    END AS VARCHAR) AS "program_category",
    g."utm_campaign" AS "campaign", 'ga4' AS "source", 'ga4' AS "source_system"
FROM "ga4_events" g
LEFT JOIN "web_identity_map" m ON g."user_id" = m."web_user_id";

-- Outbound SDR touches (already keyed to a Salesforce contact).
INSERT INTO "touchpoints"
SELECT
    o."event_time", o."contact_id" AS "user_id", CAST(NULL AS VARCHAR) AS "web_user_id",
    c."account_id", o."contact_id",
    c."email" AS "email", o."prospect_id" AS "session_id", 'Outbound SDR' AS "channel",
    'Outbound SDR' AS "program_category", o."sequence" AS "campaign",
    'outreach' AS "source", 'outreach' AS "source_system"
FROM "outreach_activity" o
JOIN "sf_contacts" c ON o."email" = c."email";

-- Email-nurture engagement touches.
INSERT INTO "touchpoints"
SELECT
    h."event_time", h."vid" AS "user_id", CAST(NULL AS VARCHAR) AS "web_user_id",
    c."account_id", c."contact_id",
    c."email" AS "email", h."vid" AS "session_id", 'Email Nurture' AS "channel",
    'Email Nurture' AS "program_category", h."campaign" AS "campaign",
    'hubspot' AS "source", 'hubspot' AS "source_system"
FROM "hubspot_events" h
JOIN "sf_contacts" c ON h."email" = c."email"
WHERE h."event_type" IN ('email_open', 'email_click');
