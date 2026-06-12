-- Identity resolution, stage 1: build the anonymous -> account bridge.
--
-- A HubSpot form submission carries both the hutk web cookie (== the GA4
-- client_id we see on anonymous traffic) and the email. Joining that email to
-- the Salesforce contacts changelog yields a mapping:
--     web_user_id  ->  contact_id  ->  account_id
-- materialized as a CHANGELOG so downstream stream-to-table temporal joins can
-- look up an account for previously-anonymous web traffic.
--
-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

-- Built with CREATE CHANGELOG AS SELECT, keyed by web_user_id (the downstream
-- touchpoints stream temporal-joins this changelog on web_user_id).
--
-- A stream->changelog join (hubspot_events JOIN sf_contacts) yields a STREAM, so
-- it cannot directly back a CHANGELOG. Aggregating GROUP BY web_user_id gives the
-- query upsert/changelog semantics: one current row per web cookie holding the
-- resolved contact/account. MAX() collapses the (effectively single) matching
-- contact per cookie. The 'key.columns' sink property names the key, matching the
-- GROUP BY.
CREATE CHANGELOG "web_identity_map" WITH (
    'topic' = 'attr_web_identity_map',
    'topic.partitions' = 1,
    'topic.replicas' = 3,
    'store' = 'demo_confluent',
    'value.format' = 'json',
    'key.columns' = 'web_user_id'
) AS
SELECT
    h."web_user_id"       AS "web_user_id",
    MAX(c."contact_id")   AS "contact_id",
    MAX(c."account_id")   AS "account_id",
    MAX(c."email")        AS "email",
    MAX(h."event_time")   AS "resolved_at"
FROM "hubspot_events" h
JOIN "sf_contacts" c
    ON h."email" = c."email"
WHERE h."event_type" = 'form_submission'
  AND h."web_user_id" IS NOT NULL
GROUP BY h."web_user_id";
