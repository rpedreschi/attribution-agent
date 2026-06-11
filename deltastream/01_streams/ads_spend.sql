-- LinkedIn Ads + Google Ads spend/performance.
-- Both platforms publish the same shape into their own topics; we define one
-- stream per platform and UNION them at the sink. Daily granularity rows.

CREATE STREAM linkedin_ads (
    "spend_date"   VARCHAR,           -- yyyy-mm-dd
    "channel"      VARCHAR,           -- Paid Social
    "campaign"     VARCHAR,
    "spend_amount" DOUBLE,
    "impressions"  BIGINT,
    "clicks"       BIGINT
) WITH (
    'topic' = 'src.linkedin.ads',
    'store' = 'confluent_cloud',
    'value.format' = 'json'
);

CREATE STREAM google_ads (
    "spend_date"   VARCHAR,
    "channel"      VARCHAR,           -- Paid Search
    "campaign"     VARCHAR,
    "spend_amount" DOUBLE,
    "impressions"  BIGINT,
    "clicks"       BIGINT
) WITH (
    'topic' = 'src.google.ads',
    'store' = 'confluent_cloud',
    'value.format' = 'json'
);
