-- conversions
-- B2B funnel events. One row per funnel-stage transition for a contact/account.
-- event_type covers the full funnel: touch, conversation, mql, sql,
-- opp_created, closed_won, closed_lost.
--
-- closed_won rows carry the revenue that the attribution views distribute
-- across channels. The sum of revenue over closed_won rows in the reporting
-- period is the total attributed revenue (identical across all three models).

CREATE TABLE IF NOT EXISTS attribution.conversions
(
    event_time      DateTime64(3, 'UTC'),
    user_id         String,
    account_id      String,
    contact_id      Nullable(String),
    event_type      LowCardinality(String),       -- touch | conversation | mql | sql | opp_created | closed_won | closed_lost
    opportunity_id  Nullable(String),
    stage_from      LowCardinality(String),
    stage_to        LowCardinality(String),
    revenue         Decimal(18, 2) DEFAULT 0,     -- ARR / deal value; non-zero on closed_won
    deal_size       LowCardinality(String),       -- SMB | MidMarket | Enterprise
    program_category LowCardinality(String),      -- category credited at this stage (last-touch convenience)
    source_system   LowCardinality(String),
    ingested_at     DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (account_id, event_time)
SETTINGS index_granularity = 8192;
