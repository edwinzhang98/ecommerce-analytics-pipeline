{#
    Payments rolled up and pivoted to one row per order (ADR 0003, ADR 0004).
    An order can be paid with several payment rows (e.g. a voucher plus a credit card).
#}

{%- set payment_types = ['credit_card', 'boleto', 'voucher', 'debit_card'] -%}

with

payments as (

    select * from {{ ref('stg_olist__order_payments') }}

),

ranked as (

    select
        *,
        -- deterministic "main" payment method: the largest amount, then the first sequence
        row_number() over (
            partition by order_id
            order by payment_value_brl desc, payment_sequential
        ) as amount_rank

    from payments

),

pivoted as (

    select
        order_id,
        count(*) as payment_count,
        count(distinct payment_type) as payment_type_count,
        sum(payment_value_brl) as payment_total_brl,
        {%- for payment_type in payment_types %}
        sum(case when payment_type = '{{ payment_type }}' then payment_value_brl else 0 end)
            as {{ payment_type }}_amount_brl,
        {%- endfor %}
        bool_or(payment_type = 'voucher') as has_voucher_payment,
        max(payment_installments) as max_payment_installments,
        max(case when amount_rank = 1 then payment_type end) as primary_payment_type

    from ranked
    group by order_id

)

select * from pivoted
