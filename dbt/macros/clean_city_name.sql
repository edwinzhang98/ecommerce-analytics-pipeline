{#
    Normalise a free-text Brazilian city name:
      1. lower-case, strip accents, collapse repeated whitespace
      2. drop anything after a "/", "\" or "," separator ("sao paulo / sp", "novo hamburgo, rs, brasil")
      3. drop a trailing state code after a hyphen ("lages - sc", "andira-pr")
      4. if `state_column` is given, drop a trailing space-separated state code only when it is the
         row's own state ("brasilia df" in DF -> "brasilia"), so that real names such as
         "sento se" (Sento Se, in Bahia) are left alone
      5. return null when what is left is not a usable city: only digits / punctuation
         (a zip code typed as the city), an e-mail address, or <= 2 characters (a state code).
         Names that merely contain a digit stay ("quilometro 14 do mutum" is a real district).
    Used for customer, seller and geolocation cities.
#}
{% macro clean_city_name(column_name, state_column=none) -%}
    {%- set state_codes = 'ac|al|ap|am|ba|ce|df|es|go|ma|mt|ms|mg|pa|pb|pr|pe|pi|rj|rn|rs|ro|rr|sc|sp|se|to' -%}
    {%- set separators_removed -%}
        trim(regexp_replace(regexp_replace(
            trim(regexp_replace(lower(strip_accents(trim({{ column_name }}))), '\s+', ' ', 'g')),
            '\s*[/\\,].*$', ''), '\s*-\s*({{ state_codes }})$', ''))
    {%- endset -%}
    {%- if state_column -%}
        {%- set normalised -%}
            case
                when ends_with({{ separators_removed }}, ' ' || lower(trim({{ state_column }})))
                    then trim(left({{ separators_removed }}, length({{ separators_removed }}) - 3))
                else {{ separators_removed }}
            end
        {%- endset -%}
    {%- else -%}
        {%- set normalised = separators_removed -%}
    {%- endif -%}
    case
        when regexp_full_match({{ normalised }}, '[0-9\s.\-]+')
            or contains({{ normalised }}, '@')
            or length({{ normalised }}) <= 2
            then null
        else {{ normalised }}
    end
{%- endmacro %}
