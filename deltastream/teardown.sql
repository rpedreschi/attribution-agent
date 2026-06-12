-- teardown.sql — drop everything this project created, for a clean restart.
--
-- PREREQUISITE — terminate the running continuous queries first. DeltaStream
-- will not drop a relation that an active query reads from or writes to, and
-- query ids are dynamic so they cannot be scripted here. Run:
--
--     LIST QUERIES;
--
-- then, for every query id listed:
--
--     TERMINATE QUERY <id>;
--
-- and only then run this file.
--
-- NOT dropped (on purpose): the shared `demo_confluent` store, and the Kafka
-- topics themselves. To clear the topics, delete the attr_* topics in Confluent
-- or just re-run `python -m attribution_agent.mock_generator --recreate-topics`.
--
-- A "does not exist" error on any line is harmless (it was already gone). If you
-- pipe this file and the CLI stops on such an error, either run the lines by
-- hand or just use the single DROP DATABASE at the bottom, which removes every
-- relation at once.

USE ROLE orgadmin;

-- Materialized views (consume the fact streams) ----------------------------
DROP MATERIALIZED VIEW "attribution"."public"."mv_won_revenue_by_account";
DROP MATERIALIZED VIEW "attribution"."public"."mv_channel_touch_distribution";
DROP MATERIALIZED VIEW "attribution"."public"."mv_funnel_by_category";
DROP MATERIALIZED VIEW "attribution"."public"."mv_spend_by_channel";

-- Fact + identity relations (drop consumers before producers) --------------
DROP STREAM    "attribution"."public"."funnel_events";
DROP STREAM    "attribution"."public"."spend";
DROP STREAM    "attribution"."public"."conversions";
DROP STREAM    "attribution"."public"."touchpoints";
DROP CHANGELOG "attribution"."public"."web_identity_map";
DROP STREAM    "attribution"."public"."web_resolved";

-- Source changelogs + streams ----------------------------------------------
DROP CHANGELOG "attribution"."public"."sf_contacts";
DROP CHANGELOG "attribution"."public"."sf_accounts";
DROP STREAM    "attribution"."public"."sf_opportunities";
DROP STREAM    "attribution"."public"."ga4_events";
DROP STREAM    "attribution"."public"."hubspot_events";
DROP STREAM    "attribution"."public"."outreach_activity";
DROP STREAM    "attribution"."public"."linkedin_ads";
DROP STREAM    "attribution"."public"."google_ads";

-- The (now empty) database -------------------------------------------------
DROP DATABASE "attribution";

-- Org-level objects, outside the database ----------------------------------
DROP API_TOKEN "attribution_agent_token";
DROP ROLE "attribution_reader";
