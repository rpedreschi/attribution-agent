-- campaign_spend
-- Daily spend per campaign, sunk from the LinkedIn Ads / Google Ads streams
-- (and manual/loaded cost for non-ad channels such as Outbound SDR and Events).
-- The denominator for CAC and ROI.

CREATE TABLE IF NOT EXISTS attribution.campaign_spend
(
    spend_date       Date,
    channel          LowCardinality(String),
    program_category LowCardinality(String),
    campaign         String,
    spend_amount     Decimal(18, 2),
    impressions      UInt64 DEFAULT 0,
    clicks           UInt64 DEFAULT 0,
    source_platform  LowCardinality(String),      -- linkedin, google_ads, outreach, hubspot, manual
    ingested_at      DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(spend_date)
ORDER BY (channel, campaign, spend_date)
SETTINGS index_granularity = 8192;
