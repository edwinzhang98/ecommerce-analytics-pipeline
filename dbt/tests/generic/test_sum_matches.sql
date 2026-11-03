{#
    Reconciliation check: sum(column_name) in this model must equal sum(compare_column) in
    `compare_model` within `tolerance`. Optional filters apply to each side.
    Example: item-level GMV must add up to order-level GMV, i.e. no double counting.
#}
{% test sum_matches(model, column_name, compare_model, compare_column, model_filter=none, compare_filter=none, tolerance=0.01) %}

with

model_total as (

    select coalesce(sum({{ column_name }}), 0) as total
    from {{ model }}
    {% if model_filter %}where {{ model_filter }}{% endif %}

),

compare_total as (

    select coalesce(sum({{ compare_column }}), 0) as total
    from {{ compare_model }}
    {% if compare_filter %}where {{ compare_filter }}{% endif %}

)

select
    model_total.total as model_total,
    compare_total.total as compare_total,
    model_total.total - compare_total.total as difference
from model_total
cross join compare_total
where abs(model_total.total - compare_total.total) > {{ tolerance }}

{% endtest %}
