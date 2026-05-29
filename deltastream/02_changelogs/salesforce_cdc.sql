-- Salesforce CDC changelogs.
-- CHANGELOG (not STREAM) because these are upsert-semantics dimension tables
-- keyed by id; identity resolution joins against the latest version of each row.
--
-- contacts: the identity spine. Maps email -> contact_id -> account_id, which
--           is how anonymous web/ad traffic gets attributed to an account.
-- accounts: the account dimension sunk into ClickHouse.
-- opportunities: stage transitions feed the conversions table.

CREATE CHANGELOG sf_contacts (
    "contact_id" VARCHAR,
    "email"      VARCHAR,
    "account_id" VARCHAR,
    "first_name" VARCHAR,
    "last_name"  VARCHAR,
    "updated_at" TIMESTAMP,
    PRIMARY KEY ("contact_id")
) WITH (
    'topic' = 'src.salesforce.cdc.contacts',
    'store' = 'kafka_src',
    'value.format' = 'json',
    'timestamp' = 'updated_at'
);

CREATE CHANGELOG sf_accounts (
    "account_id"     VARCHAR,
    "name"           VARCHAR,
    "industry"       VARCHAR,
    "employee_count" INTEGER,
    "arr_band"       VARCHAR,
    "region"         VARCHAR,
    "is_customer"    INTEGER,
    "updated_at"     TIMESTAMP,
    PRIMARY KEY ("account_id")
) WITH (
    'topic' = 'src.salesforce.cdc.accounts',
    'store' = 'kafka_src',
    'value.format' = 'json',
    'timestamp' = 'updated_at'
);

CREATE CHANGELOG sf_opportunities (
    "opportunity_id" VARCHAR,
    "account_id"     VARCHAR,
    "stage_from"     VARCHAR,
    "stage_to"       VARCHAR,
    "amount"         DOUBLE,
    "deal_size"      VARCHAR,
    "event_time"     TIMESTAMP,
    PRIMARY KEY ("opportunity_id", "event_time")
) WITH (
    'topic' = 'src.salesforce.cdc.opportunities',
    'store' = 'kafka_src',
    'value.format' = 'json',
    'timestamp' = 'event_time'
);
