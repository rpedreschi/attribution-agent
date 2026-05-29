-- Sink LinkedIn Ads + Google Ads spend into ClickHouse attribution.campaign_spend.
-- Non-ad channel cost (Outbound SDR loaded cost, Events, Brand) is loaded
-- directly into ClickHouse by the mock generator / finance export — it does not
-- flow through an ad-platform Kafka topic.

INSERT INTO clickhouse_sink."attribution"."campaign_spend"
SELECT
    CAST("spend_date" AS DATE)   AS "spend_date",
    "channel",
    "channel"                    AS "program_category",
    "campaign",
    "spend_amount",
    "impressions",
    "clicks",
    'linkedin'                   AS "source_platform"
FROM linkedin_ads;

INSERT INTO clickhouse_sink."attribution"."campaign_spend"
SELECT
    CAST("spend_date" AS DATE)   AS "spend_date",
    "channel",
    "channel"                    AS "program_category",
    "campaign",
    "spend_amount",
    "impressions",
    "clicks",
    'google_ads'                 AS "source_platform"
FROM google_ads;
