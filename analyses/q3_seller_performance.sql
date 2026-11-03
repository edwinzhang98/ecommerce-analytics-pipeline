-- =====================================================================================
-- Q3. How concentrated is GMV across sellers, and how do sellers differ on fulfilment and reviews?
-- Decision : which sellers the seller-management team should work with first.
-- Inputs   : marts.seller_scorecard, marts.fct_orders, marts.fct_order_items
-- Output   : gmv_concentration     - share of GMV held by the top 1/5/10/20/50% of sellers
--            pareto_curve          - cumulative GMV share by seller rank (for the chart)
--            handover_vs_outcome   - single-seller orders the seller handed to the carrier late vs
--                                    on time: late-delivery and bad-review rates
--            seller_quadrants      - established sellers split by late-handover and bad-review rates
--            watchlist             - largest sellers in the "late handover AND bad reviews" quadrant
-- Parameters: min_seller_orders (50), late_handover_threshold_pct (15), bad_review_threshold_pct (20)
-- Caveat   : order-level outcomes are attributed to every seller in multi-seller orders (1.3%).
-- Run      : uv run python scripts/run_sql.py analyses/q3_seller_performance.sql
-- =====================================================================================

set variable min_seller_orders = 50;
set variable late_handover_threshold_pct = 15;
set variable bad_review_threshold_pct = 20;

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

-- result: gmv_concentration
with

active as (

    select * from marts.seller_scorecard
    where net_orders > 0

),

tiers as (

    select unnest([1, 5, 10, 20, 50]) as top_pct_of_sellers

)

select
    tiers.top_pct_of_sellers,
    cast(ceil((select count(*) from active) * tiers.top_pct_of_sellers / 100.0) as integer) as sellers,
    round(100 * max(active.cumulative_gmv_share), 1) as gmv_share_pct

from tiers
inner join active
    on active.gmv_rank <= ceil((select count(*) from active) * tiers.top_pct_of_sellers / 100.0)
group by tiers.top_pct_of_sellers
order by tiers.top_pct_of_sellers;

-- result: pareto_curve
select
    gmv_rank,
    round(100.0 * gmv_rank / count(*) over (), 3) as seller_share_pct,
    round(100 * cumulative_gmv_share, 3) as cumulative_gmv_share_pct

from marts.seller_scorecard
where net_orders > 0
order by gmv_rank;

-- result: handover_vs_outcome
with

shipping_limits as (

    select order_id, min(shipping_limit_at) as shipping_limit_at
    from marts.fct_order_items
    group by order_id

),

orders as (

    select
        fct_orders.order_id,
        fct_orders.order_delivered_to_carrier_at > shipping_limits.shipping_limit_at as is_late_handover,
        fct_orders.is_late_delivery,
        fct_orders.has_review,
        fct_orders.is_bad_review,
        fct_orders.delivery_days

    from marts.fct_orders as fct_orders
    inner join shipping_limits
        on fct_orders.order_id = shipping_limits.order_id
    where fct_orders.is_late_delivery is not null
        and fct_orders.order_delivered_to_carrier_at is not null
        -- one carrier timestamp per order: only single-seller orders have an unambiguous SLA
        and fct_orders.distinct_seller_count = 1

)

select
    case when is_late_handover then 'seller handed over late' else 'seller handed over on time' end as handover,
    count(*) as delivered_orders,
    round(100.0 * count(*) / sum(count(*)) over (), 1) as share_of_orders_pct,
    count(*) filter (where is_late_delivery) as late_deliveries,
    round(100.0 * late_deliveries / delivered_orders, 2) as late_delivery_rate_pct,
    round(100 * wilson_low(late_deliveries::double, delivered_orders), 2) as late_ci_low_pct,
    round(100 * wilson_high(late_deliveries::double, delivered_orders), 2) as late_ci_high_pct,
    round(100.0 * count(*) filter (where is_bad_review) / count(*) filter (where has_review), 2) as bad_review_rate_pct,
    round(avg(delivery_days), 1) as avg_delivery_days

from orders
group by is_late_handover
order by handover;

-- result: seller_quadrants
with

established as (

    select
        *,
        100 * late_handover_rate > getvariable('late_handover_threshold_pct') as is_slow_handover,
        100 * bad_review_rate > getvariable('bad_review_threshold_pct') as is_poorly_reviewed

    from marts.seller_scorecard
    where net_orders >= getvariable('min_seller_orders')

)

select
    case
        when is_slow_handover and is_poorly_reviewed then '1. late handover AND bad reviews'
        when is_slow_handover then '2. late handover only'
        when is_poorly_reviewed then '3. bad reviews only'
        else '4. healthy'
    end as quadrant,
    count(*) as sellers,
    sum(net_orders) as net_orders,
    sum(gmv_brl) as gmv_brl,
    round(100.0 * sum(gmv_brl) / (select sum(gmv_brl) from marts.seller_scorecard), 1) as share_of_marketplace_gmv_pct,
    round(100 * avg(late_handover_rate), 1) as avg_late_handover_rate_pct,
    round(100 * avg(bad_review_rate), 1) as avg_bad_review_rate_pct

from established
group by quadrant
order by quadrant;

-- result: watchlist
select
    seller_id,
    seller_state,
    top_category,
    net_orders,
    gmv_brl,
    gmv_rank,
    round(100 * late_handover_rate, 1) as late_handover_rate_pct,
    round(100 * late_delivery_rate, 1) as late_delivery_rate_pct,
    round(100 * bad_review_rate, 1) as bad_review_rate_pct,
    round(avg_review_score, 2) as avg_review_score

from marts.seller_scorecard
where net_orders >= getvariable('min_seller_orders')
    and 100 * late_handover_rate > getvariable('late_handover_threshold_pct')
    and 100 * bad_review_rate > getvariable('bad_review_threshold_pct')
order by gmv_brl desc
limit 15;
