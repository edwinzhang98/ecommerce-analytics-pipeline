{#
    dim_sellers — one row per seller with cleaned location and coordinates. When the seller's
    own city value is unusable, the city is inferred from the zip prefix (flagged).
    Performance metrics live in seller_scorecard (marts/business).
#}

with

sellers as (

    select * from {{ ref('stg_olist__sellers') }}

),

geolocation as (

    select * from {{ ref('int_geolocation_aggregated_to_zip_prefixes') }}

),

states as (

    select * from {{ ref('brazil_states') }}

),

final as (

    select
        cast(sellers.seller_id as varchar) as seller_id,
        cast(sellers.seller_zip_code_prefix as varchar) as seller_zip_code_prefix,
        -- 7 sellers typed something that is not a city (a zip code, an e-mail, "sp"):
        -- fall back to the most common city of their zip prefix
        cast(coalesce(sellers.seller_city, geolocation.city) as varchar) as seller_city,
        cast(sellers.seller_city is null and geolocation.city is not null as boolean)
            as is_city_inferred_from_zip,
        cast(sellers.seller_state as varchar) as seller_state,
        cast(states.state_name as varchar) as seller_state_name,
        cast(states.region_name as varchar) as seller_region,
        cast(geolocation.latitude as double) as seller_latitude,
        cast(geolocation.longitude as double) as seller_longitude

    from sellers
    left join geolocation
        on sellers.seller_zip_code_prefix = geolocation.zip_code_prefix
    left join states
        on sellers.seller_state = states.state_code

)

select * from final
