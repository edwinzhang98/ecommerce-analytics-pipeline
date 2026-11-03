with

source as (

    select * from {{ source('olist', 'order_items') }}

),

renamed as (

    select
        -- ids
        {{ dbt_utils.generate_surrogate_key(['order_id', 'order_item_id']) }} as order_item_key,
        order_id,
        cast(order_item_id as integer) as order_item_id,
        product_id,
        seller_id,

        -- timestamps (naive local time, America/Sao_Paulo)
        cast(shipping_limit_date as timestamp) as shipping_limit_at,

        -- amounts (BRL). One row is one unit: quantity is implicit in the row count.
        cast(price as decimal(10, 2)) as item_price_brl,
        cast(freight_value as decimal(10, 2)) as freight_value_brl,

        -- metadata
        _loaded_at

    from source

)

select * from renamed
