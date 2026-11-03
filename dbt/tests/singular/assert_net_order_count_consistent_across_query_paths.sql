{#
    The original complaint, as a test: "three analysts got three different order counts".
    Six different ways of counting net orders must agree. Paths 1-5 go through the marts;
    path 6 skips every intermediate and mart model:
      1. fct_orders filtered on is_net_order (the documented way)
      2. the star join fct_orders x dim_customers x dim_date (proves the dimensions cannot fan out)
      3. monthly counts through dim_date, summed (proves no order falls outside the calendar)
      4. dim_customers.frequency_orders summed (built through the person-level aggregation)
      5. the item fact: distinct net orders in fct_order_items plus net orders that have no items
         (proves the item-level status flag agrees with the order level)
      6. straight from staging and the status seed, bypassing every intermediate and mart model
    If any join fanned out, or a model dropped or duplicated orders, the paths would disagree
    and the test returns every path with its count.
#}

{{ config(tags=['reconciliation']) }}

with

fct_orders as (

    select * from {{ ref('fct_orders') }}

),

paths as (

    select '1. fct_orders where is_net_order' as query_path, count(*) as net_orders
    from fct_orders
    where is_net_order

    union all

    select '2. star join fct_orders x dim_customers x dim_date', count(*)
    from fct_orders
    inner join {{ ref('dim_customers') }} as dim_customers
        on fct_orders.customer_unique_id = dim_customers.customer_unique_id
    inner join {{ ref('dim_date') }} as dim_date
        on fct_orders.order_purchase_date = dim_date.date_day
    where fct_orders.is_net_order

    union all

    select '3. monthly net orders via dim_date, summed', coalesce(sum(monthly_net_orders), 0)
    from (
        select dim_date.year_month, count(*) as monthly_net_orders
        from fct_orders
        inner join {{ ref('dim_date') }} as dim_date
            on fct_orders.order_purchase_date = dim_date.date_day
        where fct_orders.is_net_order
        group by dim_date.year_month
    )

    union all

    -- coalesce: an empty table must give 0 (and fail), not NULL (which count(distinct) would ignore)
    select '4. sum of dim_customers.frequency_orders', coalesce(sum(frequency_orders), 0)
    from {{ ref('dim_customers') }}

    union all

    select '5. distinct net orders in fct_order_items + net orders without items',
        (select count(distinct order_id) from {{ ref('fct_order_items') }} where is_net_order)
        + (select count(*) from fct_orders where is_net_order and not has_items)

    union all

    select '6. stg_olist__orders x order_status_mapping seed', count(*)
    from {{ ref('stg_olist__orders') }} as orders
    inner join {{ ref('order_status_mapping') }} as status_mapping
        on orders.order_status = status_mapping.order_status
    where status_mapping.is_net_order

)

select *
from paths
where (select count(distinct net_orders) from paths) > 1
