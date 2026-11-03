{#
    dim_date — one row per calendar day, 2016-01-01 to 2018-12-31 (covers every purchase,
    estimate and delivery date in the data). Adds Brazilian national holidays (seed),
    Black Friday, and a flag for months with complete data coverage.
#}

with

spine as (

    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('2016-01-01' as date)",
        end_date="cast('2019-01-01' as date)"
    ) }}

),

holidays as (

    select * from {{ ref('brazil_national_holidays') }}

),

days as (

    select cast(date_day as date) as date_day
    from spine

),

final as (

    select
        cast(days.date_day as date) as date_day,
        cast(extract(year from days.date_day) as integer) as year,
        cast(extract(quarter from days.date_day) as integer) as quarter,
        cast(extract(month from days.date_day) as integer) as month,
        cast(strftime(days.date_day, '%B') as varchar) as month_name,
        cast(strftime(days.date_day, '%Y-%m') as varchar) as year_month,
        cast(date_trunc('month', days.date_day) as date) as month_start_date,
        cast(date_trunc('week', days.date_day) as date) as week_start_date,
        cast(extract(day from days.date_day) as integer) as day_of_month,
        cast(isodow(days.date_day) as integer) as day_of_week,
        cast(strftime(days.date_day, '%A') as varchar) as day_name,
        cast(isodow(days.date_day) in (6, 7) as boolean) as is_weekend,
        cast(holidays.holiday_date is not null as boolean) as is_holiday,
        cast(holidays.holiday_name as varchar) as holiday_name,
        -- Black Friday: the day after the fourth Thursday of November
        cast(
            extract(month from days.date_day) = 11
            and isodow(days.date_day) = 5
            and extract(day from days.date_day) between 23 and 29
            as boolean
        ) as is_black_friday,
        -- months with full order coverage; 2016 and Sep-Oct 2018 are partial (see DQ report)
        cast(
            strftime(days.date_day, '%Y-%m')
                between '{{ var("complete_data_start_month") }}' and '{{ var("complete_data_end_month") }}'
            as boolean
        ) as is_complete_data_month

    from days
    left join holidays
        on days.date_day = holidays.holiday_date

)

select * from final
