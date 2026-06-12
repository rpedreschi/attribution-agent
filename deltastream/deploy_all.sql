-- ==============================================================================
-- deploy_all.sql — GENERATED, every deltastream/ statement in deploy order.
--
-- Convenience bundle for testing: run this one file instead of opening each
-- folder. Regenerate with deltastream/build_deploy_all.sh after editing any
-- source file — do not hand-edit this file.
--
-- Prereqs: the demo_confluent store exists (default), datagen has published to
-- the src.* topics, and you run with a DDL-capable role. The repeated
-- USE DATABASE/SCHEMA headers are harmless.
-- ==============================================================================

-- ############################################################################
-- ## deltastream/00_stores.sql
-- ############################################################################

-- Environment bootstrap: the database/schema that every later object lives in.
--
-- The Kafka store already exists in this DeltaStream org as `demo_confluent`
-- (and is the default store), so there is NO CREATE STORE here. The stream and
-- changelog DDLs reference 'demo_confluent' directly in their WITH clauses.
--
-- NOTE: the attribution context is served from DeltaStream materialized views
-- over MCP (see 06_mcp/). DeltaStream uses ClickHouse internally to back MVs; we
-- do not manage it.

-- 1. The database (and its default `public` schema) that holds every stream,
--    changelog, and materialized view. Must match config.deltastream.database
--    / schema_name (defaults: attribution / public). Quoted lowercase so the
--    name is stored exactly as the config and MCP layer expect it.
CREATE DATABASE "attribution";

-- 2. Session context. DeltaStream creates unqualified objects in — and resolves
--    names against — the current database/schema, so set these at the start of
--    EVERY CLI or web-app session before running 01_streams/ onward (re-run if
--    you reconnect). This is what guarantees every object lands in
--    attribution.public. demo_confluent is already the default store, so no
--    USE STORE is required.
USE DATABASE "attribution";
USE SCHEMA "public";

-- ############################################################################
-- ## deltastream/01_streams/ga4_sessions.sql
-- ############################################################################

-- GA4 web sessions / page views / conversion events.
-- Shaped like the GA4 Measurement Protocol / BigQuery export event payload.
-- This is the anonymous-traffic stream that identity resolution later stitches
-- to known Salesforce contacts.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE STREAM "ga4_events" (
    "event_time"    TIMESTAMP,
    "user_id"       VARCHAR,          -- GA4 client_id (anonymous) or user_id when set
    "session_id"    VARCHAR,
    "event_name"    VARCHAR,          -- session_start, page_view, generate_lead, ...
    "page_location" VARCHAR,
    "device_type"   VARCHAR,
    "utm_source"    VARCHAR,
    "utm_medium"    VARCHAR,
    "utm_campaign"  VARCHAR,
    "utm_term"      VARCHAR,
    "utm_content"   VARCHAR
) WITH (
    'topic' = 'src.ga4.events',
    'store' = 'demo_confluent',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);

-- ############################################################################
-- ## deltastream/01_streams/hubspot_events.sql
-- ############################################################################

-- HubSpot MAP: form fills, email engagement, lifecycle stage transitions.
-- Shaped like HubSpot's webhook/event payload. Carries an email, which is the
-- join key into the Salesforce contacts changelog for identity resolution.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE STREAM "hubspot_events" (
    "event_time"      TIMESTAMP,
    "vid"             VARCHAR,        -- HubSpot contact id
    "web_user_id"     VARCHAR,        -- hutk cookie == GA4 client_id; the anonymous->known bridge
    "email"           VARCHAR,
    "event_type"      VARCHAR,        -- form_submission, email_open, email_click, lifecycle_change
    "lifecycle_from"  VARCHAR,
    "lifecycle_to"    VARCHAR,        -- subscriber, lead, mql, sql, opportunity, customer
    "form_name"       VARCHAR,
    "campaign"        VARCHAR,
    "utm_source"      VARCHAR,
    "utm_medium"      VARCHAR,
    "utm_campaign"    VARCHAR
) WITH (
    'topic' = 'src.hubspot.events',
    'store' = 'demo_confluent',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);

-- ############################################################################
-- ## deltastream/01_streams/outreach_activity.sql
-- ############################################################################

