USE DATABASE "attribution";
USE SCHEMA "public";


USE DATABASE "attribution";
USE SCHEMA "public";

CREATE STREAM "ga4_events" (
    "event_time"    TIMESTAMP,
    "user_id"       VARCHAR,
    "session_id"    VARCHAR,
    "event_name"    VARCHAR,
    "page_location" VARCHAR,
    "device_type"   VARCHAR,
    "utm_source"    VARCHAR,
    "utm_medium"    VARCHAR,
    "utm_campaign"  VARCHAR,
    "utm_term"      VARCHAR,
    "utm_content"   VARCHAR
) WITH (
    'topic' = 'rachel_ga4_events',
    'store' = 'demo_warpstream',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);


USE DATABASE "attribution";
USE SCHEMA "public";

CREATE STREAM "hubspot_events" (
    "event_time"      TIMESTAMP,
    "vid"             VARCHAR,
    "web_user_id"     VARCHAR,
    "email"           VARCHAR,
    "event_type"      VARCHAR,
    "lifecycle_from"  VARCHAR,
    "lifecycle_to"    VARCHAR,
    "form_name"       VARCHAR,
    "campaign"        VARCHAR,
    "utm_source"      VARCHAR,
    "utm_medium"      VARCHAR,
    "utm_campaign"    VARCHAR,
    "program_category" VARCHAR
) WITH (
    'topic' = 'rachel_hubspot_events',
    'store' = 'demo_warpstream',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);


USE DATABASE "attribution";
USE SCHEMA "public";

CREATE STREAM "outreach_activity" (
    "event_time"   TIMESTAMP,
    "prospect_id"  VARCHAR,
    "email"        VARCHAR,
    "contact_id"   VARCHAR,
    "activity"     VARCHAR,
    "sequence"     VARCHAR,
    "sdr"          VARCHAR
) WITH (
    'topic' = 'rachel_outreach_activity',
    'store' = 'demo_warpstream',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);


USE DATABASE "attribution";
USE SCHEMA "public";

CREATE STREAM "linkedin_ads" (
    "spend_date"   VARCHAR,
    "channel"      VARCHAR,
    "campaign"     VARCHAR,
    "spend_amount" DOUBLE,
    "impressions"  BIGINT,
    "clicks"       BIGINT,
    "event_time"   TIMESTAMP
) WITH (
    'topic' = 'rachel_linkedin_ads',
    'store' = 'demo_warpstream',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);

CREATE STREAM "google_ads" (
    "spend_date"   VARCHAR,
    "channel"      VARCHAR,
    "campaign"     VARCHAR,
    "spend_amount" DOUBLE,
    "impressions"  BIGINT,
    "clicks"       BIGINT,
    "event_time"   TIMESTAMP
) WITH (
    'topic' = 'rachel_google_ads',
    'store' = 'demo_warpstream',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);


USE DATABASE "attribution";
USE SCHEMA "public";

CREATE STREAM "share_of_model" (
    "event_time"     TIMESTAMP,
    "buyer_query"    VARCHAR,
    "assistant"      VARCHAR,
    "mentioned"      INTEGER,
    "cited"          INTEGER,
    "brand_rank"     INTEGER,
    "top_competitor" VARCHAR,
    "sentiment"      VARCHAR
) WITH (
    'topic' = 'rachel_share_of_model',
    'topic.partitions' = 1,
    'topic.replicas' = 3,
    'store' = 'demo_warpstream',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);


USE DATABASE "attribution";
USE SCHEMA "public";

CREATE CHANGELOG "sf_contacts" (
    "contact_id" VARCHAR,
    "email"      VARCHAR,
    "account_id" VARCHAR,
    "first_name" VARCHAR,
    "last_name"  VARCHAR,
    "updated_at" TIMESTAMP,
    PRIMARY KEY ("email")
) WITH (
    'topic' = 'rachel_salesforce_cdc_contacts',
    'store' = 'demo_warpstream',
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
    'topic' = 'rachel_salesforce_cdc_accounts',
    'store' = 'demo_warpstream',
    'value.format' = 'json',
    'timestamp' = 'updated_at',
    'timestamp.format' = 'iso8601'
);

