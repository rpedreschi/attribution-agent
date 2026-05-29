-- marketing_touchpoints
-- Extends the published ClickHouse marketing-attribution pattern
-- (https://oneuptime.com/blog/post/2026-03-31-clickhouse-marketing-attribution-analytics/view)
-- with B2B identity columns (account_id) populated by DeltaStream identity resolution.
--
-- One row per marketing touch across all six source systems after identity
-- resolution. Sunk into here by the DeltaStream INSERT INTO job.

CREATE TABLE IF NOT EXISTS attribution.marketing_touchpoints
(
    event_time      DateTime64(3, 'UTC'),
    user_id         String,                       -- anonymous web id OR known contact id
    account_id      Nullable(String),             -- resolved via Salesforce CDC join; NULL when still anonymous
    contact_id      Nullable(String),             -- resolved Salesforce/HubSpot contact
    session_id      String,
    channel         LowCardinality(String),       -- Paid Search, Paid Social, Email Nurture, Outbound SDR, Organic/Web, Events, Brand
    program_category LowCardinality(String),      -- coarser grouping used in the funnel + CAC sheets
    campaign        String,
    medium          LowCardinality(String),
    source          LowCardinality(String),       -- google, linkedin, hubspot, outreach, ga4, salesforce
    keyword         String,
    landing_page    String,
    device_type     LowCardinality(String),
    utm_source      String,
    utm_medium      String,
    utm_campaign    String,
    utm_term        String,
    utm_content     String,
    -- bookkeeping
    source_system   LowCardinality(String),       -- which of the six APIs produced this
    ingested_at     DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (account_id, user_id, event_time)
SETTINGS index_granularity = 8192;
