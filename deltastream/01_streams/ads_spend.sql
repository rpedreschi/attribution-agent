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
    "clicks"       BIGINT,
    "event_time"   TIMESTAMP          -- wall-clock of the spend row (for spend timeline)
) WITH (
    'topic' = 'attr_linkedin_ads',
    'store' = 'demo_confluent',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);

CREATE STREAM "google_ads" (
    "spend_date"   VARCHAR,
    "channel"      VARCHAR,           -- Paid Search
    "campaign"     VARCHAR,
    "spend_amount" DOUBLE,
    "impressions"  BIGINT,
    "clicks"       BIGINT,
    "event_time"   TIMESTAMP
) WITH (
    'topic' = 'attr_google_ads',
    'store' = 'demo_confluent',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);
