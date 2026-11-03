with

source as (

    select * from {{ source('olist', 'sellers') }}

),

renamed as (

    select
        -- ids
        seller_id,

        -- location. seller_city is typed by sellers; see macros/clean_city_name.sql
        lpad(trim(seller_zip_code_prefix), 5, '0') as seller_zip_code_prefix,
        {{ clean_city_name('seller_city') }} as seller_city,
        upper(trim(seller_state)) as seller_state,

        -- metadata
        _loaded_at

    from source

)

select * from renamed
