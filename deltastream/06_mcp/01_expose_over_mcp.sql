-- Expose the materialized views over DeltaStream's MCP endpoint.
--
-- DeltaStream auto-exposes any materialized view the API token's role can
-- SELECT as an MCP tool the agent discovers and calls. So exposure = RBAC:
-- create a least-privilege reader role, grant it SELECT on exactly the four
-- context MVs, and mint an API token bound to that role.
--
-- The agent then calls the MCP endpoint with `Authorization: Bearer <token>`
-- (see src/attribution_agent/agent/deltastream_mcp.py and config.deltastream).

-- 1. Least-privilege role.
CREATE ROLE attribution_reader;

-- 2. Grant usage on the database/schema and SELECT on only the exposed MVs.
GRANT USAGE ON DATABASE attribution TO ROLE attribution_reader;
GRANT USAGE ON SCHEMA attribution.public TO ROLE attribution_reader;

GRANT SELECT ON MATERIALIZED VIEW mv_spend_by_channel            TO ROLE attribution_reader;
GRANT SELECT ON MATERIALIZED VIEW mv_funnel_by_category          TO ROLE attribution_reader;
GRANT SELECT ON MATERIALIZED VIEW mv_channel_touch_distribution  TO ROLE attribution_reader;
GRANT SELECT ON MATERIALIZED VIEW mv_won_revenue_by_account      TO ROLE attribution_reader;

-- 3. Mint the API token bound to the role. Copy the returned token into
--    config.deltastream.api_token (or the DELTASTREAM_API_TOKEN env var).
--    Brand/Events spend rows still live in mv_spend_by_channel, but the agent's
--    own guardrails (not RBAC) exclude them from autonomy.
CREATE API_TOKEN attribution_agent_token WITH ('role' = 'attribution_reader');

-- Verify exposed tools (shell):
--   curl -s "$DELTASTREAM_MCP_ENDPOINT" \
--     -H "Authorization: Bearer $DELTASTREAM_API_TOKEN" \
--     -H "Content-Type: application/json" \
--     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