CREATE STREAM "sf_opportunities" (
    "opportunity_id" VARCHAR,
    "account_id"     VARCHAR,
    "stage_from"     VARCHAR,
    "stage_to"       VARCHAR,
    "amount"         DOUBLE,
    "deal_size"      VARCHAR,
    "event_time"     TIMESTAMP,
    "program_category" VARCHAR
) WITH (
    'topic' = 'rachel_salesforce_cdc_opportunities',
    'store' = 'demo_warpstream',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);


USE DATABASE "attribution";
USE SCHEMA "public";

CREATE STREAM "web_resolved" WITH (
    'topic' = 'rachel_web_resolved',
    'topic.partitions' = 1,
    'topic.replicas' = 3,
    'store' = 'demo_warpstream',
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

CREATE CHANGELOG "web_identity_map" WITH (
    'topic' = 'rachel_web_identity_map',
    'topic.partitions' = 1,
    'topic.replicas' = 3,
    'store' = 'demo_warpstream',
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
    'topic.replicas' = 3,
    'store' = 'demo_warpstream',
    'value.format' = 'json',
    'timestamp' = 'event_time'
);

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

INSERT INTO "touchpoints"
SELECT
    o."event_time", o."contact_id" AS "user_id", CAST(NULL AS VARCHAR) AS "web_user_id",
    c."account_id", o."contact_id",
    c."email" AS "email", o."prospect_id" AS "session_id", 'Outbound SDR' AS "channel",
    'Outbound SDR' AS "program_category", o."sequence" AS "campaign",
    'outreach' AS "source", 'outreach' AS "source_system"
FROM "outreach_activity" o
JOIN "sf_contacts" c ON o."email" = c."email";

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


USE DATABASE "attribution";
USE SCHEMA "public";

CREATE STREAM "conversions" (
    "event_time"       TIMESTAMP,
    "account_id"       VARCHAR,
    "contact_id"       VARCHAR,
    "email"            VARCHAR,
    "event_type"       VARCHAR,
    "opportunity_id"   VARCHAR,
    "revenue"          DOUBLE,
    "deal_size"        VARCHAR,
    "program_category" VARCHAR
) WITH (
    'topic' = 'rachel_conversions',
    'topic.partitions' = 1,
    'topic.replicas' = 3,
    'store' = 'demo_warpstream',
    'value.format' = 'json',
    'timestamp' = 'event_time'
);

INSERT INTO "conversions"
SELECT
    o."event_time", o."account_id", CAST(NULL AS VARCHAR) AS "contact_id",
    CAST(NULL AS VARCHAR) AS "email",
    CAST(CASE o."stage_to"
        WHEN 'ClosedWon'  THEN 'closed_won'
        WHEN 'ClosedLost' THEN 'closed_lost'
        WHEN 'SQL'        THEN 'sql'
        ELSE 'opp_created'
    END AS VARCHAR) AS "event_type",
    o."opportunity_id",
    CAST(CASE WHEN o."stage_to" = 'ClosedWon' THEN o."amount" ELSE 0 END AS DOUBLE) AS "revenue",
    o."deal_size", o."program_category"
FROM "sf_opportunities" o;

INSERT INTO "conversions"
SELECT
    h."event_time", c."account_id", c."contact_id",
    c."email" AS "email",
    CAST(CASE h."lifecycle_to" WHEN 'mql' THEN 'mql' ELSE 'conversation' END AS VARCHAR) AS "event_type",
    CAST(NULL AS VARCHAR) AS "opportunity_id", CAST(0 AS DOUBLE) AS "revenue",
    '' AS "deal_size", h."program_category"
FROM "hubspot_events" h
JOIN "sf_contacts" c ON h."email" = c."email"
WHERE h."event_type" = 'lifecycle_change'
  AND h."lifecycle_to" IN ('mql', 'sql', 'opportunity');


USE DATABASE "attribution";
USE SCHEMA "public";

CREATE STREAM "spend" (
    "spend_date"       VARCHAR,
    "channel"          VARCHAR,
    "program_category" VARCHAR,
    "campaign"         VARCHAR,
    "spend_amount"     DOUBLE,
    "source_platform"  VARCHAR,
    "event_time"       TIMESTAMP
) WITH (
    'topic' = 'rachel_spend',
    'topic.partitions' = 1,
    'topic.replicas' = 3,
    'store' = 'demo_warpstream',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);

CREATE STREAM "channel_cost" (
    "spend_date"   VARCHAR,
    "channel"      VARCHAR,
    "spend_amount" DOUBLE,
    "event_time"   TIMESTAMP
) WITH (
    'topic' = 'rachel_channel_cost',
    'topic.partitions' = 1,
    'topic.replicas' = 3,
    'store' = 'demo_warpstream',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);

INSERT INTO "spend"
SELECT "spend_date", "channel", "channel" AS "program_category", "campaign",
       "spend_amount", 'linkedin' AS "source_platform", "event_time"
FROM "linkedin_ads";

INSERT INTO "spend"
SELECT "spend_date", "channel", "channel" AS "program_category", "campaign",
       "spend_amount", 'google_ads' AS "source_platform", "event_time"
FROM "google_ads";

INSERT INTO "spend"
SELECT "spend_date", "channel", "channel" AS "program_category",
       '' AS "campaign", "spend_amount", 'finance' AS "source_platform", "event_time"
FROM "channel_cost";


USE DATABASE "attribution";
USE SCHEMA "public";

CREATE STREAM "funnel_events" (
    "event_time"       TIMESTAMP,
    "program_category" VARCHAR,
    "stage"            VARCHAR
) WITH (
    'topic' = 'rachel_funnel_events',
    'topic.partitions' = 1,
    'topic.replicas' = 3,
    'store' = 'demo_warpstream',
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


USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_spend_by_channel" AS
SELECT
    "channel",
    "program_category",
    SUM("spend_amount") AS "spend"
FROM "spend"
GROUP BY "channel", "program_category";


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


USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_share_of_model" AS
SELECT
    "buyer_query",
    COUNT(*)                              AS "probes",
    SUM("mentioned")                      AS "mentions",
    SUM("cited")                          AS "citations",
    MIN("brand_rank")                     AS "best_rank",
    AVG(CAST("brand_rank" AS DOUBLE))     AS "avg_rank",
    MAX("event_time")                     AS "last_checked"
FROM "share_of_model"
GROUP BY "buyer_query";


USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_revenue_timeline" AS
SELECT
    FLOOR("event_time" TO MINUTE) AS "bucket",
    SUM("revenue")                AS "revenue",
    COUNT(*)                      AS "deals"
FROM "conversions"
WHERE "event_type" = 'closed_won'
GROUP BY FLOOR("event_time" TO MINUTE);


USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_touch_timeline" AS
SELECT
    "channel",
    FLOOR("event_time" TO MINUTE) AS "bucket",
    COUNT(*)                      AS "touches"
FROM "touchpoints"
WHERE "account_id" IS NOT NULL
GROUP BY "channel", FLOOR("event_time" TO MINUTE);


USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_som_timeline" AS
SELECT
    "buyer_query",
    FLOOR("event_time" TO MINUTE) AS "bucket",
    COUNT(*)                      AS "probes",
    SUM("mentioned")              AS "mentions"
FROM "share_of_model"
GROUP BY "buyer_query", FLOOR("event_time" TO MINUTE);


USE DATABASE "attribution";
USE SCHEMA "public";

CREATE MATERIALIZED VIEW "mv_spend_timeline" AS
SELECT
    "channel",
    FLOOR("event_time" TO MINUTE) AS "bucket",
    SUM("spend_amount")           AS "spend"
FROM "spend"
GROUP BY "channel", FLOOR("event_time" TO MINUTE);
