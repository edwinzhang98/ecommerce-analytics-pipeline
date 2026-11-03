{#
    True when a coordinate falls inside a bounding box around Brazil, including the
    Atlantic islands (Fernando de Noronha, Trindade). Coarse by design: it only catches
    points that are clearly wrong (Europe, North America, lat/lng = 0).
#}
{% macro is_within_brazil(lat, lng) -%}
    ({{ lat }} between -34.0 and 5.5 and {{ lng }} between -74.5 and -28.5)
{%- endmacro %}
