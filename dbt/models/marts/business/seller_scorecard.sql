{#
    seller_scorecard — one wide row per seller with volume, GMV concentration, fulfilment and
    review outcomes, for the seller-management team. Valid orders only.

    Attribution: delivery and review outcomes are recorded per order. In the 1.3% of orders
    with more than one seller, the outcome is attributed to every seller in the order
    (see docs/analyst_guide.md). Handover SLA = the order reached the carrier after the
    seller's shipping limit date.
#}

with

sellers as (

    select * from {{ ref('dim_sellers') }}

),

orders as (

    select * from {{ ref('fct_orders') }}
    where is_valid_order

),

seller_items as (

    select
        fct_order_items.seller_id,
        fct_order_items.order_id,
        fct_order_items.product_id,
        fct_order_items.order_purchase_date,
        fct_order_items.shipping_limit_at,
        fct_order_items.item_price_brl,
        fct_order_items.freight_value_brl,
        fct_order_items.item_total_brl,
        dim_products.product_category

    from {{ ref('fct_order_items') }} as fct_order_items
    inner join orders
        on fct_order_items.order_id = orders.order_id
    left join {{ ref('dim_products') }} as dim_products
        on fct_order_items.product_id = dim_products.product_id

),

-- one row per seller x order, so order-level outcomes count once per seller
seller_orders as (

    select
        seller_items.seller_id,
        seller_items.order_id,
        min(seller_items.shipping_limit_at) as shipping_limit_at,
        max(orders.order_delivered_to_carrier_at) as delivered_to_carrier_at,
        bool_or(orders.is_delivered) as is_delivered,
        bool_or(orders.is_late_delivery) as is_late_delivery,
        max(orders.delivery_days) as delivery_days,
        bool_or(orders.has_review) as has_review,
        max(orders.review_score) as review_score,
        bool_or(orders.is_bad_review) as is_bad_review

    from seller_items
    inner join orders
        on seller_items.order_id = orders.order_id
    group by seller_items.seller_id, seller_items.order_id

),

volume as (

    select
        seller_id,
        count(*) as items_sold,
        count(distinct product_id) as distinct_products,
        sum(item_total_brl) as gmv_brl,
        sum(item_price_brl) as item_revenue_brl,
        sum(freight_value_brl) as freight_brl,
        avg(item_price_brl) as avg_item_price_brl,
        min(order_purchase_date) as first_sale_date,
        max(order_purchase_date) as last_sale_date,
        count(distinct date_trunc('month', order_purchase_date)) as active_months

    from seller_items
    group by seller_id

),

outcomes as (

    select
        seller_id,
        count(*) as valid_orders,
        count(*) filter (where is_delivered) as delivered_orders,
        avg(case when is_late_delivery then 1.0 when not is_late_delivery then 0.0 end)
            as late_delivery_rate,
        avg(delivery_days) as avg_delivery_days,
        count(*) filter (where delivered_to_carrier_at is not null) as handed_over_orders,
        avg(
            case
                when delivered_to_carrier_at is null then null
                when delivered_to_carrier_at > shipping_limit_at then 1.0
                else 0.0
            end
        ) as late_handover_rate,
        count(*) filter (where has_review) as reviewed_orders,
        avg(review_score) as avg_review_score,
        avg(case when is_bad_review then 1.0 when not is_bad_review then 0.0 end) as bad_review_rate

    from seller_orders
    group by seller_id

),

category_preference as (

    select
        seller_id,
        product_category,
        row_number() over (
            partition by seller_id
            order by count(*) desc, sum(item_total_brl) desc, product_category
        ) as preference_rank

    from seller_items
    group by seller_id, product_category

),

joined as (

    select
        sellers.seller_id,
        sellers.seller_city,
        sellers.seller_state,
        sellers.seller_region,
        volume.first_sale_date,
        volume.last_sale_date,
        coalesce(volume.active_months, 0) as active_months,
        coalesce(outcomes.valid_orders, 0) as valid_orders,
        coalesce(volume.items_sold, 0) as items_sold,
        coalesce(volume.distinct_products, 0) as distinct_products,
        category_preference.product_category as top_category,
        coalesce(volume.gmv_brl, 0) as gmv_brl,
        coalesce(volume.item_revenue_brl, 0) as item_revenue_brl,
        coalesce(volume.freight_brl, 0) as freight_brl,
        volume.avg_item_price_brl,
        coalesce(outcomes.delivered_orders, 0) as delivered_orders,
        outcomes.late_delivery_rate,
        outcomes.avg_delivery_days,
        coalesce(outcomes.handed_over_orders, 0) as handed_over_orders,
        outcomes.late_handover_rate,
        coalesce(outcomes.reviewed_orders, 0) as reviewed_orders,
        outcomes.avg_review_score,
        outcomes.bad_review_rate

    from sellers
    left join volume
        on sellers.seller_id = volume.seller_id
    left join outcomes
        on sellers.seller_id = outcomes.seller_id
    left join category_preference
        on sellers.seller_id = category_preference.seller_id
        and category_preference.preference_rank = 1

),

final as (

    select
        cast(seller_id as varchar) as seller_id,
        cast(seller_city as varchar) as seller_city,
        cast(seller_state as varchar) as seller_state,
        cast(seller_region as varchar) as seller_region,
        cast(first_sale_date as date) as first_sale_date,
        cast(last_sale_date as date) as last_sale_date,
        cast(active_months as integer) as active_months,
        cast(valid_orders as integer) as valid_orders,
        cast(items_sold as integer) as items_sold,
        cast(distinct_products as integer) as distinct_products,
        cast(top_category as varchar) as top_category,
        cast(gmv_brl as decimal(18, 2)) as gmv_brl,
        cast(item_revenue_brl as decimal(18, 2)) as item_revenue_brl,
        cast(freight_brl as decimal(18, 2)) as freight_brl,
        cast(avg_item_price_brl as decimal(18, 2)) as avg_item_price_brl,
        cast(row_number() over (order by gmv_brl desc, seller_id) as integer) as gmv_rank,
        cast(gmv_brl / nullif(sum(gmv_brl) over (), 0) as double) as gmv_share,
        cast(
            sum(gmv_brl) over (order by gmv_brl desc, seller_id rows between unbounded preceding and current row)
            / nullif(sum(gmv_brl) over (), 0)
            as double
        ) as cumulative_gmv_share,
        cast(delivered_orders as integer) as delivered_orders,
        cast(late_delivery_rate as double) as late_delivery_rate,
        cast(avg_delivery_days as double) as avg_delivery_days,
        cast(handed_over_orders as integer) as handed_over_orders,
        cast(late_handover_rate as double) as late_handover_rate,
        cast(reviewed_orders as integer) as reviewed_orders,
        cast(avg_review_score as double) as avg_review_score,
        cast(bad_review_rate as double) as bad_review_rate

    from joined

)

select * from final
