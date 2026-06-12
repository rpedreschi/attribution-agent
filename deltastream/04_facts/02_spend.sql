-- Unified `spend` stream: LinkedIn + Google Ads daily spend. Non-ad channel
-- cost (Outbound SDR loaded cost, Events, Brand) is published to its own Kafka
-- topic by finance/manual export and unioned in here in production; for the
-- demo the two ad platforms are the live spend sources.

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
