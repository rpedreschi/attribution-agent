# DeltaStream deploy runbook

Bring the attribution pipeline up in DeltaStream once events are flowing into
Confluent (i.e. after `python -m attribution_agent.mock_generator --stream`).

Everything is driven from SQL — run it in the **web app** SQL editor or the
**CLI** (`deltastream`, see [Starting with the CLI](https://docs.deltastream.io/getting-started/starting-with-cli)).
Either way you run the same statements in the same order.

> **Quick test shortcut:** `deltastream/deploy_all.sql` is every statement below
> concatenated in order — run that one file instead of opening each folder.
> It's generated; regenerate with `bash deltastream/build_deploy_all.sh` after
> editing any source file. The numbered files below remain the source of truth.

## 0. Before you start

- Events must already be in Confluent on the `src.*` topics. Confirm with the
  datagen run, or in the Confluent UI (each topic should have a message count).
- The Kafka store already exists as `demo_confluent` (the default store); you do
  not create one. You just need a DDL-capable role to create the database and
  objects. The `attribution_reader` role minted in step 6 is read-only and is
  only for the agent's MCP token.

## 1. Database + session context  — `00_stores.sql`

The Kafka store already exists in this org as **`demo_confluent`** (the default
store), so there is no store to create — the stream/changelog DDLs reference
`'demo_confluent'` directly. Just run `00_stores.sql`: it creates the
`attribution` database and sets the session context (`USE DATABASE / SCHEMA`).

> **The session context is what puts every object in `attribution.public`.**
> DeltaStream creates unqualified objects in the current database/schema, so
> `USE DATABASE "attribution"; USE SCHEMA "public";` at the top of the session is
> what guarantees the streams, changelogs, and MVs all land there. It's
> per-connection — if you reconnect (new CLI session, web-app refresh), re-run
> those two `USE` statements before running anything else.

Validate:

```sql
LIST STORES;                          -- demo_confluent present (already exists)
PRINT STORE "demo_confluent";         -- lists the src.* topics => connectivity OK
LIST DATABASES;                       -- attribution present
```

> **Identifiers are quoted lowercase everywhere.** Every object and column name
> in `deltastream/` is double-quoted lowercase (e.g. `"ga4_events"`,
> `"event_time"`) so DeltaStream stores it exactly as written — matching the
> JSON payload keys and the lowercase names in `config.deltastream`. When you
> hand-write a query, quote names the same way (`SELECT * FROM "touchpoints";`),
> or the unquoted name may fold to a different case and "not found".
>
> **Topic ownership convention:** every topic DeltaStream *creates* is prefixed
> `attr_` (`attr_touchpoints`, `attr_conversions`, `attr_spend`,
> `attr_funnel_events`, `attr_web_identity_map`) so ops can tell whose topics
> they are. The `src.*` topics are datagen *inputs* and are not renamed.
> Because DeltaStream has to create those `attr_*` topics, each carries
> `'topic.partitions' = '6'` and `'topic.replicas' = '3'` in its WITH clause
> (Confluent Cloud requires replication factor 3); adjust if your cluster
> differs.

If `PRINT STORE` can't list topics, the store credentials/URI are wrong — fix
before going further.

## 2. Source streams — `01_streams/`

Run all four: `ga4_sessions.sql`, `hubspot_events.sql`, `outreach_activity.sql`,
`ads_spend.sql` (creates `linkedin_ads` + `google_ads`).

Validate — **a `SELECT` on a stream is a continuous query** (it tails the topic
and runs until you stop it, Ctrl-C). That's exactly what you want here: you
should see rows scroll, proving ingestion *and* timestamp parsing:

```sql
SELECT * FROM "ga4_events";           -- rows scroll => iso8601 event_time parsed
SELECT * FROM "linkedin_ads";
```

If a stream returns nothing, the topic name in the DDL doesn't match the topic in
Confluent, or `timestamp.format` doesn't match the payload. The datagen emits
`2026-06-12T00:46:43.000Z` (iso8601) — that matches the stream DDLs.

## 3. Salesforce changelogs — `02_changelogs/`

Run `salesforce_cdc.sql` (creates `sf_contacts`, `sf_accounts`, `sf_opportunities`).

```sql
LIST CHANGELOGS;
SELECT * FROM "sf_contacts";          -- the identity spine: email -> contact -> account
```

## 4. Identity resolution — `03_identity/`

Run in order: `01_web_identity_map.sql`, then `02_touchpoints.sql`.

`02_touchpoints.sql` creates the `touchpoints` stream and launches **three
continuous `INSERT INTO` queries**. These run forever — check they reached
`running` (not `errored`):

```sql
LIST QUERIES;                         -- the INSERT INTO queries should be Running
SELECT * FROM "touchpoints" WHERE "account_id" IS NOT NULL;   -- resolved touches appear
```

`account_id` is NULL for still-anonymous GA4 traffic and fills in once a contact
forms-fills (the anon->known bridge). With the live stream's compressed journeys
you should see resolved rows within a minute or two.

## 5. Facts + materialized views — `04_facts/`, then `05_views/`

Run `04_facts/` in order (`01_conversions.sql`, `02_spend.sql`,
`03_funnel_events.sql`) — each adds more continuous queries. Then `05_views/`
(the four `mv_*`). Re-check `LIST QUERIES;` — everything should be `Running`.

Unlike streams, **a `SELECT` on a materialized view returns a snapshot** of
current state (bounded — it returns and exits):

```sql
SELECT * FROM "mv_won_revenue_by_account" ORDER BY "revenue" DESC;
SELECT * FROM "mv_channel_touch_distribution" LIMIT 20;
SELECT * FROM "mv_spend_by_channel";
SELECT * FROM "mv_funnel_by_category";
```

`mv_won_revenue_by_account` populates only after journeys reach `closed_won`. With
`--stream` defaults that's a couple minutes in; with `--backfill` the Q1 closes
are immediate.

## 6. Expose over MCP — `06_mcp/`

Run `01_expose_over_mcp.sql`. It creates the least-privilege `attribution_reader`
role, grants it `SELECT` on the four MVs (each becomes an MCP tool), and mints an
API token. **Copy the token** into `DELTASTREAM_API_TOKEN` (or
`config/settings.yaml`).

> If you created the MVs somewhere other than `attribution.public`, fix the
> fully-qualified grant names in this file to match.

## 7. Confirm the agent can see it

```bash
python -m attribution_agent.agent.cli doctor
```

This checks config, Confluent topics, the live MCP handshake (lists the four
exposed MVs as tools), and the LLM backend.

## Health-check cheat sheet

| command | what it tells you |
|---|---|
| `LIST QUERIES;` | every `INSERT INTO` / MV query is `Running`, none `Errored` |
| `DESCRIBE QUERY <id>;` | why a specific query errored |
| `SELECT * FROM <stream>;` | live ingestion + timestamp parsing (continuous) |
| `SELECT * FROM <mv>;` | current aggregated state (snapshot) |
| `PRINT STORE "demo_confluent";` | store connectivity / topic visibility |

## Teardown / redeploy

To rebuild, drop in reverse dependency order (MVs → fact/identity streams +
their queries → changelogs → source streams), or drop the database. Terminate
the continuous queries first (`TERMINATE QUERY <id>;`) — a stream with a running
query attached to it can't be dropped.
