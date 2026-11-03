with

source as (

    select * from {{ source('olist', 'order_reviews') }}

),

renamed as (

    select
        -- ids. review_id alone is NOT unique: one survey answer can cover several orders.
        {{ dbt_utils.generate_surrogate_key(['review_id', 'order_id']) }} as order_review_key,
        review_id,
        order_id,

        -- review
        cast(review_score as integer) as review_score,
        {{ clean_text('review_comment_title') }} as review_comment_title,
        {{ clean_text('review_comment_message') }} as review_comment_message,

        -- dates. The source "creation date" is the day the survey was sent (time is always 00:00).
        cast(review_creation_date as date) as review_survey_sent_date,
        cast(review_answer_timestamp as timestamp) as review_answered_at,

        -- metadata
        _loaded_at

    from source

)

select * from renamed
