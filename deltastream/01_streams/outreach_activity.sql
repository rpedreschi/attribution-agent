-- Outreach SDR activity: dials, conversations, sequence enrollment.
-- Carries the prospect email + (when known) the Salesforce contact id, so SDR
-- touches attach to the right account during identity resolution.

CREATE STREAM outreach_activity (
    "event_time"   TIMESTAMP,
    "prospect_id"  VARCHAR,
    "email"        VARCHAR,
    "contact_id"   VARCHAR,           -- Salesforce contact id when synced
    "activity"     VARCHAR,           -- dial, conversation, sequence_enroll, reply
    "sequence"     VARCHAR,
    "sdr"          VARCHAR
) WITH (
    'topic' = 'src.outreach.activity',
    'store' = 'confluent_cloud',
    'value.format' = 'json',
    'timestamp' = 'event_time',
    'timestamp.format' = 'iso8601'
);
