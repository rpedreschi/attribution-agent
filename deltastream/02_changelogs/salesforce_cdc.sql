-- Salesforce CDC relations.
-- contacts + accounts are CHANGELOGs (upsert-semantics dimension tables keyed by
-- id; identity resolution joins against the latest version of each row).
-- opportunities is a STREAM, not a changelog: stage transitions are append-only
-- events, and it is only ever read as a source for the conversions stream (never
-- joined as a lookup), so changelog semantics would wrongly collapse it.
--
-- contacts: the identity spine. Maps email -> contact_id -> account_id, which
--           is how anonymous web/ad traffic gets attributed to an account.
--           Keyed by EMAIL (not contact_id): every downstream stream->changelog
--           join resolves contacts on email, and DeltaStream requires such a
--           join to reference the changelog's primary key. email is 1:1 with
--           contact_id here, so upsert semantics are unchanged.
-- accounts: the account dimension (available for enrichment / future MVs).
-- opportunities: stage-transition events feed the conversions stream.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE CHANGELOG "sf_contacts" (
    "contact_id" VARCHAR,
    "email"      VARCHAR,
    "account_id" VARCHAR,
    "first_name" VARCHAR,
    "last_name"  VARCHAR,
    "updated_at" TIMESTAMP,
    PRIMARY KEY ("email")
) WITH (
    'topic' = 'rachel_salesforce_cdc_contacts',
    'topic.partitions' = 1,
    'topic.replicas' = 1,
    'store' = 'demo_warpstream',
    'kafka.properties.request.timeout.ms' = '60000',
    'kafka.properties.delivery.timeout.ms' = '120000',
    'kafka.properties.linger.ms' = '100',
    'kafka.properties.batch.size' = '1048576',
    'value.format' = 'json',
    'timestamp' = 'updated_at',
    'timestamp.format' = 'iso8601'
);

CREATE CHANGELOG "sf_accounts" (
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
    'topic' = 'rachel_salesforce_cdc_accounts',
    'topic.partitions' = 1,
    'topic.replicas' = 1,
    'store' = 'demo_warpstream',
    'kafka.properties.request.timeout.ms' = '60000',
    'kafka.properties.delivery.timeout.ms' = '120000',
    'kafka.properties.linger.ms' = '100',
    'kafka.properties.batch.size' = '1048576',
    'value.format' = 'json',
    'timestamp' = 'updated_at',
    'timestamp.format' = 'iso8601'
);

CREATE STREAM "sf_opportunities" (
    "opportunity_id" VARCHAR,
    "account_id"     VARCHAR,
    "stage_from"     VARCHAR,
    "stage_to"       VARCHAR,
    "amount"         DOUBLE,
    "deal_size"      VARCHAR,
    "event_time"     TIMESTAMP,
    "program_category" VARCHAR        -- source channel (lead source)
) WITH (
    'topic' = 'rachel_salesforce_cdc_opportunities',
    'topic.partitions' = 1,
    'topic.replicas' = 1,
    'store' = 'demo_warpstream',
    'kafka.properties.request.timeout.ms' = '60000',
    'kafka.properties.delivery.timeout.ms' = '120000',
    'kafka.properties.linger.ms' = '100',
    'kafka.properties.batch.size' = '1048576',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);
