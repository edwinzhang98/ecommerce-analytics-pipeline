-- =====================================================================================
-- Q0. Do the three analysts now get the same order count?
-- Purpose : the acceptance test of the whole project. The three analysts' questions, answered
--           through the marts by different query paths, must return the same net order count.
--           (The same check runs in every `dbt build`:
--            dbt/tests/singular/assert_net_order_count_consistent_across_query_paths.sql)
-- Inputs  : marts.fct_orders, marts.fct_order_items, marts.dim_customers, marts.customer_360, marts.dim_date
-- Output  : result `query_paths`: one row per path with the net orders it returns
--           result `named_order_metrics`: the three official order metrics, which are allowed to differ
-- Run     : uv run python scripts/run_sql.py analyses/q0_order_count_reconciliation.sql
-- =====================================================================================

-- result: query_paths
select
    'A (finance)' as analyst,
    'fct_orders: net orders and net GMV in one table, no join needed' as query_path,
    count(*) as net_orders,
    sum(order_gmv_brl) as net_gmv_brl
from marts.fct_orders
where is_net_order

union all

select
    'A (finance), item level',
    'fct_order_items joined to fct_orders (many-to-one), count(distinct order_id) + net orders without items',
    (select count(distinct fct_order_items.order_id)
        from marts.fct_order_items as fct_order_items
        inner join marts.fct_orders as fct_orders on fct_order_items.order_id = fct_orders.order_id
        where fct_orders.is_net_order)
    + (select count(*) from marts.fct_orders where is_net_order and not has_items),
    (select sum(fct_order_items.item_total_brl)
        from marts.fct_order_items as fct_order_items
        inner join marts.fct_orders as fct_orders on fct_order_items.order_id = fct_orders.order_id
        where fct_orders.is_net_order)

union all

select
    'B (ops)',
    'fct_orders x dim_date, summed by month',
    sum(net_orders),
    sum(net_gmv_brl)
from (
    select dim_date.year_month, count(*) as net_orders, sum(fct_orders.order_gmv_brl) as net_gmv_brl
    from marts.fct_orders as fct_orders
    inner join marts.dim_date as dim_date on fct_orders.order_purchase_date = dim_date.date_day
    where fct_orders.is_net_order
    group by dim_date.year_month
)

union all

select
    'C (marketing)',
    'dim_customers: sum of frequency_orders over people',
    sum(frequency_orders),
    sum(monetary_gmv_brl)
from marts.dim_customers

union all

select
    'C (marketing), CRM table',
    'customer_360: sum of frequency_orders',
    sum(frequency_orders),
    sum(monetary_gmv_brl)
from marts.customer_360;

-- result: named_order_metrics
select 'placed orders' as metric, 'every order, any status' as definition, count(*) as orders
from marts.fct_orders
union all
select 'net orders (official KPI)', 'excludes canceled and unavailable', count(*) filter (where is_net_order)
from marts.fct_orders
union all
select 'delivered orders', 'status delivered', count(*) filter (where is_delivered)
from marts.fct_orders;
