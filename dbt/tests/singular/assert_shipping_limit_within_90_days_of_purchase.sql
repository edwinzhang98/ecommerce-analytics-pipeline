{#
    DQ-12 baseline: the seller's shipping deadline is normally a few days after purchase.
    8 items (7 orders) in the source have a deadline more than 90 days after the purchase,
    4 of them about three years later (in 2020). Kept; monitored.
#}

{{
    config(
        warn_if='>8',
        error_if='>100',
        store_failures=true,
        tags=['known_issue'],
        meta={'dq_issue': 'DQ-12'}
    )
}}

select
    order_items.order_id,
    order_items.order_item_id,
    orders.order_purchased_at,
    order_items.shipping_limit_at,
    date_diff('day', orders.order_purchased_at, order_items.shipping_limit_at) as days_after_purchase

from {{ ref('stg_olist__order_items') }} as order_items
inner join {{ ref('stg_olist__orders') }} as orders
    on order_items.order_id = orders.order_id
where order_items.shipping_limit_at > orders.order_purchased_at + interval 90 day
