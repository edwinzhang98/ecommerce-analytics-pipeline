-- =====================================================================================
-- 04 Value ranges and outliers of the numeric columns
-- Purpose : plausibility of amounts, installments, weights and coordinates.
-- Inputs  : raw.order_items, raw.order_payments, raw.products, raw.geolocation, raw.order_reviews
-- Output  : one row per measure: distribution + count of values breaking a plausibility rule
-- Run     : uv run python scripts/run_sql.py sql/data_quality/04_value_ranges_and_outliers.sql
-- =====================================================================================

-- result: value_ranges
with

measures as (

    select 'order_items.price (BRL)' as measure, price::double as value, price::double <= 0 as is_flagged,
        '<= 0' as rule from raw.order_items
    union all select 'order_items.freight_value (BRL)', freight_value::double, freight_value::double < 0, '< 0' from raw.order_items
    union all select 'order_payments.payment_value (BRL)', payment_value::double, payment_value::double <= 0, '<= 0' from raw.order_payments
    union all select 'order_payments.payment_installments', payment_installments::double, payment_installments::int < 1, '< 1' from raw.order_payments
    union all select 'order_reviews.review_score', review_score::double, review_score::int not between 1 and 5, 'not 1-5' from raw.order_reviews
    union all select 'products.product_weight_g', product_weight_g::double, product_weight_g::int <= 0, '<= 0' from raw.products
    union all select 'products.product_length_cm', product_length_cm::double, product_length_cm::int <= 0, '<= 0' from raw.products
    union all select 'geolocation.latitude', geolocation_lat::double,
        not (geolocation_lat::double between -34.0 and 5.5), 'outside Brazil box' from raw.geolocation
    union all select 'geolocation.longitude', geolocation_lng::double,
        not (geolocation_lng::double between -74.5 and -28.5), 'outside Brazil box' from raw.geolocation

)

select
    measure,
    count(value) as non_null_values,
    min(value) as min_value,
    round(quantile_cont(value, 0.01), 2) as p01,
    round(median(value), 2) as median_value,
    round(quantile_cont(value, 0.99), 2) as p99,
    max(value) as max_value,
    any_value(rule) as plausibility_rule,
    count(*) filter (where is_flagged) as flagged_values

from measures
group by measure
order by measure;
