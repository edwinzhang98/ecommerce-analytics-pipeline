{#
    Order status and lifecycle logic (ADR 0002):
      * status -> status group and "valid order" flag, driven by the order_status_mapping seed
      * delivery durations and the late-delivery flag (delivered orders only)
      * lifecycle anomaly flags for timestamps that are out of order in the source
#}

with

orders as (

    select * from {{ ref('stg_olist__orders') }}

),

status_mapping as (

    select * from {{ ref('order_status_mapping') }}

),

classified as (

    select
        orders.order_id,
        orders.customer_id,
        orders.order_status,
        status_mapping.order_status_group,
        status_mapping.is_valid_order,
        orders.order_status = 'delivered' as is_delivered,

        orders.order_purchased_at,
        orders.order_approved_at,
        orders.order_delivered_to_carrier_at,
        orders.order_delivered_to_customer_at,
        orders.order_estimated_delivery_date,
        cast(orders.order_purchased_at as date) as order_purchase_date,

        -- delivery metrics are defined for delivered orders with a delivery timestamp only
        orders.order_status = 'delivered'
            and orders.order_delivered_to_customer_at is not null as has_delivery_metrics

    from orders
    left join status_mapping
        on orders.order_status = status_mapping.order_status

),

with_metrics as (

    select
        *,

        case when has_delivery_metrics then cast(order_delivered_to_customer_at as date) end
            as order_delivered_date,

        round(date_diff('second', order_purchased_at, order_approved_at) / 3600.0, 2)
            as hours_to_approval,

        case when has_delivery_metrics
            then date_diff('day', order_purchase_date, cast(order_delivered_to_customer_at as date))
        end as delivery_days,

        date_diff('day', order_purchase_date, order_estimated_delivery_date)
            as estimated_delivery_days,

        -- positive = delivered after the estimated date, negative = early
        case when has_delivery_metrics
            then date_diff('day', order_estimated_delivery_date, cast(order_delivered_to_customer_at as date))
        end as delivery_delay_days,

        -- late = delivered on a later calendar day than the estimate shown at purchase
        case when has_delivery_metrics
            then cast(order_delivered_to_customer_at as date) > order_estimated_delivery_date
        end as is_late_delivery,

        -- lifecycle anomaly flags (source timestamps that contradict each other)
        order_approved_at < order_purchased_at as is_approved_before_purchase,
        order_delivered_to_carrier_at < order_purchased_at as is_carrier_before_purchase,
        order_delivered_to_carrier_at < order_approved_at as is_carrier_before_approval,
        order_delivered_to_customer_at < order_delivered_to_carrier_at as is_delivered_before_carrier,
        order_delivered_to_customer_at < order_approved_at as is_delivered_before_approval,
        order_status = 'delivered' and order_delivered_to_customer_at is null
            as is_delivered_without_timestamp,
        order_status = 'delivered' and order_approved_at is null
            as is_delivered_without_approval,
        order_status = 'canceled' and order_delivered_to_customer_at is not null
            as is_canceled_with_delivery

    from classified

),

final as (

    select
        * exclude (
            is_approved_before_purchase,
            is_carrier_before_purchase,
            is_carrier_before_approval,
            is_delivered_before_carrier,
            is_delivered_before_approval,
            is_delivered_without_timestamp,
            is_delivered_without_approval,
            is_canceled_with_delivery
        ),
        nullif(concat_ws(',',
            case when is_approved_before_purchase then 'approved_before_purchase' end,
            case when is_carrier_before_purchase then 'carrier_before_purchase' end,
            case when is_carrier_before_approval then 'carrier_before_approval' end,
            case when is_delivered_before_carrier then 'delivered_before_carrier' end,
            case when is_delivered_before_approval then 'delivered_before_approval' end,
            case when is_delivered_without_timestamp then 'delivered_without_timestamp' end,
            case when is_delivered_without_approval then 'delivered_without_approval' end,
            case when is_canceled_with_delivery then 'canceled_with_delivery' end
        ), '') as lifecycle_anomalies

    from with_metrics

)

select * from final
