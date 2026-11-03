{#
    The order-grain backbone of the marts: one row per order (all statuses), with items,
    payments and the latest review attached. Every child table is aggregated to the order
    grain BEFORE the join, so this model can never fan out (ADR 0003); a dbt test checks
    that it has exactly as many rows as stg_olist__orders.
#}

with

orders as (

    select * from {{ ref('int_orders_classified') }}

),

-- Olist issues one customer record per order, holding the address used for that order:
-- per the source documentation it is the order's delivery location.
customers as (

    select
        customer_id,
        customer_unique_id,
        customer_zip_code_prefix,
        customer_city,
        customer_state

    from {{ ref('stg_olist__customers') }}

),

states as (

    select state_code, region_name from {{ ref('brazil_states') }}

),

items as (

    select * from {{ ref('int_order_items_aggregated_to_orders') }}

),

payments as (

    select * from {{ ref('int_payments_pivoted_to_orders') }}

),

reviews as (

    select * from {{ ref('int_reviews_deduplicated_to_orders') }}

),

joined as (

    select
        orders.*,
        customers.customer_unique_id,

        -- delivery address of this order
        customers.customer_zip_code_prefix as delivery_zip_code_prefix,
        customers.customer_city as delivery_city,
        customers.customer_state as delivery_state,
        states.region_name as delivery_region,

        -- items
        items.order_id is not null as has_items,
        coalesce(items.item_count, 0) as item_count,
        coalesce(items.distinct_product_count, 0) as distinct_product_count,
        coalesce(items.distinct_seller_count, 0) as distinct_seller_count,
        coalesce(items.items_subtotal_brl, 0) as items_subtotal_brl,
        coalesce(items.freight_total_brl, 0) as freight_total_brl,
        coalesce(items.order_gmv_brl, 0) as order_gmv_brl,

        -- payments
        payments.order_id is not null as has_payment,
        coalesce(payments.payment_count, 0) as payment_count,
        coalesce(payments.payment_total_brl, 0) as payment_total_brl,
        coalesce(payments.credit_card_amount_brl, 0) as credit_card_amount_brl,
        coalesce(payments.boleto_amount_brl, 0) as boleto_amount_brl,
        coalesce(payments.voucher_amount_brl, 0) as voucher_amount_brl,
        coalesce(payments.debit_card_amount_brl, 0) as debit_card_amount_brl,
        coalesce(payments.has_voucher_payment, false) as has_voucher_payment,
        payments.primary_payment_type,
        payments.max_payment_installments,

        -- latest review
        reviews.order_id is not null as has_review,
        reviews.review_id,
        reviews.review_score,
        coalesce(reviews.review_count, 0) as review_count,
        reviews.review_survey_sent_date,
        reviews.review_answered_at

    from orders
    left join customers
        on orders.customer_id = customers.customer_id
    left join states
        on customers.customer_state = states.state_code
    left join items
        on orders.order_id = items.order_id
    left join payments
        on orders.order_id = payments.order_id
    left join reviews
        on orders.order_id = reviews.order_id

),

final as (

    select
        *,

        payment_total_brl - order_gmv_brl as payment_gmv_difference_brl,

        -- payments and items should agree; installment interest makes some differ (ADR 0004)
        has_items and has_payment
            and abs(payment_total_brl - order_gmv_brl) > {{ var('payment_mismatch_tolerance_brl') }}
            as is_payment_mismatch,

        review_score <= {{ var('bad_review_max_score') }} as is_bad_review

    from joined

)

select
    *,
    nullif(concat_ws(',',
        lifecycle_anomalies,
        case when not has_items then 'no_items' end,
        case when not has_payment then 'no_payment' end,
        case when is_payment_mismatch then 'payment_mismatch' end
    ), '') as data_quality_flags

from final
