with

source as (

    select * from {{ source('olist', 'orders') }}

),

renamed as (

    select
        -- ids
        order_id,
        customer_id,

        -- status
        lower(trim(order_status)) as order_status,

        -- timestamps: naive local time (America/Sao_Paulo), see docs/assumptions.md
        cast(order_purchase_timestamp as timestamp) as order_purchased_at,
        cast(order_approved_at as timestamp) as order_approved_at,
        cast(order_delivered_carrier_date as timestamp) as order_delivered_to_carrier_at,
        cast(order_delivered_customer_date as timestamp) as order_delivered_to_customer_at,

        -- the estimate is a calendar date in the source (time is always 00:00:00)
        cast(order_estimated_delivery_date as date) as order_estimated_delivery_date,

        -- metadata
        _loaded_at

    from source

)

select * from renamed
