{#
    Source timestamps are naive local time in America/Sao_Paulo (see docs/assumptions.md).
    Convert one to a naive UTC timestamp. Uses the IANA rules, so the Brazilian daylight
    saving time that applied until 2019 is handled.
#}
{% macro local_to_utc(column_name, source_tz='America/Sao_Paulo') -%}
    timezone('UTC', timezone('{{ source_tz }}', {{ column_name }}))
{%- endmacro %}
