{#
    Normalise a free-text Brazilian city name:
      1. lower-case, strip accents, collapse repeated whitespace
      2. drop anything after a "/", "\" or "," separator ("sao paulo / sp", "novo hamburgo, rs, brasil")
      3. drop a trailing state code after a hyphen ("lages - sc", "andira-pr")
      4. return null when what is left is not a usable city: only digits / punctuation
         (a zip code typed as the city), an e-mail address, or <= 2 characters (a state code).
         Names that merely contain a digit stay ("quilometro 14 do mutum" is a real district).
    Used for seller and geolocation cities, which are typed by hand in the source.
#}
{% macro clean_city_name(column_name) -%}
    {%- set state_codes = 'ac|al|ap|am|ba|ce|df|es|go|ma|mt|ms|mg|pa|pb|pr|pe|pi|rj|rn|rs|ro|rr|sc|sp|se|to' -%}
    {%- set normalised -%}
        trim(regexp_replace(regexp_replace(
            trim(regexp_replace(lower(strip_accents(trim({{ column_name }}))), '\s+', ' ', 'g')),
            '\s*[/\\,].*$', ''), '\s*-\s*({{ state_codes }})$', ''))
    {%- endset -%}
    case
        when regexp_full_match({{ normalised }}, '[0-9\s.\-]+')
            or contains({{ normalised }}, '@')
            or length({{ normalised }}) <= 2
            then null
        else {{ normalised }}
    end
{%- endmacro %}
