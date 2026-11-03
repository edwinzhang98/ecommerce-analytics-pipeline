{#
    Every product category must have an English name, either from the source translation
    table or from the product_category_translation_overrides seed. A new, untranslated
    category fails the build so it is added to the seed instead of leaking Portuguese
    labels into reports.
#}

with

translations as (

    select product_category_name from {{ ref('stg_olist__product_category_translation') }}
    union all
    select product_category_name from {{ ref('product_category_translation_overrides') }}

)

select distinct products.product_category_name

from {{ ref('stg_olist__products') }} as products
left join translations
    on products.product_category_name = translations.product_category_name
where products.product_category_name is not null
    and translations.product_category_name is null
