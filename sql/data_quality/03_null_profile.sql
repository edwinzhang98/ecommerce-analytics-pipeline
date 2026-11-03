-- =====================================================================================
-- 03 Null profile of every raw column that has nulls (exact counts)
-- Purpose : where values are missing (empty CSV fields load as NULL).
-- Inputs  : the 9 raw tables
-- Output  : one row per (table, column) with at least one null, worst first
-- Run     : uv run python scripts/run_sql.py sql/data_quality/03_null_profile.sql
-- =====================================================================================

-- result: null_profile
with

nulls as (

    select 'orders' as table_name, (select count(*) from raw.orders) as row_count, column_name, null_count
    from (unpivot (select count(*) - count(columns(* exclude (_source_file, _loaded_at))) from raw.orders)
          on columns(*) into name column_name value null_count)
    union all
    select 'order_items', (select count(*) from raw.order_items), column_name, null_count
    from (unpivot (select count(*) - count(columns(* exclude (_source_file, _loaded_at))) from raw.order_items)
          on columns(*) into name column_name value null_count)
    union all
    select 'customers', (select count(*) from raw.customers), column_name, null_count
    from (unpivot (select count(*) - count(columns(* exclude (_source_file, _loaded_at))) from raw.customers)
          on columns(*) into name column_name value null_count)
    union all
    select 'order_payments', (select count(*) from raw.order_payments), column_name, null_count
    from (unpivot (select count(*) - count(columns(* exclude (_source_file, _loaded_at))) from raw.order_payments)
          on columns(*) into name column_name value null_count)
    union all
    select 'order_reviews', (select count(*) from raw.order_reviews), column_name, null_count
    from (unpivot (select count(*) - count(columns(* exclude (_source_file, _loaded_at))) from raw.order_reviews)
          on columns(*) into name column_name value null_count)
    union all
    select 'products', (select count(*) from raw.products), column_name, null_count
    from (unpivot (select count(*) - count(columns(* exclude (_source_file, _loaded_at))) from raw.products)
          on columns(*) into name column_name value null_count)
    union all
    select 'sellers', (select count(*) from raw.sellers), column_name, null_count
    from (unpivot (select count(*) - count(columns(* exclude (_source_file, _loaded_at))) from raw.sellers)
          on columns(*) into name column_name value null_count)
    union all
    select 'geolocation', (select count(*) from raw.geolocation), column_name, null_count
    from (unpivot (select count(*) - count(columns(* exclude (_source_file, _loaded_at))) from raw.geolocation)
          on columns(*) into name column_name value null_count)

)

select
    table_name,
    column_name,
    row_count,
    null_count,
    round(100.0 * null_count / row_count, 2) as null_pct

from nulls
where null_count > 0
order by null_pct desc, table_name, column_name;
