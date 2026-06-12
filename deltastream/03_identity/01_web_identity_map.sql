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

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

-- Declared with an explicit PRIMARY KEY ("web_user_id"): downstream, the
-- touchpoints stream temporal-joins this changelog on web_user_id, and
-- DeltaStream requires that join to reference the changelog's primary key.
CREATE CHANGELOG "web_identity_map" (
    "web_user_id" VARCHAR,
    "contact_id"  VARCHAR,
    "account_id"  VARCHAR,
    "resolved_at" TIMESTAMP,
    PRIMARY KEY ("web_user_id")
) WITH (
    'topic' = 'attr_web_identity_map',
    'store' = 'demo_confluent',
    'value.format' = 'json',
    'timestamp' = 'resolved_at'
);

INSERT INTO "web_identity_map"
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
