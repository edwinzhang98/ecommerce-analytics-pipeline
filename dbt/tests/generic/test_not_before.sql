{#
    Event-order check: fails for every row where `column_name` happens strictly before
    `compare_column` (rows where either side is null are ignored).
    Example: an order cannot be delivered before it was purchased.
#}
{% test not_before(model, column_name, compare_column) %}

select *
from {{ model }}
where {{ column_name }} is not null
    and {{ compare_column }} is not null
    and {{ column_name }} < {{ compare_column }}

{% endtest %}
