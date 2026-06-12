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

-- Built with CREATE CHANGELOG AS SELECT, keyed by web_user_id: a current
-- web_user_id -> email row per web cookie. The account is NOT resolved here —
-- touchpoints joins sf_contacts on this email to get the account.
--
-- Why no sf_contacts join here: a stream->changelog join yields a STREAM (can't
-- back a CHANGELOG), and the alternative — GROUP BY with the sf_contacts join —
-- can't both satisfy "the joined changelog's key (email) must be projected" and
-- keep web_user_id as the sole key. So this stage is hubspot-only: GROUP BY
-- web_user_id gives changelog/upsert semantics, MAX() collapses the (single)
-- form email per cookie, and 'key.columns' names the key.
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
    MAX(h."email")        AS "email",
    MAX(h."event_time")   AS "resolved_at"
FROM "hubspot_events" h
WHERE h."event_type" = 'form_submission'
  AND h."web_user_id" IS NOT NULL
GROUP BY h."web_user_id";
