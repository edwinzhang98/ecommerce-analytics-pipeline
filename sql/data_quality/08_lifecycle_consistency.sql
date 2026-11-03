-- =====================================================================================
-- 08 Order lifecycle consistency
-- Purpose : timestamps that contradict the lifecycle purchase -> approval -> carrier -> customer,
--           and statuses that contradict the timestamps.
-- Inputs  : raw.orders
-- Output  : one row per anomaly type with the number of orders
-- Run     : uv run python scripts/run_sql.py sql/data_quality/08_lifecycle_consistency.sql
-- =====================================================================================

-- result: lifecycle_anomalies
with

orders as (

    select
        order_status,
        order_purchase_timestamp::timestamp as purchased_at,
        order_approved_at::timestamp as approved_at,
        order_delivered_carrier_date::timestamp as carrier_at,
        order_delivered_customer_date::timestamp as delivered_at,
        order_estimated_delivery_date::timestamp as estimated_at

    from raw.orders

)

select 'approved before purchase' as anomaly, count(*) filter (where approved_at < purchased_at) as orders from orders
union all select 'carrier pickup before approval', count(*) filter (where carrier_at < approved_at) from orders
union all select 'carrier pickup before purchase', count(*) filter (where carrier_at < purchased_at) from orders
union all select 'delivered before carrier pickup', count(*) filter (where delivered_at < carrier_at) from orders
union all select 'delivered before approval', count(*) filter (where delivered_at < approved_at) from orders
union all select 'delivered before purchase', count(*) filter (where delivered_at < purchased_at) from orders
union all select 'estimate before purchase', count(*) filter (where estimated_at < purchased_at::date) from orders
union all select 'status delivered, no delivery time', count(*) filter (where order_status = 'delivered' and delivered_at is null) from orders
union all select 'status delivered, no approval time', count(*) filter (where order_status = 'delivered' and approved_at is null) from orders
union all select 'status canceled, has delivery time', count(*) filter (where order_status = 'canceled' and delivered_at is not null) from orders;
