with

source as (

    select * from {{ source('olist', 'customers') }}

),

renamed as (

    select
        -- ids: customer_id is issued per order; customer_unique_id identifies the person
        customer_id,
        customer_unique_id,

        -- location (zip prefixes keep their leading zeros as text)
        lpad(trim(customer_zip_code_prefix), 5, '0') as customer_zip_code_prefix,
        {{ clean_city_name('customer_city') }} as customer_city,
        upper(trim(customer_state)) as customer_state,

        -- metadata
        _loaded_at

    from source

)

select * from renamed
