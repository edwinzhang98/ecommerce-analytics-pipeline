{#
    Grain: one row per distinct (zip prefix, latitude, longitude, city, state) after cleaning.
    The raw file has ~1M rows for ~19k zip prefixes, with exact duplicates and spelling
    variants of the same city, so it is de-duplicated here and aggregated to one row per
    zip prefix in int_geolocation_aggregated_to_zip_prefixes.
#}

with

source as (

    select * from {{ source('olist', 'geolocation') }}

),

renamed as (

    select
        lpad(trim(geolocation_zip_code_prefix), 5, '0') as zip_code_prefix,
        cast(geolocation_lat as double) as latitude,
        cast(geolocation_lng as double) as longitude,
        {{ clean_city_name('geolocation_city') }} as city,
        upper(trim(geolocation_state)) as state_code

    from source

),

deduplicated as (

    select distinct * from renamed

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['zip_code_prefix', 'latitude', 'longitude', 'city', 'state_code']) }}
            as geolocation_key,
        zip_code_prefix,
        latitude,
        longitude,
        city,
        state_code,
        {{ is_within_brazil('latitude', 'longitude') }} as is_within_brazil

    from deduplicated

)

select * from final
