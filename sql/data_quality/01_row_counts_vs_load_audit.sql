-- =====================================================================================
-- 01 Row-count reconciliation of the EL step
-- Purpose : file lines vs parsed rows vs the release's known row counts vs what sits in raw.
-- Inputs  : raw.load_audit, raw.orders, raw.order_items, raw.customers, raw.order_payments,
--           raw.order_reviews, raw.products, raw.sellers, raw.geolocation,
--           raw.product_category_name_translation
-- Output  : one row per raw table
-- Run     : uv run python scripts/run_sql.py sql/data_quality/01_row_counts_vs_load_audit.sql
-- =====================================================================================

-- result: row_counts
with

raw_tables as (

    select 'orders' as table_name, count(*) as rows_in_raw from raw.orders
    union all select 'order_items', count(*) from raw.order_items
    union all select 'customers', count(*) from raw.customers
    union all select 'order_payments', count(*) from raw.order_payments
    union all select 'order_reviews', count(*) from raw.order_reviews
    union all select 'products', count(*) from raw.products
    union all select 'sellers', count(*) from raw.sellers
    union all select 'geolocation', count(*) from raw.geolocation
    union all select 'product_category_name_translation', count(*) from raw.product_category_name_translation

)

select
    load_audit.table_name,
    load_audit.source_file,
    round(load_audit.file_bytes / 1e6, 2) as file_mb,
    load_audit.physical_data_lines,
    load_audit.parsed_rows,
    load_audit.expected_rows,
    raw_tables.rows_in_raw,
    load_audit.parsed_rows - load_audit.physical_data_lines as parsed_minus_lines,
    load_audit.parsed_rows = load_audit.expected_rows and raw_tables.rows_in_raw = load_audit.parsed_rows
        as reconciles

from raw.load_audit as load_audit
inner join raw_tables
    on load_audit.table_name = raw_tables.table_name
order by load_audit.parsed_rows desc;
