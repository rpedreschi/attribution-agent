-- Sink the three resolved touchpoint streams into ClickHouse
-- attribution.marketing_touchpoints. One INSERT INTO per source stream
-- (DeltaStream runs each as a continuous query); they all target the same
-- ClickHouse table, which is the UNION the funnel + attribution views read.

INSERT INTO clickhouse_sink."attribution"."marketing_touchpoints"
SELECT "event_time", "user_id", "account_id", "contact_id", "session_id",
       "channel", "program_category", "campaign", "medium", "source",
       "" AS "keyword", "landing_page", "device_type",
       "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
       "source_system"
FROM tp_web;

INSERT INTO clickhouse_sink."attribution"."marketing_touchpoints"
SELECT "event_time", "user_id", "account_id", "contact_id", "session_id",
       "channel", "program_category", "campaign", "medium", "source",
       "" AS "keyword", "landing_page", "device_type",
       "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
       "source_system"
FROM tp_outreach;

INSERT INTO clickhouse_sink."attribution"."marketing_touchpoints"
SELECT "event_time", "user_id", "account_id", "contact_id", "session_id",
       "channel", "program_category", "campaign", "medium", "source",
       "" AS "keyword", "landing_page", "device_type",
       "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
       "source_system"
FROM tp_email;
