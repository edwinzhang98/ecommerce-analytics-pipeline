-- =====================================================================================
-- Q1. How do delivery time and lateness relate to bad reviews, and which states are worst?
-- Decision : where logistics improvement should be targeted first (ops / logistics lead).
-- Inputs   : marts.fct_orders, marts.dim_date
-- Output   : late_vs_on_time  - bad-review rate for late vs on-time deliveries (95% Wilson CI)
--            by_delay         - bad-review rate by days early / late vs the estimate
--            by_state         - per delivery state: delivery time, late rate, bad-review rate, and the
--                               bad-review rate expected from its late rate alone
--            state_correlation - how much of the state-to-state spread lateness explains
-- Population: delivered orders with a delivery date AND a review; complete months by default.
-- Caveat   : associations, not causal effects (e.g. remote states differ in many ways).
-- Run      : uv run python scripts/run_sql.py analyses/q1_delivery_vs_reviews_by_state.sql
-- =====================================================================================

set variable bad_review_max_score = 2;    -- a review with score <= this is "bad"
set variable min_orders_per_state = 300;  -- hide states with fewer reviewed deliveries
set variable complete_months_only = true; -- restrict to 2017-01 .. 2018-08

create or replace temp macro wilson_low(successes, trials) as
    case when trials > 0 then
        (successes / trials + 1.96 ^ 2 / (2 * trials)
            - 1.96 * sqrt((successes / trials) * (1 - successes / trials) / trials + 1.96 ^ 2 / (4 * trials * trials)))
        / (1 + 1.96 ^ 2 / trials)
    end;

create or replace temp macro wilson_high(successes, trials) as
    case when trials > 0 then
        (successes / trials + 1.96 ^ 2 / (2 * trials)
            + 1.96 * sqrt((successes / trials) * (1 - successes / trials) / trials + 1.96 ^ 2 / (4 * trials * trials)))
        / (1 + 1.96 ^ 2 / trials)
    end;

create or replace temp view q1_population as
select
    fct_orders.order_id,
    fct_orders.delivery_state,
    fct_orders.delivery_region,
    fct_orders.delivery_days,
    fct_orders.delivery_delay_days,
    fct_orders.is_late_delivery,
    fct_orders.review_score,
    fct_orders.review_score <= getvariable('bad_review_max_score') as is_bad

from marts.fct_orders as fct_orders
inner join marts.dim_date as dim_date
    on fct_orders.order_purchase_date = dim_date.date_day
where fct_orders.is_late_delivery is not null
    and fct_orders.has_review
    and (not getvariable('complete_months_only') or dim_date.is_complete_data_month);

-- result: late_vs_on_time
select
    case when is_late_delivery then 'late' else 'on time' end as delivery_outcome,
    count(*) as reviewed_deliveries,
    count(*) filter (where is_bad) as bad_reviews,
    round(100.0 * bad_reviews / reviewed_deliveries, 2) as bad_review_rate_pct,
    round(100 * wilson_low(bad_reviews::double, reviewed_deliveries), 2) as ci_low_pct,
    round(100 * wilson_high(bad_reviews::double, reviewed_deliveries), 2) as ci_high_pct,
    round(avg(review_score), 2) as avg_review_score

from q1_population
group by is_late_delivery
order by delivery_outcome desc;

-- result: by_delay
select
    case
        when delivery_delay_days <= -15 then 1
        when delivery_delay_days <= -8 then 2
        when delivery_delay_days <= -1 then 3
        when delivery_delay_days = 0 then 4
        when delivery_delay_days <= 3 then 5
        when delivery_delay_days <= 7 then 6
        when delivery_delay_days <= 14 then 7
        else 8
    end as bucket_order,
    case bucket_order
        when 1 then '15+ days early' when 2 then '8-14 days early' when 3 then '1-7 days early'
        when 4 then 'on the estimated day' when 5 then '1-3 days late' when 6 then '4-7 days late'
        when 7 then '8-14 days late' else '15+ days late'
    end as delay_bucket,
    count(*) as reviewed_deliveries,
    count(*) filter (where is_bad) as bad_reviews,
    round(100.0 * bad_reviews / reviewed_deliveries, 2) as bad_review_rate_pct,
    round(100 * wilson_low(bad_reviews::double, reviewed_deliveries), 2) as ci_low_pct,
    round(100 * wilson_high(bad_reviews::double, reviewed_deliveries), 2) as ci_high_pct

from q1_population
group by bucket_order
order by bucket_order;

-- result: by_state
with

national as (

    select
        count(*) filter (where is_bad and is_late_delivery) / count(*) filter (where is_late_delivery) as bad_rate_late,
        count(*) filter (where is_bad and not is_late_delivery) / count(*) filter (where not is_late_delivery) as bad_rate_on_time

    from q1_population

),

states as (

    select
        delivery_state,
        any_value(delivery_region) as delivery_region,
        count(*) as reviewed_deliveries,
        avg(delivery_days) as avg_delivery_days,
        median(delivery_days) as median_delivery_days,
        avg(is_late_delivery::int) as late_share,
        count(*) filter (where is_bad) as bad_reviews,
        count(*) filter (where is_bad and not is_late_delivery)
            / nullif(count(*) filter (where not is_late_delivery), 0) as bad_rate_on_time

    from q1_population
    group by delivery_state

)

select
    states.delivery_state,
    states.delivery_region,
    states.reviewed_deliveries,
    round(states.avg_delivery_days, 1) as avg_delivery_days,
    states.median_delivery_days,
    round(100 * states.late_share, 2) as late_rate_pct,
    round(100.0 * states.bad_reviews / states.reviewed_deliveries, 2) as bad_review_rate_pct,
    round(100 * wilson_low(states.bad_reviews::double, states.reviewed_deliveries), 2) as ci_low_pct,
    round(100 * wilson_high(states.bad_reviews::double, states.reviewed_deliveries), 2) as ci_high_pct,
    round(100 * states.bad_rate_on_time, 2) as bad_review_rate_on_time_pct,
    -- what the state's bad-review rate would be if only its late share differed from the nation
    round(100 * (states.late_share * national.bad_rate_late + (1 - states.late_share) * national.bad_rate_on_time), 2)
        as expected_bad_review_rate_pct,
    round(bad_review_rate_pct - expected_bad_review_rate_pct, 2) as excess_vs_expected_pp

from states
cross join national
where states.reviewed_deliveries >= getvariable('min_orders_per_state')
order by late_rate_pct desc;

-- result: state_correlation
with

states as (

    select
        delivery_state,
        count(*) as reviewed_deliveries,
        avg(is_late_delivery::int) as late_share,
        avg(is_bad::int) as bad_share,
        avg(delivery_days) as avg_delivery_days

    from q1_population
    group by delivery_state
    having count(*) >= getvariable('min_orders_per_state')

)

select
    count(*) as states_included,
    sum(reviewed_deliveries) as reviewed_deliveries,
    round(corr(late_share, bad_share), 3) as corr_late_rate_vs_bad_review_rate,
    round(corr(late_share, bad_share) ^ 2, 3) as r_squared_late_rate,
    round(corr(avg_delivery_days, bad_share), 3) as corr_avg_days_vs_bad_review_rate,
    round(100 * regr_slope(bad_share, late_share), 1) as bad_review_pp_per_100pp_late

from states;
