{#
    fct_orders — one row per order placed on the marketplace, in any status.
    The single source of truth for order counts (ADR 0002):
      placed orders    = count(*)
      net orders (KPI) = count(*) filter (where is_valid_order)
      delivered orders = count(*) filter (where is_delivered)
#}

with

orders as (

    select * from {{ ref('int_orders_joined') }}

),

final as (

    select
        -- keys
        cast(order_id as varchar) as order_id,
        cast(customer_unique_id as varchar) as customer_unique_id,
        cast(customer_id as varchar) as customer_id,
        cast(order_purchase_date as date) as order_purchase_date,

        -- status
        cast(order_status as varchar) as order_status,
        cast(order_status_group as varchar) as order_status_group,
        cast(is_valid_order as boolean) as is_valid_order,
        cast(is_delivered as boolean) as is_delivered,

        -- lifecycle timestamps (local time, America/Sao_Paulo)
        cast(order_purchased_at as timestamp) as order_purchased_at,
        cast({{ local_to_utc('order_purchased_at') }} as timestamp) as order_purchased_at_utc,
        cast(order_approved_at as timestamp) as order_approved_at,
        cast(order_delivered_to_carrier_at as timestamp) as order_delivered_to_carrier_at,
        cast(order_delivered_to_customer_at as timestamp) as order_delivered_to_customer_at,
        cast(order_estimated_delivery_date as date) as order_estimated_delivery_date,
        cast(order_delivered_date as date) as order_delivered_date,

        -- delivery performance (delivered orders only)
        cast(hours_to_approval as double) as hours_to_approval,
        cast(delivery_days as integer) as delivery_days,
        cast(estimated_delivery_days as integer) as estimated_delivery_days,
        cast(delivery_delay_days as integer) as delivery_delay_days,
        cast(is_late_delivery as boolean) as is_late_delivery,

        -- items
        cast(item_count as integer) as item_count,
        cast(distinct_product_count as integer) as distinct_product_count,
        cast(distinct_seller_count as integer) as distinct_seller_count,
        cast(items_subtotal_brl as decimal(18, 2)) as items_subtotal_brl,
        cast(freight_total_brl as decimal(18, 2)) as freight_total_brl,
        cast(order_gmv_brl as decimal(18, 2)) as order_gmv_brl,

        -- payments
        cast(payment_total_brl as decimal(18, 2)) as payment_total_brl,
        cast(payment_count as integer) as payment_count,
        cast(primary_payment_type as varchar) as primary_payment_type,
        cast(max_payment_installments as integer) as max_payment_installments,
        cast(credit_card_amount_brl as decimal(18, 2)) as credit_card_amount_brl,
        cast(boleto_amount_brl as decimal(18, 2)) as boleto_amount_brl,
        cast(voucher_amount_brl as decimal(18, 2)) as voucher_amount_brl,
        cast(debit_card_amount_brl as decimal(18, 2)) as debit_card_amount_brl,
        cast(has_voucher_payment as boolean) as has_voucher_payment,
        cast(payment_gmv_difference_brl as decimal(18, 2)) as payment_gmv_difference_brl,

        -- review (latest answer per order)
        cast(has_review as boolean) as has_review,
        cast(review_id as varchar) as review_id,
        cast(review_score as integer) as review_score,
        cast(is_bad_review as boolean) as is_bad_review,
        cast(review_count as integer) as review_count,
        cast(review_answered_at as timestamp) as review_answered_at,

        -- data quality
        cast(has_items as boolean) as has_items,
        cast(has_payment as boolean) as has_payment,
        cast(is_payment_mismatch as boolean) as is_payment_mismatch,
        cast(data_quality_flags as varchar) as data_quality_flags

    from orders

)

select * from final
