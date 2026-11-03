{#
    Coverage guard (DQ-15): every month flagged as complete in dim_date must have a plausible
    volume of net orders. Catches a partial extract or a broken date join before it reaches a
    trend chart. Threshold: var `min_net_orders_per_complete_month` (default 500; the smallest
    complete month, 2017-01, has ~790).
#}

with

monthly as (

    select
        dim_date.year_month,
        count(fct_orders.order_id) filter (where fct_orders.is_valid_order) as net_orders

    from {{ ref('dim_date') }} as dim_date
    left join {{ ref('fct_orders') }} as fct_orders
        on dim_date.date_day = fct_orders.order_purchase_date
    where dim_date.is_complete_data_month
    group by dim_date.year_month

)

select *
from monthly
where net_orders < {{ var('min_net_orders_per_complete_month') }}
