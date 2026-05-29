-- Sink the Salesforce accounts changelog into ClickHouse attribution.accounts.
-- ReplacingMergeTree on the ClickHouse side collapses to the latest updated_at
-- per account_id, so streaming the full changelog is safe.

INSERT INTO clickhouse_sink."attribution"."accounts"
SELECT
    "account_id",
    "name",
    "industry",
    "employee_count",
    "arr_band",
    "region",
    "is_customer",
    "updated_at"
FROM sf_accounts;
