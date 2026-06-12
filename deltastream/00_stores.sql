-- Environment bootstrap: the Confluent Cloud store + the database/schema that
-- every later object lives in. Run once per environment, first, before the
-- stream/changelog definitions in 01_streams/ onward.
--
-- NOTE: there is no ClickHouse sink store anymore. The attribution context is
-- served from DeltaStream materialized views over MCP (see 06_mcp/). DeltaStream
-- uses ClickHouse internally to back MVs; we do not manage it.

-- 1. The Kafka store. Fill in the three placeholders below with YOUR cluster:
--      'uris'              -> KAFKA_BOOTSTRAP_SERVERS (e.g. pkc-921jm.us-east-2.aws.confluent.cloud:9092)
--      'availability_zone' -> the AZ/region your Confluent cluster runs in
--      username / password -> your Confluent API key / secret. For a quick demo
--                             you may inline the literal key/secret here;
--                             DeltaStream stores them encrypted. To keep them
--                             out of this file, create them with CREATE SECRET
--                             first and reference the secret names instead.
CREATE STORE "confluent_cloud"
    WITH (
        'type' = KAFKA,
        'availability_zone' = 'us-east-2a',
        'uris' = 'pkc-xxxxx.us-east-2.aws.confluent.cloud:9092',
        'kafka.sasl.hash_function' = PLAIN,
        'kafka.sasl.username' = 'KAFKA_API_KEY',
        'kafka.sasl.password' = 'KAFKA_API_SECRET'
    );

-- 2. The database (and its default `public` schema) that holds every stream,
--    changelog, and materialized view. Must match config.deltastream.database
--    / schema_name (defaults: attribution / public). Quoted lowercase so the
--    name is stored exactly as the config and MCP layer expect it.
CREATE DATABASE "attribution";

-- 3. Session context. DeltaStream resolves unqualified object names against the
--    current database/schema/store, so set these at the start of EVERY CLI or
--    web-app session before running 01_streams/ onward (re-run if you reconnect).
USE DATABASE "attribution";
USE SCHEMA "public";
USE STORE "confluent_cloud";
