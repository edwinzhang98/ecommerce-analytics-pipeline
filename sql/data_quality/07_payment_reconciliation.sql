-- =====================================================================================
-- 07 Cross-table reconciliation: payments vs items + freight
-- Purpose : does what customers paid equal what they bought? (Mostly yes; installment interest
--           explains most gaps, see ADR 0004.)
-- Inputs  : raw.orders, raw.order_items, raw.order_payments
-- Output  : result 1 `summary`: one row of totals
--           result 2 `difference_buckets`: orders by size of the gap (payments minus items + freight)
-- Run     : uv run python scripts/run_sql.py sql/data_quality/07_payment_reconciliation.sql
-- =====================================================================================

-- result: summary
with

items as (

    select order_id, sum(price::decimal(10, 2) + freight_value::decimal(10, 2)) as items_and_freight
    from raw.order_items
    group by order_id

),

payments as (

    select
        order_id,
        sum(payment_value::decimal(10, 2)) as paid,
        max(payment_installments::int) as max_installments,
        bool_or(payment_type = 'credit_card') as has_credit_card

    from raw.order_payments
    group by order_id

),

compared as (

    select items.order_id, items_and_freight, paid, paid - items_and_freight as difference,
        max_installments, has_credit_card
    from items
    inner join payments on items.order_id = payments.order_id

)

select
    count(*) as orders_with_items_and_payments,
    count(*) filter (where abs(difference) <= 0.01) as exact_match,
    count(*) filter (where abs(difference) > 0.01) as off_by_more_than_1_cent,
    count(*) filter (where abs(difference) > 1) as off_by_more_than_1_brl,
    count(*) filter (where difference > 1) as overpaid_more_than_1_brl,
    count(*) filter (where difference > 1 and has_credit_card and max_installments > 1) as overpaid_card_in_installments,
    count(*) filter (where difference < -1) as underpaid_more_than_1_brl,
    sum(items_and_freight) as total_items_and_freight_brl,
    sum(paid) as total_paid_brl,
    sum(difference) as net_difference_brl

from compared;

-- result: difference_buckets
with

items as (

    select order_id, sum(price::decimal(10, 2) + freight_value::decimal(10, 2)) as items_and_freight
    from raw.order_items
    group by order_id

),

payments as (

    select order_id, sum(payment_value::decimal(10, 2)) as paid
    from raw.order_payments
    group by order_id

),

compared as (

    select paid - items_and_freight as difference
    from items
    inner join payments on items.order_id = payments.order_id

)

select
    case
        when difference < -10 then '1. underpaid > R$10'
        when difference < -1 then '2. underpaid R$1-10'
        when difference <= 1 then '3. within R$1'
        when difference <= 10 then '4. overpaid R$1-10'
        when difference <= 100 then '5. overpaid R$10-100'
        else '6. overpaid > R$100'
    end as difference_bucket,
    count(*) as orders

from compared
group by difference_bucket
order by difference_bucket;
