{#
    One review per order (ADR 0003). 547 orders have 2-3 survey answers; we keep the most
    recently answered one, i.e. the customer's latest opinion, and keep the count.
    review_id is not unique in the source (one answer can cover several orders), so the
    order is the grain, not the review.
#}

with

reviews as (

    select * from {{ ref('stg_olist__order_reviews') }}

),

ranked as (

    select
        *,
        row_number() over (
            partition by order_id
            order by review_answered_at desc, review_survey_sent_date desc, review_id
        ) as recency_rank,
        count(*) over (partition by order_id) as review_count

    from reviews

),

latest as (

    select
        order_id,
        review_id,
        review_score,
        review_comment_title,
        review_comment_message,
        review_survey_sent_date,
        review_answered_at,
        review_count

    from ranked
    where recency_rank = 1

)

select * from latest
