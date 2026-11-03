{#
    DQ-16 baseline: payments should equal items + freight. In the source, 249 orders differ by
    more than the tolerance (default R$1.00), almost all card payments in installments where
    the amount includes interest (ADR 0004). Passes at the known baseline, warns if it grows,
    errors if it explodes. Failing rows are stored for inspection.
#}

{{
    config(
        warn_if='>249',
        error_if='>1000',
        store_failures=true,
        tags=['known_issue'],
        meta={'dq_issue': 'DQ-16'}
    )
}}

select
    order_id,
    order_status,
    order_gmv_brl,
    payment_total_brl,
    payment_gmv_difference_brl,
    max_payment_installments,
    primary_payment_type

from {{ ref('fct_orders') }}
where has_items
    and has_payment
    and abs(payment_gmv_difference_brl) > {{ var('payment_mismatch_tolerance_brl') }}
