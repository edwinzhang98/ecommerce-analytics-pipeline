-- =====================================================================================
-- 02 Primary-key uniqueness of every raw table
-- Purpose : is the obvious key really unique? review_id and order_id in reviews are not; customer_unique_id
--           and the geolocation zip prefix repeat by design (a person, a postal area).
-- Inputs  : raw.orders, raw.customers, raw.order_items, raw.order_payments, raw.order_reviews,
--           raw.products, raw.sellers, raw.geolocation, raw.product_category_name_translation
-- Output  : one row per (table, candidate key) with rows, distinct keys and duplicates
-- Run     : uv run python scripts/run_sql.py sql/data_quality/02_primary_keys.sql
-- =====================================================================================

-- result: primary_keys
select 'orders' as table_name, 'order_id' as candidate_key, count(*) as row_count,
    count(distinct order_id) as distinct_keys from raw.orders
union all select 'customers', 'customer_id', count(*), count(distinct customer_id) from raw.customers
union all select 'customers', 'customer_unique_id', count(*), count(distinct customer_unique_id) from raw.customers
union all select 'order_items', 'order_id + order_item_id', count(*), count(distinct (order_id, order_item_id)) from raw.order_items
union all select 'order_payments', 'order_id + payment_sequential', count(*), count(distinct (order_id, payment_sequential)) from raw.order_payments
union all select 'order_reviews', 'review_id', count(*), count(distinct review_id) from raw.order_reviews
union all select 'order_reviews', 'order_id', count(*), count(distinct order_id) from raw.order_reviews
union all select 'order_reviews', 'review_id + order_id', count(*), count(distinct (review_id, order_id)) from raw.order_reviews
union all select 'products', 'product_id', count(*), count(distinct product_id) from raw.products
union all select 'sellers', 'seller_id', count(*), count(distinct seller_id) from raw.sellers
union all select 'geolocation', 'zip_code_prefix', count(*), count(distinct geolocation_zip_code_prefix) from raw.geolocation
union all select 'geolocation', 'all columns', count(*),
    count(distinct (geolocation_zip_code_prefix, geolocation_lat, geolocation_lng, geolocation_city, geolocation_state)) from raw.geolocation
union all select 'product_category_name_translation', 'product_category_name', count(*), count(distinct product_category_name)
    from raw.product_category_name_translation;
