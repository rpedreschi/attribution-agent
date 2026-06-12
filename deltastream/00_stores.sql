-- Environment bootstrap: the database/schema that every later object lives in.
--
-- The Kafka store already exists in this DeltaStream org as `demo_confluent`
-- (and is the default store), so there is NO CREATE STORE here. The stream and
-- changelog DDLs reference 'demo_confluent' directly in their WITH clauses.
--
-- NOTE: the attribution context is served from DeltaStream materialized views
-- over MCP (see 06_mcp/). DeltaStream uses ClickHouse internally to back MVs; we
-- do not manage it.

-- 1. The database (and its default `public` schema) that holds every stream,
--    changelog, and materialized view. Must match config.deltastream.database
--    / schema_name (defaults: attribution / public). Quoted lowercase so the
--    name is stored exactly as the config and MCP layer expect it.
CREATE DATABASE "attribution";

-- 2. Session context. DeltaStream creates unqualified objects in — and resolves
--    names against — the current database/schema, so set these at the start of
--    EVERY CLI or web-app session before running 01_streams/ onward (re-run if
--    you reconnect). This is what guarantees every object lands in
--    attribution.public. demo_confluent is already the default store, so no
--    USE STORE is required.
USE DATABASE "attribution";
USE SCHEMA "public";
