{#
    fct_order_items — one row per unit sold (order line). Incremental (ADR 0005).

    What each run processes (delete+insert on order_item_key):
      1. new orders: purchased since the newest purchase already loaded, minus a
         `fct_order_items_lookback_days` safety window for rows that land a little late;
      2. every order that was still OPEN at the last run (status not terminal per the
         order_status_mapping seed), because its status, and so `is_net_order`, may have changed.
    Item attributes (price, freight, product, seller, shipping limit) never change after purchase,
    and terminal statuses (delivered, canceled, unavailable) never change by definition, so rows
    outside 1 and 2 cannot be stale.

    Known limit: a row that arrives more than the lookback window after newer purchases were loaded
    is skipped. The grain test fct_order_items_has_one_row_per_source_item then fails, and the fix
    is `dbt build --full-refresh -s fct_order_items` (proved in scripts/check_incremental.py).
#}

-- the seed is only referenced inside the incremental branch, so declare the dependency:
-- depends_on: {{ ref('order_status_mapping') }}

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
        order_purchase_date,
        order_status,
        is_net_order

    from {{ ref('int_orders_joined') }}

    {% if is_incremental() %}
    where
        order_purchased_at >= (
            select max(order_purchased_at) - interval '{{ var("fct_order_items_lookback_days") }} days'
            from {{ this }}
        )
        or order_id in (
            select loaded.order_id
            from {{ this }} as loaded
            inner join {{ ref('order_status_mapping') }} as status_mapping
                on loaded.order_status = status_mapping.order_status
            where not status_mapping.is_terminal_status
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

        -- order status, so item-level sums can be restricted to net orders without a join
        cast(orders.order_status as varchar) as order_status,
        cast(orders.is_net_order as boolean) as is_net_order,

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
