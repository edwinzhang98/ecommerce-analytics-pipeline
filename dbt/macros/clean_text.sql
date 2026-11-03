{#
    Free-text comments: collapse line breaks and repeated whitespace into single spaces,
    trim, and turn empty / whitespace-only strings into null.
#}
{% macro clean_text(column_name) -%}
    nullif(trim(regexp_replace({{ column_name }}, '\s+', ' ', 'g')), '')
{%- endmacro %}
