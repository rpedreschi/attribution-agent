-- Identity resolution, stage 2: a single resolved-touchpoint stream that
-- normalizes all touch-producing sources to the marketing_touchpoints shape,
-- with account_id/contact_id attached.
--
-- GA4 web traffic is the only anonymous source: it temporal-joins the
-- web_identity_map changelog on user_id to attach an account (NULL while still
-- anonymous). Outreach and HubSpot touches arrive already keyed to a known
-- contact, so they resolve through sf_contacts directly. Three intermediate
-- CSAS statements, UNION'd at the sink (file 04).

-- 2a. Resolved web touches.
CREATE STREAM tp_web AS
SELECT
    g."event_time"                                   AS "event_time",
    g."user_id"                                      AS "user_id",
    m."account_id"                                   AS "account_id",
    m."contact_id"                                   AS "contact_id",
    g."session_id"                                   AS "session_id",
    'Organic/Web'                                    AS "channel",
    'Organic/Web'                                    AS "program_category",
    g."utm_campaign"                                 AS "campaign",
    g."utm_medium"                                   AS "medium",
    'ga4'                                            AS "source",
    g."page_location"                                AS "landing_page",
    g."device_type"                                  AS "device_type",
    g."utm_source"                                   AS "utm_source",
    g."utm_medium"                                   AS "utm_medium",
    g."utm_campaign"                                 AS "utm_campaign",
    g."utm_term"                                     AS "utm_term",
    g."utm_content"                                  AS "utm_content",
    'ga4'                                            AS "source_system"
FROM ga4_events g
LEFT JOIN web_identity_map m
    ON g."user_id" = m."web_user_id";

-- 2b. Outreach SDR touches (already key to a Salesforce contact).
CREATE STREAM tp_outreach AS
SELECT
    o."event_time"                                   AS "event_time",
    o."contact_id"                                   AS "user_id",
    c."account_id"                                   AS "account_id",
    o."contact_id"                                   AS "contact_id",
    o."prospect_id"                                  AS "session_id",
    'Outbound SDR'                                   AS "channel",
    'Outbound SDR'                                   AS "program_category",
    o."sequence"                                     AS "campaign",
    'sdr'                                            AS "medium",
    'outreach'                                       AS "source",
    ''                                               AS "landing_page",
    'n/a'                                            AS "device_type",
    'outreach'                                       AS "utm_source",
    'sdr'                                            AS "utm_medium",
    o."sequence"                                     AS "utm_campaign",
    ''                                               AS "utm_term",
    ''                                               AS "utm_content",
    'outreach'                                       AS "source_system"
FROM outreach_activity o
JOIN sf_contacts c
    ON o."email" = c."email";

-- 2c. HubSpot email-nurture touches (engagement events, not the form bridge).
CREATE STREAM tp_email AS
SELECT
    h."event_time"                                   AS "event_time",
    h."vid"                                          AS "user_id",
    c."account_id"                                   AS "account_id",
    c."contact_id"                                   AS "contact_id",
    h."vid"                                          AS "session_id",
    'Email Nurture'                                  AS "channel",
    'Email Nurture'                                  AS "program_category",
    h."campaign"                                     AS "campaign",
    'email'                                          AS "medium",
    'hubspot'                                        AS "source",
    ''                                               AS "landing_page",
    'n/a'                                            AS "device_type",
    h."utm_source"                                   AS "utm_source",
    'email'                                          AS "utm_medium",
    h."utm_campaign"                                 AS "utm_campaign",
    ''                                               AS "utm_term",
    ''                                               AS "utm_content",
    'hubspot'                                        AS "source_system"
FROM hubspot_events h
JOIN sf_contacts c
    ON h."email" = c."email"
WHERE h."event_type" IN ('email_open', 'email_click');
