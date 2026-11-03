{#
    One row per person (customer_unique_id). In the source, customer_id is issued per order,
    so 96,096 people appear under 99,441 customer_ids (ADR 0003).
      * address: from the person's most recent net order (or most recent order if none)
      * order history: placed / net orders, purchase days, GMV (net orders only)
#}

with

customers as (

    select * from {{ ref('stg_olist__customers') }}

),

orders as (

    select * from {{ ref('int_orders_joined') }}

),

address_ranked as (

    select
        customers.customer_unique_id,
        customers.customer_zip_code_prefix,
        customers.customer_city,
        customers.customer_state,
        -- prefer the most recent net order: a canceled order's address should not win
        row_number() over (
            partition by customers.customer_unique_id
            order by orders.is_net_order desc, orders.order_purchased_at desc, orders.order_id
        ) as recency_rank

    from customers
    inner join orders
        on customers.customer_id = orders.customer_id

),

latest_address as (

    select * exclude (recency_rank)
    from address_ranked
    where recency_rank = 1

),

order_history as (

    select
        customer_unique_id,
        count(*) as orders_placed,
        min(order_purchased_at) as first_order_at,
        count(*) filter (where is_net_order) as frequency_orders,
        count(distinct order_purchase_date) filter (where is_net_order) as purchase_days,
        min(order_purchased_at) filter (where is_net_order) as first_net_order_at,
        max(order_purchased_at) filter (where is_net_order) as last_net_order_at,
        coalesce(sum(order_gmv_brl) filter (where is_net_order), 0) as monetary_gmv_brl

    from orders
    group by customer_unique_id

),

final as (

    select
        latest_address.customer_unique_id,
        latest_address.customer_zip_code_prefix,
        latest_address.customer_city,
        latest_address.customer_state,
        order_history.orders_placed,
        order_history.first_order_at,
        order_history.frequency_orders,
        order_history.purchase_days,
        order_history.first_net_order_at,
        order_history.last_net_order_at,
        order_history.monetary_gmv_brl

    from latest_address
    inner join order_history
        on latest_address.customer_unique_id = order_history.customer_unique_id

)

select * from final
