{#
    DQ-15 baseline: a satisfaction survey cannot be sent before the order was placed.
    64 review rows in the source are dated before the purchase date. Kept (the score is still
    the customer's answer) but monitored.
#}

{{
    config(
        warn_if='>64',
        error_if='>500',
        store_failures=true,
        tags=['known_issue'],
        meta={'dq_issue': 'DQ-15'}
    )
}}

select
    reviews.order_id,
    reviews.review_id,
    reviews.review_survey_sent_date,
    orders.order_purchased_at

from {{ ref('stg_olist__order_reviews') }} as reviews
inner join {{ ref('stg_olist__orders') }} as orders
    on reviews.order_id = orders.order_id
where reviews.review_survey_sent_date < cast(orders.order_purchased_at as date)
