-- =====================================================================================
-- Why three analysts got three different order counts (reproduced on the raw tables)
-- Purpose : the diagnosis behind docs/01_request_and_scope.md. Each query is a plausible thing
--           an analyst would write against raw; each answers a different question.
-- Inputs  : raw.orders, raw.order_items, raw.order_payments
-- Output  : result `order_counts`: one row per approach, with the "orders" it reports and the
--           revenue the same query would report
-- Run     : uv run python scripts/run_sql.py sql/metrics/01_three_analysts_on_raw.sql
-- =====================================================================================

-- result: order_counts
select
    'A' as analyst,
    'Finance: count(*) after joining orders -> order_items -> order_payments' as query,
    (select count(*) from raw.orders
        inner join raw.order_items using (order_id)
        inner join raw.order_payments using (order_id)) as orders_reported,
    (select sum(payment_value::decimal(10, 2)) from raw.orders
        inner join raw.order_items using (order_id)
        inner join raw.order_payments using (order_id)) as revenue_reported_brl,
    'Fan-out: an order with 3 items and 2 payments becomes 6 rows, so orders and revenue are double counted' as why_it_differs

union all

select
    'B',
    'Ops: count(*) from orders',
    (select count(*) from raw.orders),
    (select sum(payment_value::decimal(10, 2)) from raw.order_payments),
    'Counts every status, including canceled and unavailable orders'

union all

select
    'C',
    'Marketing: count(*) from orders where order_status = ''delivered''',
    (select count(*) from raw.orders where order_status = 'delivered'),
    (select sum(payment_value::decimal(10, 2)) from raw.order_payments
        where order_id in (select order_id from raw.orders where order_status = 'delivered')),
    'Only delivered orders: a valid metric, but a different one under the same name'

union all

select
    'Official',
    'Net orders: count(*) from orders where status not in (canceled, unavailable)',
    (select count(*) from raw.orders where order_status not in ('canceled', 'unavailable')),
    (select sum(price::decimal(10, 2) + freight_value::decimal(10, 2)) from raw.order_items
        where order_id in (select order_id from raw.orders where order_status not in ('canceled', 'unavailable'))),
    'The agreed definition (ADR 0002). Revenue = GMV of net orders (items + freight).'
;
