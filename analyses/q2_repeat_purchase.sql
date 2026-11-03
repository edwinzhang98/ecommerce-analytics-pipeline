-- =====================================================================================
-- Q2. What share of customers buy again, and how quickly?
-- Decision : whether retention (CRM) or acquisition should get the next marketing euro, and
--            which first-order experiences go with lower repurchase (CRM manager).
-- Inputs   : marts.fct_orders, marts.customer_360
-- Output   : definition_sensitivity     - repeat rate under 3 definitions (why the official one;
--                                         the per-order customer_id trap is shown on raw in
--                                         sql/metrics/03_customer_key_trap_on_raw.sql)
--            time_to_second_purchase    - how long repeaters take to come back
--            cohort_repeat              - repurchase within N days by first-purchase month,
--                                         only for cohorts observed for the full N days
--            repeat_by_first_experience - repurchase within N days by how the first order went
-- Parameters: repeat_window_days (default 180)
-- Official definition: a repeat customer bought on 2+ different days (net orders).
-- Run      : uv run python scripts/run_sql.py analyses/q2_repeat_purchase.sql --var repeat_window_days=90
-- =====================================================================================

set variable repeat_window_days = 180;

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

-- result: definition_sensitivity
with

net_orders as (

    select * from marts.fct_orders
    where is_net_order

),

by_person as (

    select
        count(*) as n_orders,
        count(distinct order_purchased_at) as n_checkouts,
        count(distinct order_purchase_date) as n_purchase_days

    from net_orders
    group by customer_unique_id

)

select
    1 as sort_order,
    'person with 2+ net orders' as definition,
    count(*) as customers,
    count(*) filter (where n_orders >= 2) as repeat_customers,
    round(100.0 * repeat_customers / customers, 2) as repeat_rate_pct
from by_person
union all
select 2, 'person with 2+ checkouts (distinct purchase timestamps)', count(*),
    count(*) filter (where n_checkouts >= 2), round(100.0 * count(*) filter (where n_checkouts >= 2) / count(*), 2)
from by_person
union all
select 3, 'person with 2+ purchase days (official)', count(*),
    count(*) filter (where n_purchase_days >= 2), round(100.0 * count(*) filter (where n_purchase_days >= 2) / count(*), 2)
from by_person
order by sort_order;

-- result: time_to_second_purchase
select
    case
        when days_to_second_purchase <= 7 then 1
        when days_to_second_purchase <= 30 then 2
        when days_to_second_purchase <= 90 then 3
        when days_to_second_purchase <= 180 then 4
        when days_to_second_purchase <= 365 then 5
        else 6
    end as bucket_order,
    case bucket_order
        when 1 then '1-7 days' when 2 then '8-30 days' when 3 then '31-90 days'
        when 4 then '91-180 days' when 5 then '181-365 days' else 'over 365 days'
    end as time_to_second_purchase,
    count(*) as repeat_customers,
    round(100.0 * count(*) / sum(count(*)) over (), 1) as share_pct,
    round(100.0 * sum(count(*)) over (order by bucket_order) / sum(count(*)) over (), 1) as cumulative_share_pct,
    (select median(days_to_second_purchase) from marts.customer_360) as median_days_all_repeaters

from marts.customer_360
where days_to_second_purchase is not null
group by bucket_order
order by bucket_order;

-- result: cohort_repeat
with

customers as (

    select
        customer_unique_id,
        first_net_order_month,
        cast(first_net_order_at as date) as first_purchase_date,
        days_to_second_purchase,
        rfm_reference_date

    from marts.customer_360
    where has_net_order

),

cohorts as (

    select
        strftime(first_net_order_month, '%Y-%m') as cohort_month,
        count(*) as customers,
        count(*) filter (where days_to_second_purchase <= getvariable('repeat_window_days')) as repeat_customers,
        -- a cohort is fully observed when even its last customer had the whole window before the data ends
        max(first_purchase_date) + to_days(getvariable('repeat_window_days')) <= max(rfm_reference_date)
            as is_fully_observed

    from customers
    where first_net_order_month between date '2017-01-01' and date '2018-08-01'
    group by first_net_order_month

)

select
    cohort_month,
    customers,
    repeat_customers,
    round(100.0 * repeat_customers / customers, 2) as repeat_rate_pct,
    round(100 * wilson_low(repeat_customers::double, customers), 2) as ci_low_pct,
    round(100 * wilson_high(repeat_customers::double, customers), 2) as ci_high_pct,
    is_fully_observed

from cohorts
order by cohort_month;

-- result: repeat_by_first_experience
with

first_orders as (

    select
        customer_unique_id,
        order_purchase_date,
        is_late_delivery,
        has_review,
        is_bad_review,
        row_number() over (partition by customer_unique_id order by order_purchased_at, order_id) as order_number

    from marts.fct_orders
    where is_net_order

),

customers as (

    select
        first_orders.customer_unique_id,
        first_orders.is_late_delivery,
        first_orders.has_review,
        first_orders.is_bad_review,
        customer_360.days_to_second_purchase <= getvariable('repeat_window_days') as repurchased

    from first_orders
    inner join marts.customer_360 as customer_360
        on first_orders.customer_unique_id = customer_360.customer_unique_id
    where first_orders.order_number = 1
        -- only customers observed for the full window
        and first_orders.order_purchase_date + to_days(getvariable('repeat_window_days')) <= customer_360.rfm_reference_date

),

groups as (

    select 'first delivery' as dimension, case when is_late_delivery then 'late' else 'on time' end as first_order,
        count(*) as customers, count(*) filter (where repurchased) as repeat_customers
    from customers where is_late_delivery is not null group by 1, 2
    union all
    select 'first review', case when is_bad_review then 'bad (1-2 stars)' else 'not bad (3-5 stars)' end,
        count(*), count(*) filter (where repurchased)
    from customers where has_review group by 1, 2

)

select
    dimension,
    first_order,
    customers,
    repeat_customers,
    round(100.0 * repeat_customers / customers, 2) as repeat_rate_pct,
    round(100 * wilson_low(repeat_customers::double, customers), 2) as ci_low_pct,
    round(100 * wilson_high(repeat_customers::double, customers), 2) as ci_high_pct

from groups
order by dimension, first_order;
