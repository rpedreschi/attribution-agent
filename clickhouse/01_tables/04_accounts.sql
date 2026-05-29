-- accounts
-- Salesforce account dimension, sunk from the Salesforce CDC stream.
-- ReplacingMergeTree so late-arriving CDC updates collapse to the latest
-- version per account_id.

CREATE TABLE IF NOT EXISTS attribution.accounts
(
    account_id      String,
    name            String,
    industry        LowCardinality(String),
    employee_count  UInt32,
    arr_band        LowCardinality(String),       -- <1M | 1-10M | 10-50M | 50M+
    region          LowCardinality(String),       -- NA | EMEA | APAC | LATAM
    is_customer     UInt8 DEFAULT 0,
    updated_at      DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY account_id
SETTINGS index_granularity = 8192;
