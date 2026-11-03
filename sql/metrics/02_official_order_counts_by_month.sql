-- =====================================================================================
-- Official order counts and GMV by month, from the marts
-- Purpose : the three named order metrics side by side, on the agreed date basis
--           (local purchase date). This is the query behind the monthly business review.
-- Inputs  : marts.fct_orders, marts.dim_date
-- Output  : one row per month: placed / net / delivered orders, net GMV, AOV, complete-month flag
-- Run     : uv run python scripts/run_sql.py sql/metrics/02_official_order_counts_by_month.sql
-- =====================================================================================

-- result: monthly_order_metrics
select
    dim_date.year_month,
    bool_and(dim_date.is_complete_data_month) as is_complete_data_month,
    count(fct_orders.order_id) as placed_orders,
    count(fct_orders.order_id) filter (where fct_orders.is_net_order) as net_orders,
    count(fct_orders.order_id) filter (where fct_orders.is_delivered) as delivered_orders,
    coalesce(sum(fct_orders.order_gmv_brl) filter (where fct_orders.is_net_order), 0) as net_gmv_brl,
    round(
        sum(fct_orders.order_gmv_brl) filter (where fct_orders.is_net_order)
        / nullif(count(fct_orders.order_id) filter (where fct_orders.is_net_order), 0), 2
    ) as avg_order_value_brl

from marts.dim_date as dim_date
left join marts.fct_orders as fct_orders
    on dim_date.date_day = fct_orders.order_purchase_date
where dim_date.date_day between date '2016-09-01' and date '2018-10-31'
group by dim_date.year_month
order by dim_date.year_month;

-- result: totals
select
    count(*) as placed_orders,
    count(*) filter (where is_net_order) as net_orders,
    count(*) filter (where is_delivered) as delivered_orders,
    sum(order_gmv_brl) filter (where is_net_order) as net_gmv_brl

from marts.fct_orders;
