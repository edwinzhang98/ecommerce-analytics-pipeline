{#
    Fails for every row where the column is negative. Nulls are ignored
    (combine with not_null where the value is mandatory).
    Example: prices, freight, payments, GMV.
#}
{% test non_negative(model, column_name) %}

select *
from {{ model }}
where {{ column_name }} < 0

{% endtest %}
