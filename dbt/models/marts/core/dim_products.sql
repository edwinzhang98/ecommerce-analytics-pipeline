{#
    dim_products — one row per product. Adds the English category: the source translation
    table plus a seed for the two categories it is missing; products without a category
    get 'unknown' so that group-bys never silently drop them.
#}

with

products as (

    select * from {{ ref('stg_olist__products') }}

),

translations as (

    select product_category_name, product_category_name_english
    from {{ ref('stg_olist__product_category_translation') }}

    union all

    select product_category_name, product_category_name_english
    from {{ ref('product_category_translation_overrides') }}

),

final as (

    select
        -- key
        cast(products.product_id as varchar) as product_id,

        -- category
        cast(products.product_category_name as varchar) as product_category_name,
        cast(
            coalesce(translations.product_category_name_english, products.product_category_name, 'unknown')
            as varchar
        ) as product_category,

        -- listing attributes
        cast(products.product_name_length as integer) as product_name_length,
        cast(products.product_description_length as integer) as product_description_length,
        cast(products.product_photos_count as integer) as product_photos_count,

        -- physical attributes
        cast(products.product_weight_g as integer) as product_weight_g,
        cast(products.product_length_cm as integer) as product_length_cm,
        cast(products.product_height_cm as integer) as product_height_cm,
        cast(products.product_width_cm as integer) as product_width_cm,
        cast(products.product_length_cm * products.product_height_cm * products.product_width_cm as integer)
            as product_volume_cm3,

        -- completeness
        cast(
            products.product_category_name is not null
            and coalesce(products.product_weight_g, 0) > 0
            and products.product_length_cm is not null
            and products.product_height_cm is not null
            and products.product_width_cm is not null
            as boolean
        ) as has_complete_attributes

    from products
    left join translations
        on products.product_category_name = translations.product_category_name

)

select * from final
