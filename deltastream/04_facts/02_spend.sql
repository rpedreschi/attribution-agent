-- Unified `spend` stream: LinkedIn + Google Ads daily spend (rich impressions/
-- clicks rows) UNION the finance/manual loaded-cost export (channel_cost) for the
-- non-ad channels (Outbound SDR, Email Nurture, Events, Brand, Organic/Web). With
-- all three feeds, every channel has spend so the agent computes CAC/ROI across
-- the whole mix, not just the two ad platforms.

-- Ensure objects land in attribution.public even if run in a fresh session.
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
    'topic.replicas' = 1,
    'store' = 'demo_warpstream',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);

-- The finance loaded-cost feed (non-ad channels). Carries topic.partitions/
-- replicas because rachel_channel_cost is new — DeltaStream creates it here rather
-- than waiting on the datagen to publish it first.
CREATE STREAM "channel_cost" (
    "spend_date"   VARCHAR,
    "channel"      VARCHAR,
    "spend_amount" DOUBLE,
    "event_time"   TIMESTAMP
) WITH (
    'topic' = 'rachel_channel_cost',
    'topic.partitions' = 1,
    'topic.replicas' = 1,
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
