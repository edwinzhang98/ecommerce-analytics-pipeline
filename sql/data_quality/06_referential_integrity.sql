-- =====================================================================================
-- 06 Referential integrity: orphans and missing children
-- Purpose : every foreign key resolves (it does), and which parents have no children (some do).
-- Inputs  : raw.orders, raw.order_items, raw.order_payments, raw.order_reviews, raw.customers,
--           raw.products, raw.sellers, raw.geolocation
-- Output  : one row per relationship with the number of rows that do not match
-- Run     : uv run python scripts/run_sql.py sql/data_quality/06_referential_integrity.sql
-- =====================================================================================

-- result: referential_integrity
select 'orphan' as check_type, 'order_items.order_id -> orders' as relationship,
    count(*) as unmatched_rows from raw.order_items where order_id not in (select order_id from raw.orders)
union all select 'orphan', 'order_items.product_id -> products', count(*)
    from raw.order_items where product_id not in (select product_id from raw.products)
union all select 'orphan', 'order_items.seller_id -> sellers', count(*)
    from raw.order_items where seller_id not in (select seller_id from raw.sellers)
union all select 'orphan', 'order_payments.order_id -> orders', count(*)
    from raw.order_payments where order_id not in (select order_id from raw.orders)
union all select 'orphan', 'order_reviews.order_id -> orders', count(*)
    from raw.order_reviews where order_id not in (select order_id from raw.orders)
union all select 'orphan', 'orders.customer_id -> customers', count(*)
    from raw.orders where customer_id not in (select customer_id from raw.customers)
union all select 'missing child', 'orders without order_items', count(*)
    from raw.orders where order_id not in (select order_id from raw.order_items)
union all select 'missing child', 'orders without order_payments', count(*)
    from raw.orders where order_id not in (select order_id from raw.order_payments)
union all select 'missing child', 'orders without order_reviews', count(*)
    from raw.orders where order_id not in (select order_id from raw.order_reviews)
union all select 'missing child', 'customers without orders', count(*)
    from raw.customers where customer_id not in (select customer_id from raw.orders)
union all select 'missing lookup', 'customers.zip_code_prefix -> geolocation', count(*)
    from raw.customers where customer_zip_code_prefix not in (select geolocation_zip_code_prefix from raw.geolocation)
union all select 'missing lookup', 'sellers.zip_code_prefix -> geolocation', count(*)
    from raw.sellers where seller_zip_code_prefix not in (select geolocation_zip_code_prefix from raw.geolocation)
union all select 'missing lookup', 'products.category -> translation (distinct categories)', count(distinct product_category_name)
    from raw.products where product_category_name not in (select product_category_name from raw.product_category_name_translation);
