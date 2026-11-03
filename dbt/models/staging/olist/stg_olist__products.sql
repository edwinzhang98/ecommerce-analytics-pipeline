with

source as (

    select * from {{ source('olist', 'products') }}

),

renamed as (

    select
        -- ids
        product_id,

        -- category (Portuguese source value; English translation is joined in dim_products)
        nullif(trim(product_category_name), '') as product_category_name,

        -- listing attributes (source columns are misspelled "lenght")
        cast(product_name_lenght as integer) as product_name_length,
        cast(product_description_lenght as integer) as product_description_length,
        cast(product_photos_qty as integer) as product_photos_count,

        -- physical attributes
        cast(product_weight_g as integer) as product_weight_g,
        cast(product_length_cm as integer) as product_length_cm,
        cast(product_height_cm as integer) as product_height_cm,
        cast(product_width_cm as integer) as product_width_cm,

        -- metadata
        _loaded_at

    from source

)

select * from renamed
