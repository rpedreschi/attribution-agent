-- Expose the materialized views over DeltaStream's MCP endpoint.
--
-- DeltaStream auto-exposes any materialized view the API token's role can
-- SELECT as an MCP tool the agent discovers and calls. So exposure == RBAC:
-- create a least-privilege reader role, grant it SELECT on exactly the four
-- context MVs, and mint an API token bound to that role.
--
-- The agent then POSTs JSON-RPC to the MCP endpoint with
-- `Authorization: Bearer <token>` (see src/attribution_agent/agent/
-- deltastream_mcp.py and config.deltastream). Adjust the database/schema names
-- if you did not create the MVs in attribution.public.

USE ROLE orgadmin;

-- Context for consistency; the grants below are fully qualified regardless.
USE DATABASE "attribution";
USE SCHEMA "public";

-- 1. Least-privilege role.
CREATE ROLE "attribution_reader";
GRANT USAGE ON DATABASE "attribution" TO ROLE "attribution_reader";
GRANT USAGE ON SCHEMA "attribution"."public" TO ROLE "attribution_reader";

-- 2. Grant SELECT on only the exposed MVs (fully qualified). Each becomes a tool.
GRANT SELECT ON "attribution"."public"."mv_spend_by_channel"           TO ROLE "attribution_reader";
GRANT SELECT ON "attribution"."public"."mv_funnel_by_category"         TO ROLE "attribution_reader";
GRANT SELECT ON "attribution"."public"."mv_channel_touch_distribution" TO ROLE "attribution_reader";
GRANT SELECT ON "attribution"."public"."mv_won_revenue_by_account"     TO ROLE "attribution_reader";

-- 3. Mint the API token bound to the role. Copy the returned token into
--    config.deltastream.api_token (or the DELTASTREAM_API_TOKEN env var).
--    Brand/Events spend rows still live in mv_spend_by_channel, but the agent's
--    own guardrails (not RBAC) exclude them from autonomy.
CREATE API_TOKEN "attribution_agent_token" WITH ('token.role_name' = "attribution_reader");

-- Verify the exposed tools (shell):
--   curl -X POST "$DELTASTREAM_MCP_ENDPOINT" \
--     -H "Content-Type: application/json" \
--     -H "Accept: application/json,text/event-stream" \
--     -H "Authorization: Bearer $DELTASTREAM_API_TOKEN" \
--     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
-- ...or simply: python -m attribution_agent.agent.cli doctor
