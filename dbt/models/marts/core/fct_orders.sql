with

orders as (

    select * from {{ ref('stg_olist__orders') }}

),

final as (

    select
        order_id,
        customer_id,
        order_status,
        order_purchased_at,
        cast(order_purchased_at as date) as order_purchase_date
    from orders

)

select * from final