-- Outreach SDR activity: dials, conversations, sequence enrollment.
-- Carries the prospect email + (when known) the Salesforce contact id, so SDR
-- touches attach to the right account during identity resolution.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE STREAM "outreach_activity" (
    "event_time"   TIMESTAMP,
    "prospect_id"  VARCHAR,
    "email"        VARCHAR,
    "contact_id"   VARCHAR,           -- Salesforce contact id when synced
    "activity"     VARCHAR,           -- dial, conversation, sequence_enroll, reply
    "sequence"     VARCHAR,
    "sdr"          VARCHAR
) WITH (
    'topic' = 'src.outreach.activity',
    'store' = 'demo_confluent',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);

-- ############################################################################
-- ## deltastream/01_streams/ads_spend.sql
-- ############################################################################

-- LinkedIn Ads + Google Ads spend/performance.
-- Both platforms publish the same shape into their own topics; we define one
-- stream per platform and UNION them at the sink. Daily granularity rows.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE STREAM "linkedin_ads" (
    "spend_date"   VARCHAR,           -- yyyy-mm-dd
    "channel"      VARCHAR,           -- Paid Social
    "campaign"     VARCHAR,
    "spend_amount" DOUBLE,
    "impressions"  BIGINT,
    "clicks"       BIGINT
) WITH (
    'topic' = 'src.linkedin.ads',
    'store' = 'demo_confluent',
    'value.format' = 'json'
);

CREATE STREAM "google_ads" (
    "spend_date"   VARCHAR,
    "channel"      VARCHAR,           -- Paid Search
    "campaign"     VARCHAR,
    "spend_amount" DOUBLE,
    "impressions"  BIGINT,
    "clicks"       BIGINT
) WITH (
    'topic' = 'src.google.ads',
    'store' = 'demo_confluent',
    'value.format' = 'json'
);

-- ############################################################################
-- ## deltastream/02_changelogs/salesforce_cdc.sql
-- ############################################################################

-- Salesforce CDC changelogs.
-- CHANGELOG (not STREAM) because these are upsert-semantics dimension tables
-- keyed by id; identity resolution joins against the latest version of each row.
--
-- contacts: the identity spine. Maps email -> contact_id -> account_id, which
--           is how anonymous web/ad traffic gets attributed to an account.
-- accounts: the account dimension (available for enrichment / future MVs).
-- opportunities: stage transitions feed the conversions table.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE CHANGELOG "sf_contacts" (
    "contact_id" VARCHAR,
    "email"      VARCHAR,
    "account_id" VARCHAR,
    "first_name" VARCHAR,
    "last_name"  VARCHAR,
    "updated_at" TIMESTAMP,
    PRIMARY KEY ("contact_id")
) WITH (
    'topic' = 'src.salesforce.cdc.contacts',
    'store' = 'demo_confluent',
    'value.format' = 'json',
    'timestamp' = 'updated_at',
    'timestamp.format' = 'iso8601'
);

CREATE CHANGELOG "sf_accounts" (
    "account_id"     VARCHAR,
    "name"           VARCHAR,
    "industry"       VARCHAR,
    "employee_count" INTEGER,
    "arr_band"       VARCHAR,
    "region"         VARCHAR,
    "is_customer"    INTEGER,
    "updated_at"     TIMESTAMP,
    PRIMARY KEY ("account_id")
) WITH (
    'topic' = 'src.salesforce.cdc.accounts',
    'store' = 'demo_confluent',
    'value.format' = 'json',
    'timestamp' = 'updated_at',
    'timestamp.format' = 'iso8601'
);

CREATE CHANGELOG "sf_opportunities" (
    "opportunity_id" VARCHAR,
    "account_id"     VARCHAR,
    "stage_from"     VARCHAR,
    "stage_to"       VARCHAR,
    "amount"         DOUBLE,
    "deal_size"      VARCHAR,
    "event_time"     TIMESTAMP,
    PRIMARY KEY ("opportunity_id", "event_time")
) WITH (
    'topic' = 'src.salesforce.cdc.opportunities',
    'store' = 'demo_confluent',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);

-- ############################################################################
-- ## deltastream/03_identity/01_web_identity_map.sql
-- ############################################################################

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

CREATE CHANGELOG "web_identity_map" WITH (
    'topic' = 'attr_web_identity_map',
    'store' = 'demo_confluent',
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

-- ############################################################################
-- ## deltastream/03_identity/02_touchpoints.sql
-- ############################################################################

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

-- ############################################################################
-- ## deltastream/04_facts/01_conversions.sql
-- ############################################################################

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
    "event_type"       VARCHAR,    -- conversation | mql | sql | opp_created | closed_won | closed_lost
    "opportunity_id"   VARCHAR,
    "revenue"          DOUBLE,
    "deal_size"        VARCHAR,
    "program_category" VARCHAR
) WITH (
    'topic' = 'attr_conversions',
    'store' = 'demo_confluent',
    'value.format' = 'json',
    'timestamp' = 'event_time'
);

