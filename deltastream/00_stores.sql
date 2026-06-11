-- DeltaStream store: the Confluent Cloud Kafka cluster that datagen publishes
-- to. Run once per environment before the stream/changelog definitions.
-- Secrets are referenced by name and created via the DeltaStream secrets API
-- (or `CREATE SECRET`), never inlined here.
--
-- NOTE: there is no ClickHouse sink store anymore. The attribution context is
-- served from DeltaStream materialized views over MCP (see 06_mcp/). DeltaStream
-- uses ClickHouse internally to back MVs; we do not manage it.

CREATE STORE confluent_cloud
    WITH (
        'type' = KAFKA,
        'availability_zone' = 'us-east-2a',
        'uris' = 'pkc-xxxxx.us-east-2.aws.confluent.cloud:9092',
        'kafka.sasl.hash_function' = PLAIN,
        'kafka.sasl.username' = 'KAFKA_API_KEY',
        'kafka.sasl.password' = 'KAFKA_API_SECRET'
    );
