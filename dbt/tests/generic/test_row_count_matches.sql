{#
    Grain / fan-out guard: the model must have exactly as many rows as `compare_model`
    (or as many as the distinct values of `compare_column` in it, when given).
    Returns one row describing the mismatch, so it fails loudly on any join fan-out
    or accidental filter.
#}
{% test row_count_matches(model, compare_model, compare_column=none) %}

with

model_rows as (

    select count(*) as row_count from {{ model }}

),

compare_rows as (

    select
        {% if compare_column %}count(distinct {{ compare_column }}){% else %}count(*){% endif %} as row_count
    from {{ compare_model }}

)

select
    model_rows.row_count as model_row_count,
    compare_rows.row_count as compare_row_count
from model_rows
cross join compare_rows
where model_rows.row_count <> compare_rows.row_count

{% endtest %}
