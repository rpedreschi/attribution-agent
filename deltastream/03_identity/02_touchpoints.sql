-- Identity resolution, stage 2: one unified `touchpoints` stream that all
-- touch-producing sources feed, with account_id/contact_id attached.
--
-- GA4 web traffic temporal-joins web_identity_map on user_id (NULL while still
-- anonymous). Outreach and HubSpot touches resolve through sf_contacts on email.
-- The three INSERT INTO statements run as continuous queries into the same
-- backing topic, so the materialized views in 05_views read a single stream.

CREATE STREAM "touchpoints" (
    "event_time"       TIMESTAMP,
    "user_id"          VARCHAR,
    "account_id"       VARCHAR,
    "contact_id"       VARCHAR,
    "session_id"       VARCHAR,
    "channel"          VARCHAR,
    "program_category" VARCHAR,
    "campaign"         VARCHAR,
    "source"           VARCHAR,
    "source_system"    VARCHAR
) WITH (
    'topic' = 'attr_touchpoints',
    'store' = 'demo_confluent',
    'value.format' = 'json',
    'timestamp' = 'event_time'
);

-- Resolved web touches.
INSERT INTO "touchpoints"
SELECT
    g."event_time", g."user_id", m."account_id", m."contact_id", g."session_id",
    'Organic/Web' AS "channel", 'Organic/Web' AS "program_category",
    g."utm_campaign" AS "campaign", 'ga4' AS "source", 'ga4' AS "source_system"
FROM "ga4_events" g
LEFT JOIN "web_identity_map" m ON g."user_id" = m."web_user_id";

-- Outbound SDR touches (already keyed to a Salesforce contact).
INSERT INTO "touchpoints"
SELECT
    o."event_time", o."contact_id" AS "user_id", c."account_id", o."contact_id",
    o."prospect_id" AS "session_id", 'Outbound SDR' AS "channel",
    'Outbound SDR' AS "program_category", o."sequence" AS "campaign",
    'outreach' AS "source", 'outreach' AS "source_system"
FROM "outreach_activity" o
JOIN "sf_contacts" c ON o."email" = c."email";

-- Email-nurture engagement touches.
INSERT INTO "touchpoints"
SELECT
    h."event_time", h."vid" AS "user_id", c."account_id", c."contact_id",
    h."vid" AS "session_id", 'Email Nurture' AS "channel",
    'Email Nurture' AS "program_category", h."campaign" AS "campaign",
    'hubspot' AS "source", 'hubspot' AS "source_system"
FROM "hubspot_events" h
JOIN "sf_contacts" c ON h."email" = c."email"
WHERE h."event_type" IN ('email_open', 'email_click');
