{#
    fct_order_items — one row per unit sold (order line). Incremental (ADR 0005).

    Why this model is incremental: an item row never changes after the order is placed
    (price, freight, product, seller, shipping limit are fixed at purchase), so only new
    orders need processing. Mutable order state (status, delivery, review) deliberately
    lives in fct_orders, which is rebuilt in full on every run.

    Each run re-processes the last `fct_order_items_lookback_days` days before the newest
    purchase already loaded, to pick up rows that arrive late; `unique_key` +
    delete+insert make the re-processing idempotent.
#}

{{
    config(
        materialized='incremental',
        unique_key='order_item_key',
        incremental_strategy='delete+insert',
        on_schema_change='fail'
    )
}}

with

order_items as (

    select * from {{ ref('stg_olist__order_items') }}

),

orders as (

    select
        order_id,
        customer_unique_id,
        order_purchased_at,
        order_purchase_date

    from {{ ref('int_orders_joined') }}

    {% if is_incremental() %}
    where order_purchased_at >= (
        select max(order_purchased_at) - interval '{{ var("fct_order_items_lookback_days") }} days'
        from {{ this }}
    )
    {% endif %}

),

final as (

    select
        -- keys
        cast(order_items.order_item_key as varchar) as order_item_key,
        cast(order_items.order_id as varchar) as order_id,
        cast(order_items.order_item_id as integer) as order_item_id,
        cast(order_items.product_id as varchar) as product_id,
        cast(order_items.seller_id as varchar) as seller_id,
        cast(orders.customer_unique_id as varchar) as customer_unique_id,
        cast(orders.order_purchase_date as date) as order_purchase_date,

        -- timestamps (local time, America/Sao_Paulo)
        cast(orders.order_purchased_at as timestamp) as order_purchased_at,
        cast(order_items.shipping_limit_at as timestamp) as shipping_limit_at,

        -- amounts (BRL)
        cast(order_items.item_price_brl as decimal(18, 2)) as item_price_brl,
        cast(order_items.freight_value_brl as decimal(18, 2)) as freight_value_brl,
        cast(order_items.item_price_brl + order_items.freight_value_brl as decimal(18, 2))
            as item_total_brl

    from order_items
    inner join orders
        on order_items.order_id = orders.order_id

)

select * from final
