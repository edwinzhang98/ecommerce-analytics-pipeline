{#
    DQ-09 baseline: a valid (not canceled / unavailable) order should contain at least one item.
    8 orders in the source do not (5 created, 2 invoiced, 1 shipped). They stay in fct_orders
    with GMV 0 and the `no_items` flag.
#}

{{
    config(
        warn_if='>8',
        error_if='>100',
        store_failures=true,
        tags=['known_issue'],
        meta={'dq_issue': 'DQ-09'}
    )
}}

select
    order_id,
    order_status,
    order_purchased_at

from {{ ref('fct_orders') }}
where is_valid_order
    and not has_items
