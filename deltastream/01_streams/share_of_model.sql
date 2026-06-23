-- Share-of-model probe feed: the scheduled "ask the assistants" job that records,
-- per buyer-intent prompt, whether an LLM (ChatGPT / Perplexity / Gemini) named
-- the brand, cited it, and where it ranked. This is the leading indicator for the
-- AI Assistant channel — the place you lose overnight when a model updates. The
-- agent reads the aggregate (mv_share_of_model); a live drop shows up here first.
--
-- Carries topic.partitions/replicas because attr_share_of_model is new —
-- DeltaStream creates it here rather than waiting on the datagen to publish first.

-- Ensure objects land in attribution.public even if run in a fresh session.
USE DATABASE "attribution";
USE SCHEMA "public";

CREATE STREAM "share_of_model" (
    "event_time"     TIMESTAMP,
    "buyer_query"    VARCHAR,
    "assistant"      VARCHAR,    -- chatgpt | perplexity | gemini
    "mentioned"      INTEGER,    -- 1 if the answer named the brand
    "cited"          INTEGER,    -- 1 if the answer linked/cited the brand
    "brand_rank"     INTEGER,    -- 1 = first; 99 = unranked / absent
    "top_competitor" VARCHAR,
    "sentiment"      VARCHAR     -- positive | neutral | absent
) WITH (
    'topic' = 'attr_share_of_model',
    'topic.partitions' = 1,
    'topic.replicas' = 3,
    'store' = 'demo_confluent',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);
