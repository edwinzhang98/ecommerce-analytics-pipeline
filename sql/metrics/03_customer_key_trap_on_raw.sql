-- =====================================================================================
-- The customer-key trap (DQ-01), reproduced on the raw tables
-- Purpose : Olist issues a new customer_id for every order. Counting repeat customers on
--           customer_id says nobody ever comes back; on customer_unique_id (the person) the
--           answer is 2-3%. This is why the marts expose only customer_unique_id.
-- Inputs  : raw.orders, raw.customers
-- Output  : one row per key with customers, customers with 2+ net orders and the repeat rate
-- Run     : uv run python scripts/run_sql.py sql/metrics/03_customer_key_trap_on_raw.sql
-- =====================================================================================

-- result: repeat_rate_by_key
with

net_orders as (

    select orders.order_id, orders.customer_id, customers.customer_unique_id
    from raw.orders as orders
    inner join raw.customers as customers
        on orders.customer_id = customers.customer_id
    where orders.order_status not in ('canceled', 'unavailable')

),

by_customer_id as (

    select customer_id, count(*) as orders from net_orders group by customer_id

),

by_person as (

    select customer_unique_id, count(*) as orders from net_orders group by customer_unique_id

)

select
    'customer_id (issued per order)' as key_used,
    count(*) as customers,
    count(*) filter (where orders >= 2) as customers_with_2plus_orders,
    round(100.0 * count(*) filter (where orders >= 2) / count(*), 2) as repeat_rate_pct
from by_customer_id
union all
select
    'customer_unique_id (the person)',
    count(*),
    count(*) filter (where orders >= 2),
    round(100.0 * count(*) filter (where orders >= 2) / count(*), 2)
from by_person;
