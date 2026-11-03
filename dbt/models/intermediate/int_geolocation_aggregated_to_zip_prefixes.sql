{#
    One row per zip code prefix: the median coordinate of the points that fall inside
    Brazil, and the most common (cleaned) city and state for that prefix.
    The median is robust to the stray points the raw file contains.
#}

with

geolocation as (

    select * from {{ ref('stg_olist__geolocation') }}
    where is_within_brazil

),

coordinates as (

    select
        zip_code_prefix,
        median(latitude) as latitude,
        median(longitude) as longitude,
        count(*) as point_count

    from geolocation
    group by zip_code_prefix

),

city_ranked as (

    select
        zip_code_prefix,
        city,
        state_code,
        row_number() over (
            partition by zip_code_prefix
            order by count(*) desc, city, state_code
        ) as frequency_rank

    from geolocation
    where city is not null
    group by zip_code_prefix, city, state_code

),

final as (

    select
        coordinates.zip_code_prefix,
        coordinates.latitude,
        coordinates.longitude,
        coordinates.point_count,
        city_ranked.city,
        city_ranked.state_code

    from coordinates
    left join city_ranked
        on coordinates.zip_code_prefix = city_ranked.zip_code_prefix
        and city_ranked.frequency_rank = 1

)

select * from final
