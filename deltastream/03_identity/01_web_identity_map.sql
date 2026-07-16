-- Identity resolution, stage 1: build the anonymous -> account bridge as a
-- CHANGELOG keyed by web_user_id, so the touchpoints stream can look up an
-- account for previously-anonymous web traffic in a single temporal join.
--
-- A HubSpot form submission carries both the hutk web cookie (== the GA4
-- client_id on anonymous traffic) and the email; sf_contacts maps email ->
-- account. Resolving that in ONE object runs into two DeltaStream limits:
--   * a stream->changelog join yields a STREAM, so it can't directly back a
--     CHANGELOG; and
--   * doing the join under GROUP BY can't both project the join key (email, the
--     sf_contacts PK) AND keep web_user_id as the sole changelog key.
-- So it's split in two:
--   1. web_resolved (STREAM): the stream->changelog join, which as a stream sink
--      may project raw email and account — this is a normal enrichment.
--   2. web_identity_map (CHANGELOG): GROUP BY web_user_id over that stream (no
--      changelog join now), giving one current account per cookie.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

-- 1. Resolve each form submission to its account (stream-changelog enrichment).
CREATE STREAM "web_resolved" WITH (
    'topic' = 'rachel_web_resolved',
    'topic.partitions' = 1,
    'topic.replicas' = 1,
    'store' = 'demo_warpstream',
    'kafka.properties.request.timeout.ms' = '60000',
    'kafka.properties.delivery.timeout.ms' = '120000',
    'kafka.properties.linger.ms' = '100',
    'kafka.properties.batch.size' = '1048576',
    'value.format' = 'json',
    'timestamp' = 'event_time'
) AS
SELECT
    h."web_user_id"  AS "web_user_id",
    c."email"        AS "email",
    c."account_id"   AS "account_id",
    c."contact_id"   AS "contact_id",
    h."event_time"   AS "event_time"
FROM "hubspot_events" h
JOIN "sf_contacts" c ON h."email" = c."email"
WHERE h."event_type" = 'form_submission'
  AND h."web_user_id" IS NOT NULL;

-- 2. Collapse to one current account per web cookie (GROUP BY => changelog).
CREATE CHANGELOG "web_identity_map" WITH (
    'topic' = 'rachel_web_identity_map',
    'topic.partitions' = 1,
    'topic.replicas' = 1,
    'store' = 'demo_warpstream',
    'kafka.properties.request.timeout.ms' = '60000',
    'kafka.properties.delivery.timeout.ms' = '120000',
    'kafka.properties.linger.ms' = '100',
    'kafka.properties.batch.size' = '1048576',
    'value.format' = 'json',
    'key.columns' = 'web_user_id'
) AS
SELECT
    "web_user_id"       AS "web_user_id",
    MAX("account_id")   AS "account_id",
    MAX("contact_id")   AS "contact_id",
    MAX("email")        AS "email",
    MAX("event_time")   AS "resolved_at"
FROM "web_resolved"
GROUP BY "web_user_id";