-- Salesforce opportunity transitions.
INSERT INTO "conversions"
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
FROM "sf_opportunities" o;

-- HubSpot lifecycle transitions (conversation + MQL).
INSERT INTO "conversions"
SELECT
    h."event_time", c."account_id", c."contact_id",
    CASE h."lifecycle_to" WHEN 'mql' THEN 'mql' ELSE 'conversation' END AS "event_type",
    CAST(NULL AS VARCHAR) AS "opportunity_id", CAST(0 AS DOUBLE) AS "revenue",
    '' AS "deal_size", 'Email Nurture' AS "program_category"
FROM "hubspot_events" h
JOIN "sf_contacts" c ON h."email" = c."email"
WHERE h."event_type" = 'lifecycle_change'
  AND h."lifecycle_to" IN ('mql', 'sql', 'opportunity');

-- ############################################################################
-- ## deltastream/04_facts/02_spend.sql
-- ############################################################################

-- Unified `spend` stream: LinkedIn + Google Ads daily spend. Non-ad channel
-- cost (Outbound SDR loaded cost, Events, Brand) is published to its own Kafka
-- topic by finance/manual export and unioned in here in production; for the
-- demo the two ad platforms are the live spend sources.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE STREAM "spend" (
    "spend_date"       VARCHAR,
    "channel"          VARCHAR,
    "program_category" VARCHAR,
    "campaign"         VARCHAR,
    "spend_amount"     DOUBLE,
    "source_platform"  VARCHAR
) WITH (
    'topic' = 'attr_spend',
    'store' = 'demo_confluent',
    'value.format' = 'json'
);

INSERT INTO "spend"
SELECT "spend_date", "channel", "channel" AS "program_category", "campaign",
       "spend_amount", 'linkedin' AS "source_platform"
FROM "linkedin_ads";

INSERT INTO "spend"
SELECT "spend_date", "channel", "channel" AS "program_category", "campaign",
       "spend_amount", 'google_ads' AS "source_platform"
FROM "google_ads";

-- ############################################################################
-- ## deltastream/04_facts/03_funnel_events.sql
-- ############################################################################

-- `funnel_events`: touches + conversion stages normalized to (program_category,
-- stage) rows so the funnel materialized view is a single GROUP BY. Touches come
-- from the touchpoints stream; the other stages from the conversions stream.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE STREAM "funnel_events" (
    "event_time"       TIMESTAMP,
    "program_category" VARCHAR,
    "stage"            VARCHAR
) WITH (
    'topic' = 'attr_funnel_events',
    'store' = 'demo_confluent',
    'value.format' = 'json',
    'timestamp' = 'event_time'
);

INSERT INTO "funnel_events"
SELECT "event_time", "program_category", 'touch' AS "stage"
FROM "touchpoints";

INSERT INTO "funnel_events"
SELECT "event_time", "program_category", "event_type" AS "stage"
FROM "conversions"
WHERE "event_type" IN ('conversation', 'mql', 'sql', 'opp_created', 'closed_won');

-- ############################################################################
-- ## deltastream/05_views/01_mv_spend_by_channel.sql
-- ############################################################################

-- mv_spend_by_channel: trailing spend per channel. Exposed over MCP as the
-- denominator for the agent's CAC and ROI math.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_spend_by_channel" AS
SELECT
    "channel",
    "program_category",
    SUM("spend_amount") AS "spend"
FROM "spend"
GROUP BY "channel", "program_category";

-- ############################################################################
-- ## deltastream/05_views/02_mv_funnel_by_category.sql
-- ############################################################################

-- mv_funnel_by_category: the B2B funnel counts per program category, in one
-- pivoted row each. touch -> conversation -> MQL -> SQL -> opp -> won.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_funnel_by_category" AS
SELECT
    "program_category",
    COUNT(CASE WHEN "stage" = 'touch'        THEN 1 END) AS "touches",
    COUNT(CASE WHEN "stage" = 'conversation' THEN 1 END) AS "conversations",
    COUNT(CASE WHEN "stage" = 'mql'          THEN 1 END) AS "mqls",
    COUNT(CASE WHEN "stage" = 'sql'          THEN 1 END) AS "sqls",
    COUNT(CASE WHEN "stage" = 'opp_created'  THEN 1 END) AS "opps",
    COUNT(CASE WHEN "stage" = 'closed_won'   THEN 1 END) AS "won"
