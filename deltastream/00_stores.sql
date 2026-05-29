-- DeltaStream stores: the Kafka source and the ClickHouse sink.
-- Run once per environment before the stream/changelog definitions.
-- Secrets are referenced by name and created via the DeltaStream secrets API
-- (or `CREATE SECRET`), never inlined here.

CREATE STORE kafka_src
    WITH (
        'type' = KAFKA,
        'availability_zone' = 'us-east-1a',
        'uris' = 'pkc-xxxxx.us-east-1.aws.confluent.cloud:9092',
        'kafka.sasl.hash_function' = PLAIN,
        'kafka.sasl.username' = 'KAFKA_API_KEY',
        'kafka.sasl.password' = 'KAFKA_API_SECRET'
    );

-- ClickHouse sink store. DeltaStream writes resolved rows here via INSERT INTO.
CREATE STORE clickhouse_sink
    WITH (
        'type' = CLICKHOUSE,
        'uris' = 'https://your-instance.clickhouse.cloud:8443',
        'clickhouse.username' = 'default',
        'clickhouse.password' = 'CLICKHOUSE_PASSWORD'
    );
