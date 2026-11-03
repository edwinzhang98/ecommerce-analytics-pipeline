{#
    Calendar check: the date column must be gap-free and duplicate-free between its
    min and max, i.e. exactly one row per day.
#}
{% test is_continuous_date_spine(model, column_name) %}

with

stats as (

    select
        min({{ column_name }}) as first_day,
        max({{ column_name }}) as last_day,
        count(*) as row_count,
        count(distinct {{ column_name }}) as distinct_days

    from {{ model }}

)

select *
from stats
where row_count <> distinct_days
    or distinct_days <> date_diff('day', first_day, last_day) + 1

{% endtest %}