FROM "funnel_events"
GROUP BY "program_category";

-- ############################################################################
-- ## deltastream/05_views/03_mv_channel_touch_distribution.sql
-- ############################################################################

-- mv_channel_touch_distribution: per resolved account, the touch count and most
-- recent touch time on each channel. This is the attribution *context* the agent
-- needs: joined to mv_won_revenue_by_account it lets the agent compute all three
-- models (last touch = channel with the latest touch; linear = touch-count
-- share; time decay = recency-weighted from last_touch_time vs close_time).
--
-- Full per-touch journey reconstruction with normalized window functions is
-- impractical in streaming SQL, so the heavy arithmetic is deliberately pushed
-- to the agent — DeltaStream serves the live aggregated state.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_channel_touch_distribution" AS
SELECT
    "account_id",
    "channel",
    "program_category",
    COUNT(*)          AS "touch_count",
    MAX("event_time") AS "last_touch_time"
FROM "touchpoints"
WHERE "account_id" IS NOT NULL
GROUP BY "account_id", "channel", "program_category";

-- ############################################################################
-- ## deltastream/05_views/04_mv_won_revenue_by_account.sql
-- ############################################################################

-- mv_won_revenue_by_account: closed-won revenue and close time per account.
-- The numerator the agent distributes across channels using the touch
-- distribution. Summed across accounts it is the total attributed revenue.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_won_revenue_by_account" AS
SELECT
    "account_id",
    SUM("revenue")    AS "revenue",
    MAX("event_time") AS "close_time"
FROM "conversions"
WHERE "event_type" = 'closed_won'
GROUP BY "account_id";

-- ############################################################################
-- ## deltastream/06_mcp/01_expose_over_mcp.sql
-- ############################################################################

-- Expose the materialized views over DeltaStream's MCP endpoint.
--
-- DeltaStream auto-exposes any materialized view the API token's role can
-- SELECT as an MCP tool the agent discovers and calls. So exposure == RBAC:
-- create a least-privilege reader role, grant it SELECT on exactly the four
-- context MVs, and mint an API token bound to that role.
--
-- The agent then POSTs JSON-RPC to the MCP endpoint with
-- `Authorization: Bearer <token>` (see src/attribution_agent/agent/
-- deltastream_mcp.py and config.deltastream). Adjust the database/schema names
-- if you did not create the MVs in attribution.public.

USE ROLE orgadmin;

-- Context for consistency; the grants below are fully qualified regardless.
USE DATABASE "attribution";
USE SCHEMA "public";

-- 1. Least-privilege role.
CREATE ROLE "attribution_reader";
GRANT USAGE ON DATABASE "attribution" TO ROLE "attribution_reader";
GRANT USAGE ON SCHEMA "attribution"."public" TO ROLE "attribution_reader";

-- 2. Grant SELECT on only the exposed MVs (fully qualified). Each becomes a tool.
GRANT SELECT ON "attribution"."public"."mv_spend_by_channel"           TO ROLE "attribution_reader";
GRANT SELECT ON "attribution"."public"."mv_funnel_by_category"         TO ROLE "attribution_reader";
GRANT SELECT ON "attribution"."public"."mv_channel_touch_distribution" TO ROLE "attribution_reader";
GRANT SELECT ON "attribution"."public"."mv_won_revenue_by_account"     TO ROLE "attribution_reader";

-- 3. Mint the API token bound to the role. Copy the returned token into
--    config.deltastream.api_token (or the DELTASTREAM_API_TOKEN env var).
--    Brand/Events spend rows still live in mv_spend_by_channel, but the agent's
--    own guardrails (not RBAC) exclude them from autonomy.
CREATE API_TOKEN "attribution_agent_token" WITH ('token.role_name' = "attribution_reader");

-- Verify the exposed tools (shell):
--   curl -X POST "$DELTASTREAM_MCP_ENDPOINT" \
--     -H "Content-Type: application/json" \
--     -H "Accept: application/json,text/event-stream" \
--     -H "Authorization: Bearer $DELTASTREAM_API_TOKEN" \
--     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
-- ...or simply: python -m attribution_agent.agent.cli doctor
