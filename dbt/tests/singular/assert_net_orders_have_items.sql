{#
    DQ-08 baseline: a net order (not canceled / unavailable) should contain at least one item.
    8 net orders in the source do not (5 created, 2 invoiced, 1 shipped). They stay in fct_orders
    with GMV 0 and the `no_items` flag.
#}

{{
    config(
        warn_if='>8',
        error_if='>100',
        store_failures=true,
        tags=['known_issue'],
        meta={'dq_issue': 'DQ-08'}
    )
}}

select
    order_id,
    order_status,
    order_purchased_at

from {{ ref('fct_orders') }}
where is_net_order
    and not has_items
