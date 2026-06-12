-- HubSpot MAP: form fills, email engagement, lifecycle stage transitions.
-- Shaped like HubSpot's webhook/event payload. Carries an email, which is the
-- join key into the Salesforce contacts changelog for identity resolution.

CREATE STREAM "hubspot_events" (
    "event_time"      TIMESTAMP,
    "vid"             VARCHAR,        -- HubSpot contact id
    "web_user_id"     VARCHAR,        -- hutk cookie == GA4 client_id; the anonymous->known bridge
    "email"           VARCHAR,
    "event_type"      VARCHAR,        -- form_submission, email_open, email_click, lifecycle_change
    "lifecycle_from"  VARCHAR,
    "lifecycle_to"    VARCHAR,        -- subscriber, lead, mql, sql, opportunity, customer
    "form_name"       VARCHAR,
    "campaign"        VARCHAR,
    "utm_source"      VARCHAR,
    "utm_medium"      VARCHAR,
    "utm_campaign"    VARCHAR
) WITH (
    'topic' = 'src.hubspot.events',
    'store' = 'confluent_cloud',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);
