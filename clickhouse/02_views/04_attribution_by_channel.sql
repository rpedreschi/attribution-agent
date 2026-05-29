-- v_attribution_by_channel
-- Side-by-side view of the three models per channel, plus each channel's share
-- of total attributed revenue under each model. Feeds the "Attribution by
-- Channel" sheet. The model-agreement coefficient (correlation across the three
-- share vectors) is computed in the spreadsheet layer from these rows.

CREATE VIEW IF NOT EXISTS attribution.v_attribution_by_channel AS
WITH
    (SELECT sum(attributed_revenue) FROM attribution.attribution_last_touch) AS tot_lt,
    (SELECT sum(attributed_revenue) FROM attribution.attribution_linear)     AS tot_ln,
    (SELECT sum(attributed_revenue) FROM attribution.attribution_time_decay) AS tot_td
SELECT
    coalesce(lt.channel, ln.channel, td.channel)                AS channel,
    lt.attributed_revenue                                       AS last_touch_revenue,
    ln.attributed_revenue                                       AS linear_revenue,
    td.attributed_revenue                                       AS time_decay_revenue,
    round(lt.attributed_revenue / tot_lt, 4)                    AS last_touch_share,
    round(ln.attributed_revenue / tot_ln, 4)                    AS linear_share,
    round(td.attributed_revenue / tot_td, 4)                    AS time_decay_share
FROM attribution.attribution_last_touch AS lt
FULL OUTER JOIN attribution.attribution_linear     AS ln ON ln.channel = lt.channel
FULL OUTER JOIN attribution.attribution_time_decay AS td ON td.channel = lt.channel
ORDER BY time_decay_revenue DESC;
