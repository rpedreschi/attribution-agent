-- GA4 web sessions / page views / conversion events.
-- Shaped like the GA4 Measurement Protocol / BigQuery export event payload.
-- This is the anonymous-traffic stream that identity resolution later stitches
-- to known Salesforce contacts.

CREATE STREAM ga4_events (
    "event_time"    TIMESTAMP,
    "user_id"       VARCHAR,          -- GA4 client_id (anonymous) or user_id when set
    "session_id"    VARCHAR,
    "event_name"    VARCHAR,          -- session_start, page_view, generate_lead, ...
    "page_location" VARCHAR,
    "device_type"   VARCHAR,
    "utm_source"    VARCHAR,
    "utm_medium"    VARCHAR,
    "utm_campaign"  VARCHAR,
    "utm_term"      VARCHAR,
    "utm_content"   VARCHAR
) WITH (
    'topic' = 'src.ga4.events',
    'store' = 'confluent_cloud',
    'value.format' = 'json',
    'timestamp' = 'event_time'
);
