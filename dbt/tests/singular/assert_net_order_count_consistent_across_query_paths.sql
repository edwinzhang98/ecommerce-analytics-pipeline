{#
    The original complaint, as a test: "three analysts got three different order counts".
    Five different, documented ways of counting net orders from the marts must agree.
    If any join in the star schema fanned out, or a mart dropped or duplicated orders,
    the paths would disagree and this test would return every path with its count.
#}

{{ config(tags=['reconciliation']) }}

with

fct_orders as (

    select * from {{ ref('fct_orders') }}

),

paths as (

    select 'fct_orders where is_valid_order' as query_path, count(*) as net_orders
    from fct_orders
    where is_valid_order

    union all

    select 'star join fct_orders x dim_customers x dim_date', count(*)
    from fct_orders
    inner join {{ ref('dim_customers') }} as dim_customers
        on fct_orders.customer_unique_id = dim_customers.customer_unique_id
    inner join {{ ref('dim_date') }} as dim_date
        on fct_orders.order_purchase_date = dim_date.date_day
    where fct_orders.is_valid_order

    union all

    select 'sum of dim_customers.frequency_orders', sum(frequency_orders)
    from {{ ref('dim_customers') }}

    union all

    select 'sum of customer_360.frequency_orders', sum(frequency_orders)
    from {{ ref('customer_360') }}

    union all

    select 'sum of monthly net orders via dim_date', sum(monthly_net_orders)
    from (
        select dim_date.year_month, count(*) as monthly_net_orders
        from fct_orders
        inner join {{ ref('dim_date') }} as dim_date
            on fct_orders.order_purchase_date = dim_date.date_day
        where fct_orders.is_valid_order
        group by dim_date.year_month
    )

)

select *
from paths
where (select count(distinct net_orders) from paths) > 1
