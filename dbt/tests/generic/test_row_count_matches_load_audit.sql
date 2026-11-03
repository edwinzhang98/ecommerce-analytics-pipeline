{#
    Load-integrity check on a source table: its row count must equal the parsed row count
    that ingestion/load_raw.py recorded in raw.load_audit for that table. Catches partial or
    interrupted loads between the EL step and dbt.
#}
{% test row_count_matches_load_audit(model, audit_model, audit_table_name) %}

with

actual as (

    select count(*) as row_count from {{ model }}

),

expected as (

    select max(parsed_rows) as row_count
    from {{ audit_model }}
    where table_name = '{{ audit_table_name }}'

)

select
    actual.row_count as actual_row_count,
    expected.row_count as audited_row_count
from actual
cross join expected
where expected.row_count is null
    or actual.row_count <> expected.row_count

{% endtest %}
