{#
    customer_360 — one wide row per person (customer_unique_id) for CRM and analysts.
    Inherits every dim_customers column, then adds behaviour from the facts.
    All behavioural metrics use valid orders only (canceled / unavailable excluded),
    except canceled_or_unavailable_orders.
#}

with

customers as (

    select * from {{ ref('dim_customers') }}

),

orders as (

    select * from {{ ref('fct_orders') }}

),

valid_orders as (

    select * from orders
    where is_valid_order

),

items as (

    select
        fct_order_items.order_id,
        fct_order_items.customer_unique_id,
        fct_order_items.product_id,
        fct_order_items.item_total_brl,
        dim_products.product_category

    from {{ ref('fct_order_items') }} as fct_order_items
    inner join valid_orders
        on fct_order_items.order_id = valid_orders.order_id
    left join {{ ref('dim_products') }} as dim_products
        on fct_order_items.product_id = dim_products.product_id

),

order_outcomes as (

    select
        customer_unique_id,
        count(*) filter (where is_delivered) as delivered_orders,
        count(*) filter (where is_late_delivery) as late_delivery_orders,
        avg(case when is_late_delivery then 1.0 when not is_late_delivery then 0.0 end)
            as late_delivery_rate,
        avg(delivery_days) as avg_delivery_days,
        count(*) filter (where has_review) as reviewed_orders,
        avg(review_score) as avg_review_score,
        count(*) filter (where is_bad_review) as bad_review_orders,
        sum(payment_total_brl) as lifetime_paid_brl,
        bool_or(has_voucher_payment) as has_used_voucher,
        max(max_payment_installments) as max_payment_installments

    from valid_orders
    group by customer_unique_id

),

canceled as (

    select
        customer_unique_id,
        count(*) as canceled_or_unavailable_orders

    from orders
    where not is_valid_order
    group by customer_unique_id

),

payment_preference as (

    select
        customer_unique_id,
        primary_payment_type,
        row_number() over (
            partition by customer_unique_id
            order by count(*) desc, primary_payment_type
        ) as preference_rank

    from valid_orders
    where primary_payment_type is not null
    group by customer_unique_id, primary_payment_type

),

purchase_days as (

    select
        customer_unique_id,
        order_purchase_date,
        row_number() over (
            partition by customer_unique_id
            order by order_purchase_date
        ) as purchase_day_number

    from (select distinct customer_unique_id, order_purchase_date from valid_orders)

),

second_purchase as (

    select
        customer_unique_id,
        max(case when purchase_day_number = 1 then order_purchase_date end) as first_purchase_date,
        max(case when purchase_day_number = 2 then order_purchase_date end) as second_purchase_date

    from purchase_days
    group by customer_unique_id

),

item_metrics as (

    select
        customer_unique_id,
        count(*) as total_items,
        count(distinct product_id) as distinct_products,
        count(distinct product_category) as distinct_categories

    from items
    group by customer_unique_id

),

category_preference as (

    select
        customer_unique_id,
        product_category,
        row_number() over (
            partition by customer_unique_id
            order by count(*) desc, sum(item_total_brl) desc, product_category
        ) as preference_rank

    from items
    group by customer_unique_id, product_category

),

final as (

    select
        customers.*,

        -- lifecycle
        cast(
            case
                when not customers.has_valid_order then 'no_valid_order'
                when customers.is_repeat_customer then 'repeat'
                else 'one_time'
            end as varchar
        ) as customer_lifecycle_stage,
        cast(date_trunc('month', customers.first_valid_order_at) as date) as first_valid_order_month,
        cast(date_diff('day', second_purchase.first_purchase_date, second_purchase.second_purchase_date) as integer)
            as days_to_second_purchase,
        cast(coalesce(canceled.canceled_or_unavailable_orders, 0) as integer) as canceled_or_unavailable_orders,

        -- basket
        cast(coalesce(item_metrics.total_items, 0) as integer) as total_items,
        cast(coalesce(item_metrics.distinct_products, 0) as integer) as distinct_products,
        cast(coalesce(item_metrics.distinct_categories, 0) as integer) as distinct_categories,
        cast(category_preference.product_category as varchar) as top_category,

        -- payment
        cast(coalesce(order_outcomes.lifetime_paid_brl, 0) as decimal(18, 2)) as lifetime_paid_brl,
        cast(payment_preference.primary_payment_type as varchar) as preferred_payment_type,
        cast(coalesce(order_outcomes.has_used_voucher, false) as boolean) as has_used_voucher,
        cast(order_outcomes.max_payment_installments as integer) as max_payment_installments,

        -- delivery experience
        cast(coalesce(order_outcomes.delivered_orders, 0) as integer) as delivered_orders,
        cast(coalesce(order_outcomes.late_delivery_orders, 0) as integer) as late_delivery_orders,
        cast(order_outcomes.late_delivery_rate as double) as late_delivery_rate,
        cast(order_outcomes.avg_delivery_days as double) as avg_delivery_days,

        -- review experience
        cast(coalesce(order_outcomes.reviewed_orders, 0) as integer) as reviewed_orders,
        cast(order_outcomes.avg_review_score as double) as avg_review_score,
        cast(coalesce(order_outcomes.bad_review_orders, 0) as integer) as bad_review_orders

    from customers
    left join order_outcomes
        on customers.customer_unique_id = order_outcomes.customer_unique_id
    left join canceled
        on customers.customer_unique_id = canceled.customer_unique_id
    left join payment_preference
        on customers.customer_unique_id = payment_preference.customer_unique_id
        and payment_preference.preference_rank = 1
    left join second_purchase
        on customers.customer_unique_id = second_purchase.customer_unique_id
    left join item_metrics
        on customers.customer_unique_id = item_metrics.customer_unique_id
    left join category_preference
        on customers.customer_unique_id = category_preference.customer_unique_id
        and category_preference.preference_rank = 1

)

select * from final
