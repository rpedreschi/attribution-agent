-- v_won_journeys
-- The substrate for all three attribution models: every touchpoint that
-- occurred on a closed_won account on or before the close date, annotated with
-- its position in the journey and recency. One row per (opportunity, touch).
--
-- Plain VIEW (cheap, always current). The model views below read from it.

CREATE VIEW IF NOT EXISTS attribution.v_won_journeys AS
SELECT
    w.opportunity_id                                                       AS opportunity_id,
    w.account_id                                                           AS account_id,
    w.revenue                                                              AS revenue,
    w.close_time                                                           AS close_time,
    t.channel                                                              AS channel,
    t.program_category                                                     AS program_category,
    t.campaign                                                             AS campaign,
    t.event_time                                                           AS touch_time,
    dateDiff('day', t.event_time, w.close_time)                            AS days_before_close,
    row_number() OVER (PARTITION BY w.opportunity_id ORDER BY t.event_time) AS touch_seq,
    count()      OVER (PARTITION BY w.opportunity_id)                       AS touch_count,
    max(t.event_time) OVER (PARTITION BY w.opportunity_id)                  AS last_touch_time
FROM
(
    SELECT opportunity_id, account_id, event_time AS close_time, revenue
    FROM attribution.conversions
    WHERE event_type = 'closed_won'
) AS w
INNER JOIN attribution.marketing_touchpoints AS t
    ON  t.account_id  = w.account_id
    AND t.event_time <= w.close_time;
