with

source as (

    select * from {{ source('olist', 'order_payments') }}

),

renamed as (

    select
        -- ids
        {{ dbt_utils.generate_surrogate_key(['order_id', 'payment_sequential']) }} as payment_key,
        order_id,
        cast(payment_sequential as integer) as payment_sequential,

        -- payment details
        lower(trim(payment_type)) as payment_type,
        cast(payment_installments as integer) as payment_installments,

        -- amount (BRL). Card payments in installments can include interest, so the sum of
        -- payments can exceed items + freight (see docs/adr/0004).
        cast(payment_value as decimal(10, 2)) as payment_value_brl,

        -- metadata
        _loaded_at

    from source

)

select * from renamed
