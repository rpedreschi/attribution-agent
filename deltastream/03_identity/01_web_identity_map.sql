-- Identity resolution, stage 1: build the anonymous -> account bridge.
--
-- A HubSpot form submission carries both the hutk web cookie (== the GA4
-- client_id we see on anonymous traffic) and the email. Joining that email to
-- the Salesforce contacts changelog yields a mapping:
--     web_user_id  ->  contact_id  ->  account_id
-- materialized as a CHANGELOG so downstream stream-to-table temporal joins can
-- look up an account for previously-anonymous web traffic.
--
-- Join only — no aggregation (per conventions). Chained through this
-- intermediate object rather than folded into the GA4 enrichment statement.

CREATE CHANGELOG "web_identity_map" WITH (
    'topic' = 'attr_web_identity_map',
    'store' = 'confluent_cloud',
    'value.format' = 'json'
) AS
SELECT
    h."web_user_id"          AS "web_user_id",
    c."contact_id"           AS "contact_id",
    c."account_id"           AS "account_id",
    h."event_time"           AS "resolved_at"
FROM "hubspot_events" h
JOIN "sf_contacts" c
    ON h."email" = c."email"
WHERE h."event_type" = 'form_submission'
  AND h."web_user_id" IS NOT NULL;
