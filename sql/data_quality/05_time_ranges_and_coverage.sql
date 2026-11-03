-- =====================================================================================
-- 05 Time ranges of every timestamp, and monthly order coverage
-- Purpose : what period the extract really covers, and which months are incomplete.
-- Inputs  : raw.orders, raw.order_items, raw.order_reviews
-- Output  : result 1 `time_ranges`: one row per timestamp column (min, max, nulls)
--           result 2 `monthly_coverage`: orders per purchase month, all months in range
-- Run     : uv run python scripts/run_sql.py sql/data_quality/05_time_ranges_and_coverage.sql
-- =====================================================================================

-- result: time_ranges
with

stamps as (

    select 'orders.order_purchase_timestamp' as column_name, order_purchase_timestamp::timestamp as ts from raw.orders
    union all select 'orders.order_approved_at', order_approved_at::timestamp from raw.orders
    union all select 'orders.order_delivered_carrier_date', order_delivered_carrier_date::timestamp from raw.orders
    union all select 'orders.order_delivered_customer_date', order_delivered_customer_date::timestamp from raw.orders
    union all select 'orders.order_estimated_delivery_date', order_estimated_delivery_date::timestamp from raw.orders
    union all select 'order_items.shipping_limit_date', shipping_limit_date::timestamp from raw.order_items
    union all select 'order_reviews.review_creation_date', review_creation_date::timestamp from raw.order_reviews
    union all select 'order_reviews.review_answer_timestamp', review_answer_timestamp::timestamp from raw.order_reviews

)

select
    column_name,
    min(ts) as first_value,
    max(ts) as last_value,
    count(*) - count(ts) as null_count

from stamps
group by column_name
order by column_name;

-- result: monthly_coverage
with

months as (

    select unnest(generate_series(date '2016-09-01', date '2018-10-01', interval 1 month))::date as month_start

),

orders as (

    select
        date_trunc('month', order_purchase_timestamp::timestamp)::date as month_start,
        count(*) as orders_placed,
        count(*) filter (where order_status not in ('canceled', 'unavailable')) as net_orders

    from raw.orders
    group by 1

)

select
    strftime(months.month_start, '%Y-%m') as year_month,
    coalesce(orders.orders_placed, 0) as orders_placed,
    coalesce(orders.net_orders, 0) as net_orders,
    coalesce(orders.orders_placed, 0) < 100 as is_sparse_month

from months
left join orders
    on months.month_start = orders.month_start
order by year_month;
