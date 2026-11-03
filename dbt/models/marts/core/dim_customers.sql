{#
    dim_customers — one row per person (customer_unique_id), including people whose only
    orders were canceled or unavailable. Carries RFM inputs (docs/02_metric_definitions.md):
      R = recency_days, F = frequency_orders, M = monetary_gmv_brl
    Recency is measured against the last net-order purchase date in the data (rfm_reference_date),
    because the extract is historical: "today" would make every customer look lost.
#}

with

persons as (

    select * from {{ ref('int_customers_aggregated_to_persons') }}

),

geolocation as (

    select * from {{ ref('int_geolocation_aggregated_to_zip_prefixes') }}

),

states as (

    select * from {{ ref('brazil_states') }}

),

reference_date as (

    -- the last net-order purchase date in the data
    select max(cast(last_net_order_at as date)) as rfm_reference_date
    from persons

),

final as (

    select
        -- key
        cast(persons.customer_unique_id as varchar) as customer_unique_id,

        -- location (from the most recent order)
        cast(persons.customer_zip_code_prefix as varchar) as customer_zip_code_prefix,
        cast(persons.customer_city as varchar) as customer_city,
        cast(persons.customer_state as varchar) as customer_state,
        cast(states.state_name as varchar) as customer_state_name,
        cast(states.region_name as varchar) as customer_region,
        cast(geolocation.latitude as double) as customer_latitude,
        cast(geolocation.longitude as double) as customer_longitude,

        -- order history
        cast(persons.orders_placed as integer) as orders_placed,
        cast(persons.first_order_at as timestamp) as first_order_at,
        cast(persons.first_net_order_at as timestamp) as first_net_order_at,
        cast(persons.last_net_order_at as timestamp) as last_net_order_at,
        cast(persons.purchase_days as integer) as purchase_days,
        cast(persons.frequency_orders > 0 as boolean) as has_net_order,
        cast(persons.purchase_days >= 2 as boolean) as is_repeat_customer,

        -- RFM inputs
        cast(reference_date.rfm_reference_date as date) as rfm_reference_date,
        cast(
            date_diff('day', cast(persons.last_net_order_at as date), reference_date.rfm_reference_date)
            as integer
        ) as recency_days,
        cast(persons.frequency_orders as integer) as frequency_orders,
        cast(persons.monetary_gmv_brl as decimal(18, 2)) as monetary_gmv_brl,
        cast(
            case when persons.frequency_orders > 0
                then persons.monetary_gmv_brl / persons.frequency_orders
            end as decimal(18, 2)
        ) as avg_order_value_brl

    from persons
    cross join reference_date
    left join geolocation
        on persons.customer_zip_code_prefix = geolocation.zip_code_prefix
    left join states
        on persons.customer_state = states.state_code

)

select * from final
