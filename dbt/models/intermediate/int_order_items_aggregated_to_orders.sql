{#
    Order items rolled up to one row per order, so they can be joined to orders
    without fanning out (ADR 0003). Only orders that have at least one item appear here.
#}

with

order_items as (

    select * from {{ ref('stg_olist__order_items') }}

),

aggregated as (

    select
        order_id,
        count(*) as item_count,
        count(distinct product_id) as distinct_product_count,
        count(distinct seller_id) as distinct_seller_count,
        sum(item_price_brl) as items_subtotal_brl,
        sum(freight_value_brl) as freight_total_brl,
        sum(item_price_brl + freight_value_brl) as order_gmv_brl,
        min(shipping_limit_at) as first_shipping_limit_at

    from order_items
    group by order_id

)

select * from aggregated
