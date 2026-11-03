# Analyst guide: working with the marts

**For:** analysts and business users who used to query `raw` · **Maintained by:** Analytics Engineering · **Numbers checked against:** the build of 2026-11-03 (dbt 1.12.6, 300 of 300 tests passing)

The `marts` schema is the only place we support for analysis. Each `dbt build` builds the marts and runs all 300 tests (296 data tests and 4 unit tests). All 188 mart columns are documented, and enforced contracts fix their names and types. This guide covers which table answers which question, how to join safely, ten tested query recipes, and the traps behind the three different order counts.

Column definitions are in the [data dictionary](data_dictionary.md), and metric definitions in [02_metric_definitions.md](02_metric_definitions.md). The app's *Analyst guide* page is the short version of this document.

Contents: [Golden rules](#golden-rules) · [Which mart answers which question](#which-mart-answers-which-question) · [Join map](#join-map) · [Recipes](#recipes) · [Traps](#traps-and-how-the-marts-prevent-them) · [Where to run queries](#where-to-run-queries) · [Requesting a change](#how-to-request-a-change) · [FAQ](#faq)

## Golden rules

1. **Query `marts` only.** `raw`, `staging` and `intermediate` are implementation layers: they have no contract and can change without notice. `raw` also still has the source problems that the later layers handle ([data-quality register](../sql/data_quality/issue_register.yml), DQ-01 to DQ-21). The one exception is `test_failures`, which holds the failing rows of each known-issue test ([recipe 10](#10-orders-with-data-quality-flags)).
2. **Say which order count you mean.** Net orders, `count(*) filter (where is_net_order)` on `fct_orders`, is the official order KPI. Placed orders (`count(*)`) and delivered orders (`count(*) filter (where is_delivered)`) are separate metrics with their own names. Never label delivered orders as "orders".
3. **Know the grain before you count or sum.** `fct_orders` has one row per order and `fct_order_items` one row per unit sold. Order-level columns (GMV, payments, delivery, review) live on `fct_orders`; never sum them after joining to items. Join only from many rows to one ([join map](#join-map)).
4. **Date by `order_purchase_date` and trend complete months only.** It is the local (São Paulo) purchase date and joins to `dim_date.date_day`. Filter on `dim_date.is_complete_data_month` (2017-01 to 2018-08) for any trend or month-over-month comparison.
5. **Revenue means net GMV.** Sum `order_gmv_brl` (orders) or `item_total_brl` (items) where `is_net_order`. `payment_total_brl` is cash collected, including card installment interest; use it only for payment questions.
6. **A customer is a person: `customer_unique_id`.** A repeat customer is `is_repeat_customer`: net orders on 2 or more distinct purchase days. The marts deliberately leave out the source's per-order `customer_id`.
7. **Show the denominator.** Report every rate with its n. Small groups (a few hundred or fewer) get a margin of error or a caveat. A difference between groups is an association, not evidence of a cause.

## Which mart answers which question

| Question | Mart | Grain (rows) | Key columns |
|---|---|---|---|
| How many orders (placed, net, delivered)? Net GMV, AOV? | `fct_orders` | one row per order, any status (99,441) | `is_net_order`, `is_delivered`, `order_purchase_date`, `order_gmv_brl` |
| Trends by month or week; holidays, Black Friday | `fct_orders` + `dim_date` | `dim_date`: one row per calendar day, 2016-01-01 to 2018-12-31 (1,096) | `year_month`, `week_start_date`, `is_holiday`, `is_black_friday`, `is_complete_data_month` |
| Delivery performance by state or region | `fct_orders` | order | `is_late_delivery`, `delivery_days`, `delivery_delay_days`, `delivery_state`, `delivery_region` |
| Review outcomes | `fct_orders` | order | `has_review`, `review_score`, `is_bad_review`, `review_count` |
| Payment mix, installments, vouchers, cash collected | `fct_orders` | order | `primary_payment_type`, `payment_total_brl`, `credit_card_amount_brl`, `max_payment_installments`, `has_voucher_payment` |
| Sales by product, category or seller | `fct_order_items` | one row per unit sold (112,650) | `is_net_order`, `item_total_brl`, `product_id`, `seller_id` |
| Product attributes, English category name | `dim_products` | one row per product (32,951) | `product_category`, `has_complete_attributes`, `product_weight_g` |
| Seller location | `dim_sellers` | one row per seller (3,095) | `seller_state`, `seller_region`, `is_city_inferred_from_zip` |
| Seller ranking, GMV concentration, handover SLA, reviews | `seller_scorecard` | one row per seller (3,095) | `net_orders`, `gmv_brl`, `gmv_rank`, `cumulative_gmv_share`, `late_handover_rate`, `bad_review_rate` |
| Customer counts, repeat rate, RFM inputs, where customers live | `dim_customers` | one row per person (96,096) | `customer_unique_id`, `has_net_order`, `is_repeat_customer`, `recency_days`, `frequency_orders`, `monetary_gmv_brl`, `customer_state` |
| One wide row per customer for CRM: lifecycle stage, cohort, time to second purchase, delivery and review experience | `customer_360` | one row per person (96,096) | `customer_lifecycle_stage`, `first_net_order_month`, `days_to_second_purchase`, `late_delivery_orders`, `bad_review_orders` |
| Which orders have data-quality issues | `fct_orders` | order | `has_data_quality_flag`, `data_quality_flags`, `has_lifecycle_anomaly`, `is_payment_mismatch`, `has_items`, `has_payment` |

Row counts are from the 2026-11-03 build. Every mart except `fct_order_items` is rebuilt in full on every run. `fct_order_items` is incremental ([ADR 0005](adr/0005-incremental-fct-order-items.md)), and each build checks that it reconciles with `fct_orders` to the cent.

## Join map

Every supported join goes from many rows to one row, so it cannot multiply your rows. Every foreign key on the two fact tables has a `relationships` test, so an inner join does not silently drop rows.

| From (many) | To (one) | Join on | Use it for |
|---|---|---|---|
| `fct_order_items` | `fct_orders` | `order_id` | order attributes (delivery, review) on item rows; count `distinct order_id` afterwards |
| `fct_order_items` | `dim_products` | `product_id` | category and product attributes |
| `fct_order_items` | `dim_sellers` or `seller_scorecard` | `seller_id` | seller location; seller tiers such as `net_orders >= 50` |
| `fct_order_items` | `dim_customers` or `customer_360` | `customer_unique_id` | buyer attributes on items |
| `fct_order_items` | `dim_date` | `order_purchase_date = date_day` | calendar attributes, complete months |
| `fct_orders` | `dim_customers` or `customer_360` | `customer_unique_id` | buyer attributes on orders |
| `fct_orders` | `dim_date` | `order_purchase_date = date_day` | calendar attributes, complete months |
| `seller_scorecard` | `dim_sellers` | `seller_id` | one-to-one: zip prefix and coordinates |

You never need to join `customer_360` to `dim_customers`: it already carries every `dim_customers` column.

Joins to avoid:

- **Counting rows or summing an order column after joining `fct_orders` and `fct_order_items`.** The result has one row per unit, so every order repeats once per unit. For net orders, `count(*)` returns 112,101 and `sum(order_gmv_brl)` returns R$20,152,630.23, instead of 98,207 net orders and R$15,735,527.03 (+28.1%). After this join, sum item columns (`item_total_brl`) or count `distinct order_id`, and take order-level amounts from `fct_orders` alone.
- **`fct_orders` to `seller_scorecard`.** An order has no single seller. Go through `fct_order_items` and de-duplicate the (seller, order) pairs, as [recipe 4](#4-delivery-and-review-outcomes-by-category-item-to-order-join) does for categories.
- **Anything to `raw.geolocation`.** It has 1,000,163 rows for 19,015 zip prefixes (DQ-06). The coordinates are already on `dim_customers` and `dim_sellers`, one point per zip prefix.

## Recipes

Each snippet below was run read-only against the warehouse and against the app's parquet cache on 2026-11-03. Both returned identical results, which are quoted under each snippet. Every snippet is a single DuckDB statement: paste it into the DuckDB CLI (add a closing `;`) or the app's query box, or save it as a `.sql` file for `scripts/run_sql.py`.

### 1. The three named order counts in one query

```sql
select
    count(*)                                        as placed_orders,
    count(*) filter (where is_net_order)            as net_orders,
    count(*) filter (where is_delivered)            as delivered_orders,
    count(*) filter (where not is_terminal_status)  as open_orders
from marts.fct_orders
```

It returns 99,441 placed, 98,207 net, 96,478 delivered and 1,729 open orders. Every build also counts net orders six independent ways and fails if any two disagree ([`assert_net_order_count_consistent_across_query_paths.sql`](../dbt/tests/singular/assert_net_order_count_consistent_across_query_paths.sql)). [`analyses/q0_order_count_reconciliation.sql`](../analyses/q0_order_count_reconciliation.sql) shows the analysts' query paths side by side.

### 2. Monthly net orders and net GMV, complete months only

```sql
select
    dim_date.year_month,
    count(*) filter (where fct_orders.is_net_order)                         as net_orders,
    sum(fct_orders.order_gmv_brl) filter (where fct_orders.is_net_order)    as net_gmv_brl,
    round(net_gmv_brl / net_orders, 2)                                      as aov_brl
from marts.fct_orders as fct_orders
inner join marts.dim_date as dim_date
    on fct_orders.order_purchase_date = dim_date.date_day
where dim_date.is_complete_data_month
group by dim_date.year_month
order by dim_date.year_month
```

It returns 20 months, from 2017-01 (787 net orders, R$136,943.46) to 2018-08 (6,421 net orders, R$996,973.51): 97,910 net orders and R$15,683,706.74 in total. Without the `where` clause you also get 2016-09, 2016-10, 2016-12, 2018-09 and 2018-10. On a chart these look like a ramp-up and a collapse, but they are partial months at the edges of the extract (DQ-19).

### 3. Net GMV by product category

```sql
select
    dim_products.product_category,
    count(*)                                    as units_sold,
    count(distinct fct_order_items.order_id)    as net_orders,   -- an order with 2 categories counts in both
    sum(fct_order_items.item_total_brl)         as net_gmv_brl
from marts.fct_order_items as fct_order_items
inner join marts.dim_products as dim_products
    on fct_order_items.product_id = dim_products.product_id
inner join marts.dim_date as dim_date
    on fct_order_items.order_purchase_date = dim_date.date_day
where fct_order_items.is_net_order
    and dim_date.is_complete_data_month
group by dim_products.product_category
order by net_gmv_brl desc
limit 15
```

`health_beauty` leads with 9,585 units and R$1,432,213.38. `is_net_order` sits on the item row, so no join to `fct_orders` is needed. Leaving that filter out would add the items of canceled and unavailable orders (R$108,026.21 over the whole extract). GMV adds up across categories; `net_orders` does not.

### 4. Delivery and review outcomes by category (item-to-order join)

```sql
with

category_orders as (
    -- one row per (category, order): several units of one category count once
    select distinct
        dim_products.product_category,
        fct_order_items.order_id
    from marts.fct_order_items as fct_order_items
    inner join marts.dim_products as dim_products
        on fct_order_items.product_id = dim_products.product_id
    where fct_order_items.is_net_order
)

select
    category_orders.product_category,
    count(*)                                                                as net_orders,
    count(*) filter (where fct_orders.is_late_delivery is not null)         as measured_deliveries,
    round(100.0 * count(*) filter (where fct_orders.is_late_delivery) / measured_deliveries, 2) as late_rate_pct,
    count(*) filter (where fct_orders.has_review)                           as reviewed_orders,
    round(100.0 * count(*) filter (where fct_orders.is_bad_review) / reviewed_orders, 2)        as bad_review_rate_pct
from category_orders
inner join marts.fct_orders as fct_orders                -- many (category, order) rows -> one order
    on category_orders.order_id = fct_orders.order_id
group by category_orders.product_category
having count(*) >= 1000
order by bad_review_rate_pct desc
```

22 categories have 1,000 or more net orders. `office_furniture` has the highest rate of bad reviews (1-2 stars): 22.66% of 1,262 reviewed orders. `luggage_accessories` has the lowest: 8.87%. The `distinct` step matters: without it, an order with three units of one category would count three times. These rates describe orders that contain the category; they are not effects of it.

### 5. Late delivery rate and median delivery days by delivery state

```sql
with

by_state as (
    select
        fct_orders.delivery_state,
        any_value(fct_orders.delivery_region)                   as delivery_region,
        count(*)                                                as measured_deliveries,
        count(*) filter (where fct_orders.is_late_delivery)     as late_deliveries,
        median(fct_orders.delivery_days)                        as median_delivery_days
    from marts.fct_orders as fct_orders
    inner join marts.dim_date as dim_date
        on fct_orders.order_purchase_date = dim_date.date_day
    where fct_orders.is_late_delivery is not null   -- delivered, with a delivery timestamp
        and dim_date.is_complete_data_month
    group by fct_orders.delivery_state
)

select
    delivery_state,
    delivery_region,
    measured_deliveries,
    round(100.0 * late_deliveries / measured_deliveries, 2)                 as late_rate_pct,
    -- 95% margin of error in percentage points (normal approximation)
    round(196 * sqrt(late_deliveries / measured_deliveries
        * (1 - late_deliveries / measured_deliveries) / measured_deliveries), 1) as margin_pp,
    median_delivery_days
from by_state
where measured_deliveries >= 300                    -- smaller states are too noisy to rank
order by late_rate_pct desc
```

21 states pass the 300-delivery cut:

- AL has the highest late delivery rate: 21.46% ± 4.0 pp, on 396 deliveries.
- PR has the lowest: 4.06% ± 0.6 pp.
- SP is at 4.50% ± 0.2 pp, with a 7-day median delivery time.

The ranges for AL and MA (17.53% ± 2.8 pp) overlap, so their order in the ranking is not reliable. A delivery counts as late when it arrived on a later calendar day than the estimate, so an order delivered on the estimated day is on time.

### 6. Repeat customer rate

```sql
select
    count(*)                                                as customers,
    count(*) filter (where is_repeat_customer)              as repeat_customers,
    round(100.0 * repeat_customers / customers, 2)          as repeat_rate_pct,
    -- for comparison only: "2+ net orders" also counts split checkouts and same-day orders
    round(100.0 * count(*) filter (where frequency_orders >= 2) / customers, 2) as two_plus_orders_pct
from marts.dim_customers
where has_net_order
```

2,065 of the 94,990 people with a net order are repeat customers: 2.17%. The comparison column, people with 2+ net orders, shows 3.04%. That count includes checkouts split into several orders in the same second (290 times, DQ-05) and second orders placed on the same day. Counting distinct purchase timestamps gives 2.78%, and distinct purchase days 2.17% ([`analyses/q2_repeat_purchase.sql`](../analyses/q2_repeat_purchase.sql)).

### 7. Cohort repurchase within N days (fully observed cohorts only)

```sql
with

params as (
    select 90 as window_days                    -- repurchase window N
),

cohorts as (
    select
        customer_360.first_net_order_month                                          as cohort_month,
        count(*)                                                                    as customers,
        count(*) filter (where customer_360.days_to_second_purchase <= params.window_days) as repeat_customers,
        -- fully observed: even the cohort's last customer had N days before the data ends
        max(cast(customer_360.first_net_order_at as date)) + params.window_days
            <= max(customer_360.rfm_reference_date)                                 as is_fully_observed
    from marts.customer_360 as customer_360
    cross join params
    where customer_360.has_net_order
        and customer_360.first_net_order_month >= date '2017-01-01'
    group by customer_360.first_net_order_month, params.window_days
)

select
    strftime(cohort_month, '%Y-%m')                     as cohort_month,
    customers,
    repeat_customers,
    round(100.0 * repeat_customers / customers, 2)      as repeat_rate_pct
from cohorts
where is_fully_observed
order by cohort_month
```

With N = 90, 17 cohorts are fully observed (2017-01 to 2018-05), with repurchase rates from 0.93% to 1.89%. With N = 180, only 14 are (2017-01 to 2018-02). A cohort that has not yet had N days to come back would show an artificially low rate, which is why the newest months drop out.

The numbers of repeat customers per cohort are small. For example, 2017-01's 0.93% (7 of 752 people) has a 95% interval of 0.45% to 1.91%. [`analyses/q2_repeat_purchase.sql`](../analyses/q2_repeat_purchase.sql) adds Wilson intervals to every cohort.

### 8. RFM starter

```sql
with

rfm as (
    select
        customer_unique_id,
        recency_days,
        frequency_orders,
        monetary_gmv_brl,
        -- quintiles; customer_unique_id breaks ties so the scores are reproducible
        6 - ntile(5) over (order by recency_days, customer_unique_id)       as r_score,  -- 5 = most recent
        ntile(5) over (order by monetary_gmv_brl, customer_unique_id)       as m_score,  -- 5 = highest spend
        -- F as a flag, not a quintile: 97.8% of people bought on a single day
        case when is_repeat_customer then 'repeat' else 'one-time' end      as f_segment
    from marts.dim_customers
    where has_net_order
)

select
    r_score,
    min(recency_days)                                       as min_recency_days,
    max(recency_days)                                       as max_recency_days,
    count(*)                                                as customers,
    round(100.0 * count(*) filter (where f_segment = 'repeat') / count(*), 2) as repeat_pct,
    round(avg(monetary_gmv_brl), 2)                         as avg_monetary_brl
from rfm
group by r_score
order by r_score desc
```

It returns five R groups of 18,998 people each. R = 5 means a last net order 0 to 98 days before 2018-09-03 (`rfm_reference_date`, the last net-order date in the data). Replace the final `select` with `select * from rfm` to get one row per person. People with the same recency at a group boundary are split by `customer_unique_id`, so the scores are reproducible between runs. The R, F and M inputs are in `dim_customers`; [the data dictionary](data_dictionary.md#dim_customers) defines them.

### 9. Seller scorecard, established sellers only

```sql
select
    seller_id,
    seller_state,
    top_category,
    net_orders,
    gmv_brl,
    gmv_rank,
    handed_over_orders,
    round(100 * late_handover_rate, 1)  as late_handover_rate_pct,
    round(100 * late_delivery_rate, 1)  as late_delivery_rate_pct,
    reviewed_orders,
    round(100 * bad_review_rate, 1)     as bad_review_rate_pct
from marts.seller_scorecard
where net_orders >= 50                  -- established sellers only
order by late_handover_rate desc nulls last
limit 20
```

428 sellers have 50 or more net orders, and together they hold 68.5% of net GMV. Of the 3,053 sellers with a net order, 1,792 have fewer than 10. The top row has a late handover rate of 60.0% on 75 handed-over orders.

Even at 50 orders, a 30% rate carries a margin of about ±13 pp. Use the list to decide which sellers to talk to first, not as a verdict on them. `late_handover_rate` counts single-seller orders only (see [multi-seller orders](#multi-seller-orders)). [`analyses/q3_seller_performance.sql`](../analyses/q3_seller_performance.sql) has the full quadrant analysis.

### 10. Orders with data-quality flags

```sql
select
    flag,
    count(*)                                as orders,
    count(*) filter (where is_net_order)    as net_orders
from (
    select
        unnest(string_split(data_quality_flags, ',')) as flag,
        is_net_order
    from marts.fct_orders
    where has_data_quality_flag
)
group by flag
order by orders desc
```

2,428 orders carry at least one flag. The most common are `carrier_before_approval` (1,359), `no_items` (775, of which 8 are net orders) and `payment_mismatch` (249). Flags never remove rows: you decide per analysis. Before excluding a flag, check whether it moves your number:

```sql
select
    has_lifecycle_anomaly,
    count(*)                                                                as measured_deliveries,
    round(100.0 * count(*) filter (where is_late_delivery) / count(*), 2)   as late_rate_pct,
    median(delivery_days)                                                   as median_delivery_days
from marts.fct_orders
where is_late_delivery is not null
group by has_lifecycle_anomaly
order by has_lifecycle_anomaly
```

Excluding the 1,387 measured deliveries with a lifecycle anomaly moves the late delivery rate from 6.77% to 6.85%.

The rows behind each known-issue test are stored in the warehouse's `test_failures` schema (the app's query box sees only the marts). For example, `select * from test_failures.known_issue__deliveries_over_120_days` returns the 43 delivered orders that took more than 120 days (DQ-13). The [data quality report](data_quality_report.md) explains every issue.

## Traps and how the marts prevent them

### Fan-out

- **What happened on raw:** joining `orders` to `order_items` and `order_payments` returns 117,601 rows and R$20,308,134.71 of "revenue", although there are only 99,441 orders. That was Analyst A's number.
- **What the marts do:** items, payments and reviews are aggregated to one row per order before they reach `fct_orders`. Grain tests check that `fct_orders` has exactly one row per source order. Item GMV must also reconcile with order GMV to the cent (`item_gmv_reconciles_with_order_gmv`). See [ADR 0003](adr/0003-grain-fan-out-and-customer-identity.md).
- **What you still have to do:** `fct_order_items` has one row per unit, because the source has no quantity column (DQ-04). There, `count(*)` counts units; use `count(distinct order_id)` for orders. Never sum `fct_orders` columns after joining to items (see [joins to avoid](#join-map)).

### `customer_id` is not a customer

- **What happened on raw:** `customer_id` is issued per order: 99,441 ids for 96,096 people, and 2,997 people have two or more (DQ-01). Counted on `customer_id`, nobody has ever bought twice.
- **What the marts do:** `customer_id` is not exposed at all. People are `customer_unique_id` in every mart, and `dim_customers` and `customer_360` have one row per person.
- **Related trap:** one checkout can be split into several orders in the same second (290 times, DQ-05). "2+ net orders" therefore overstates repeat buying: 3.04%, against 2.78% by distinct checkout times and 2.17% by distinct purchase days. Use `is_repeat_customer`, which counts distinct purchase days.

### `review_id` is not a review count

- **What happened on raw:** 789 `review_id`s are attached to two or more orders (DQ-02), and 547 orders have 2-3 survey answers (DQ-03). Joining reviews to orders fans out.
- **What the marts do:** `fct_orders` keeps the latest answer per order and stores how many answers there were in `review_count`. Review metrics are shares of orders: `has_review`, `is_bad_review`.
- **What you still have to do:** never count `review_id`. Even after de-duplication, 561 `review_id`s cover 1,139 orders, so `count(distinct review_id)` returns 98,095 for 98,673 reviewed orders.

### Payments are not revenue

- **What happened on raw:** Analyst B's revenue, R$16,008,872.12, was the sum of every payment. That sum includes R$269,735.11 recorded against canceled and unavailable orders, as well as credit-card installment interest.
- **What the marts do:** GMV (items + freight) is the revenue measure, in `order_gmv_brl` and `item_total_brl`. Payments are kept unadjusted in `payment_total_brl`, next to `payment_gmv_difference_brl` and `is_payment_mismatch`. 249 orders differ by more than R$1. Of the 232 orders overpaid by more than R$1, 229 were paid by credit card in installments (DQ-16). See [ADR 0004](adr/0004-payments-cancellations-and-refunds.md).
- **What you still have to do:** use net GMV (R$15,735,527.03) for sales, AOV and anything by product, seller or category. Use `payment_total_brl` (R$15,739,137.01 on net orders) only for cash or payment-mix questions. Net GMV is bookings: the source has no refund data, so it is not cash and not recognised revenue.

### Incomplete months

- **What happens:** the extract runs from 2016-09-04 to 2018-10-17, but only 2017-01 to 2018-08 are complete. 2016-11 has no orders at all. 2018-09 and 2018-10 have 20 placed orders between them, of which 1 is a net order. In total, 349 placed orders (297 net orders) fall outside the complete months (DQ-19).
- **What the marts do:** `dim_date.is_complete_data_month` marks the complete months. A test fails if any complete month ever has fewer than 500 net orders.
- **What you still have to do:** filter on it for every trend, month-over-month or seasonal comparison ([recipe 2](#2-monthly-net-orders-and-net-gmv-complete-months-only)).

### Open orders

- **What happens:** 1,729 orders were still open at extract time (`is_terminal_status = false`): shipped 1,107, invoiced 314, processing 301, created 5 and approved 2. They are 1.76% of net orders and R$315,753.28 of net GMV. They count as net orders because they were neither canceled nor unavailable ([ADR 0002](adr/0002-order-status-and-net-orders.md)).
- **Why it matters:** most of them are stale. 1,623 were placed more than 90 days before the extract ends (2018-10-17), and 980 before 2018. The source has probably stopped updating some of these statuses, so many may never show as delivered.
- **What the marts do:** every order carries the flag. Delivery metrics only use delivered orders with a delivery timestamp. `fct_order_items` re-processes every open order on each incremental run, so its `is_net_order` follows status changes.
- **What you still have to do:** for fulfilment questions, use delivered orders. Where a result is sensitive to open orders, report them next to it: `count(*) filter (where is_net_order and not is_terminal_status)`. For example, all 1,107 open `shipped` orders were past their estimated delivery date when the extract ends; counted as late, they would raise the late delivery rate from 6.77% to 7.83%.

### Multi-seller orders

- **What happens:** 1,278 orders (1.3%) contain items from two or more sellers. Items and GMV belong to exactly one seller, but delivery and review outcomes are recorded once per order.
- **What the marts do:** `seller_scorecard` attributes each order-level outcome to every seller in the order. A late delivery on a two-seller order therefore counts once for each seller. `late_handover_rate` uses single-seller orders only, because the source has one carrier timestamp per order and the sellers in it have different shipping limits.
- **What you still have to do:** you can sum `gmv_brl` across sellers; it adds up exactly to net GMV. Do not sum `net_orders` or `delivered_orders` across sellers: `net_orders` adds up to 99,542, not the 98,199 net orders that have items.

### Time zone

- **What happens:** source timestamps carry no time zone. We treat them as local São Paulo time (DQ-21, [assumptions](assumptions.md)). Converting to UTC moves 14,377 orders (14.5%) to another calendar day and 407 to another month. The offset is 3 hours, or 2 hours during the Brazilian summer time that applied until 2019.
- **What the marts do:** `order_purchase_date` (local) is the date basis for every metric. `order_purchased_at_utc` exists only for joining with systems that log in UTC.
- **What you still have to do:** never derive a date or month from `order_purchased_at_utc` for reporting.

### Delivery state vs customer state

- **What happens:** Olist writes one customer record per order, so a person's address can change from one order to the next.
- **What the marts do:** they publish two columns with two meanings. `fct_orders.delivery_state` (and `delivery_region`) is where that order was delivered. `dim_customers.customer_state` is the person's address on their latest net order (their latest order, for people with no net order). The two disagree for 43 orders from 39 people.
- **What you still have to do:** use `delivery_state` for orders, GMV and delivery performance, and `customer_state` for counting people ([FAQ](#why-do-sp-mg-and-the-other-states-show-slightly-different-totals-in-two-reports)).

## Where to run queries

The warehouse is the DuckDB file `data/warehouse/olist.duckdb`, built by `make all` (see the [README](../README.md)). You can change its path with `DUCKDB_PATH` or in `config.yaml`. The first three options below use the same `marts.*` table names, so a query moves between them unchanged; MetricFlow queries metrics by name.

| Where | How | Best for |
|---|---|---|
| DuckDB warehouse | `duckdb -readonly data/warehouse/olist.duckdb`, or from Python: `duckdb.connect("data/warehouse/olist.duckdb", read_only=True)` | ad hoc SQL against the latest build |
| [`scripts/run_sql.py`](../scripts/run_sql.py) | `uv run python scripts/run_sql.py analyses/q2_repeat_purchase.sql --var repeat_window_days=90` | repo SQL files: prints every `-- result:` section; `--var` overrides a `set variable` default |
| The app's query box | `make dashboard`, page *Analyst guide*, section "Try it: query the marts" | quick checks without a SQL client |
| MetricFlow (semantic layer) | `make metrics`, or `cd dbt && uv run --group semantic mf query --metrics net_orders,late_delivery_rate --group-by metric_time__month` | the 11 official metrics, computed exactly as defined in [`_semantic_models.yml`](../dbt/models/semantic/_semantic_models.yml) |

Things to know:

- **Always open the warehouse read-only, and close your session before a build.** DuckDB allows either one process that writes or several that only read. An open session, even a read-only one, makes `make build` and `make all` fail with a lock error. `scripts/run_sql.py` opens the file read-only and exits when it finishes.
- **Use a DuckDB 2.x client.** The project pins DuckDB 2.0.0 in `uv.lock`; `uv run python` always uses that version.
- **The app reads a parquet cache, not the warehouse.** The query box runs against a copy of the marts that `make cache` writes, so after a rebuild, run `make cache` before comparing numbers with the app. The code is in [`dashboard/app_pages/7_analyst_guide.py`](../dashboard/app_pages/7_analyst_guide.py).
- **Column definitions:** the [data dictionary](data_dictionary.md), generated from the dbt YAML. `make docs` also builds the dbt docs site with lineage as a single file, `dbt/target/static_index.html`.

## How to request a change

**A number looks wrong.**

1. Check the [traps](#traps-and-how-the-marts-prevent-them) and the [FAQ](#faq), then reproduce the number with a query on the marts.
2. Open a GitHub issue with your query, the number you got, the number you expected, and where that expectation comes from.
3. If it turns out to be a source problem, Analytics Engineering adds it to the [issue register](../sql/data_quality/issue_register.yml) under the next ID (DQ-22). It also gets a baseline test that passes at today's count, warns if the count grows and errors if it explodes, and a line in the [data quality report](data_quality_report.md).

**You need a new column, metric or mart.**

1. Open an issue with the business question, the grain (what one row means), the exact definition and who will use it.
2. The change arrives as a pull request. It is ready to merge when:
   - the column is declared in the model's YAML with a description and tests (the contract rejects undeclared columns);
   - `dbt build` passes on the real data locally;
   - CI passes on the synthetic fixture ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)): parse with deprecations as errors, every data and unit test, the known-issue detection check, the best-practice lint, a MetricFlow smoke test and the incremental check;
   - the reconciliation tests still pass, for example the six-path net order count.
3. Renaming, retyping or removing a mart column is a breaking change. The pull request lists the affected consumers (see [`exposures.yml`](../dbt/models/exposures.yml): the app and the analyses) and agrees a switch-over date with them.

**You want a definition to change.**

1. Definitions live in reviewed files, not in individual queries. The order KPI is in [`order_status_mapping.csv`](../dbt/seeds/order_status_mapping.csv). The thresholds (`bad_review_max_score`, `payment_mismatch_tolerance_brl`, the complete-month range) are vars in [`dbt_project.yml`](../dbt/dbt_project.yml).
2. A definition change needs:
   - an ADR in [`docs/adr/`](adr/) (a new one, or one that supersedes the old decision);
   - updates to [02_metric_definitions.md](02_metric_definitions.md) and the semantic layer;
   - before/after numbers in the pull request;
   - approval from the Analytics Lead, plus Finance sign-off for the order KPI.
3. Example: "exclude open orders older than 90 days from net orders" would supersede ADR 0002. It is not a filter to add to one report.

## FAQ

### Why does my number differ from the old dashboard?

Usually it is a different definition, fan-out, payments used as revenue, a different period or a different date basis. The old queries on raw, reproduced in [`01_three_analysts_on_raw.sql`](../sql/metrics/01_three_analysts_on_raw.sql):

| Old query (on raw) | "Orders" | "Revenue" (R$) | What it actually measures |
|---|---:|---:|---|
| `orders` joined to `order_items` and `order_payments`, `count(*)` | 117,601 | 20,308,134.71 | rows after fan-out |
| `count(*)` from `orders`; sum of all payments | 99,441 | 16,008,872.12 | placed orders; cash, including canceled orders and interest |
| `orders` where status is `delivered`; their payments | 96,478 | 15,422,461.77 | delivered orders |
| **marts: net orders and net GMV** | **98,207** | **15,735,527.03** | the official KPI ([ADR 0002](adr/0002-order-status-and-net-orders.md)) |

If the definitions match, check the period: complete months only give 97,910 net orders and R$15,683,706.74. Then check the date basis: UTC dates move 14.5% of orders to another day.

### Why do SP, MG and the other states show slightly different totals in two reports?

One report probably uses `fct_orders.delivery_state` (where each order went) and the other `dim_customers.customer_state` (where the person last received a net order). For example:

- SP has 41,127 net orders by delivery state and 41,132 by customer state.
- MG has 11,496 by delivery state and 11,493 by customer state.

Customer counts by state also do not add up to the total. Summed over delivery states, there are 95,028 customers, against 94,990 people, because a few people received orders in more than one state. Use `delivery_state` for orders and deliveries, and `customer_state` for people.

### Why does SP look so much better than the North and Northeast?

SP is faster: in complete months the median delivery takes 7 days there, against 22 in AL and 16 to 26 in the North states. Late delivery rates are more mixed, because "late" compares the delivery with the date estimated at purchase, and estimates for distant states are longer. AL has the highest rate (21.46%, against 4.50% in SP; [recipe 5](#5-late-delivery-rate-and-median-delivery-days-by-delivery-state)). AM has a 26-day median delivery but only 2.76% late deliveries, because its median estimate is 46 days (SP: 19). Six of the seven North states have fewer than 300 deliveries in complete months, so their rates are imprecise.

The marts show where deliveries are slow or late, not why. Distance to sellers (73.9% of sellers are in the Southeast), carrier networks and product mix all differ by state, so treat these gaps as associations.

SP also holds 41.9% of complete-month net orders (41,022 of 97,910), so it dominates any count-based ranking. Compare rates instead, with their margins.

### What is an open order?

An order whose status can still change: `created`, `approved`, `invoiced`, `processing` or `shipped` (`is_terminal_status = false`). There are 1,729. They count as net orders, but most are months old (see [open orders](#open-orders)). `delivered`, `canceled` and `unavailable` are terminal: they never change.

### Why are canceled and unavailable orders in `fct_orders` at all?

Placed orders and cancellation analysis need them: 625 canceled and 609 unavailable orders, 1,234 in total, which is exactly the gap between placed orders and net orders. Every other metric filters them out with `is_net_order`.

### Which repeat rate is right: 0%, 2.17% or 3.04%?

2.17% is the official figure: 2,065 of 94,990 people bought on two or more distinct days ([recipe 6](#6-repeat-customer-rate)). 0% is what `customer_id` gives on raw. 3.04% counts any second net order, including split checkouts and second orders on the same day. [ADR 0003](adr/0003-grain-fan-out-and-customer-identity.md) explains the choice.

### Why is recency measured against 2018-09-03 and not today?

The extract is historical. Measured from today, every customer would look lapsed. `rfm_reference_date` is the last net-order purchase date in the data. The 16 orders placed after that date were all canceled.

### Can I see how an order's status changed over time?

Only partly. `fct_orders` has the approval, carrier handover and delivery timestamps, but there is no cancellation timestamp, and the source holds only each order's current status. The snapshot `snapshots.snp_olist__orders` (SCD2) records every status change from the first load onwards, but with a single extract it holds one version per order (99,441 rows). If you need status history, ask for it as a mart rather than querying the snapshot directly.

### Why is there an `unknown` product category?

610 products have no category in the source (DQ-07). Keep the `unknown` bucket in category reports and exclude it only on purpose. Two Portuguese categories missing from the source's translation table are translated by a seed (DQ-20).

### `fct_order_items` is incremental. Can I trust it to be complete?

Yes. Every build checks that it has exactly one row per source item and that its GMV matches `fct_orders` to the cent, in total and for net orders. If a late-arriving row were ever skipped, the grain test would fail the build, and the fix is a full refresh of that one model ([ADR 0005](adr/0005-incremental-fct-order-items.md)).

### The build log shows WARN on a `known_issue__...` test. Can I still use the numbers?

Yes, but tell Analytics Engineering. A known-issue test passes at today's count of a documented source problem, warns when the count grows, and errors when it explodes. For example, `known_issue__deliveries_over_120_days` passes at 43, warns above 43 and errors above 300. A warning means the source got worse, but the marts were still built and tested. An error fails the build and skips the models downstream of the failing test. In both cases the affected rows are in `test_failures.<test name>`.

### The app shows a different number from my query.

Check three things:

- **Period and filters.** The *Dashboard* page only offers complete months (2017-01 to 2018-08), and its month range or delivery-region filter may be narrowed.
- **Freshness.** The app reads the parquet cache from the last `make cache`, not the warehouse.
- **Definition.** The app reports net orders and net GMV, as in [recipes 1 and 2](#1-the-three-named-order-counts-in-one-query).

After `make all`, the cache and the warehouse hold the same data, and the same SQL returns the same result in both.

## Further reading

- [Data dictionary](data_dictionary.md): every mart column, its type and definition.
- [Metric definitions](02_metric_definitions.md) and [assumptions](assumptions.md).
- [Data quality report](data_quality_report.md) and the [issue register](../sql/data_quality/issue_register.yml) (DQ-01 to DQ-21).
- ADRs: [0001 layered architecture](adr/0001-layered-architecture.md) · [0002 order status and net orders](adr/0002-order-status-and-net-orders.md) · [0003 grain, fan-out and customer identity](adr/0003-grain-fan-out-and-customer-identity.md) · [0004 payments, cancellations and refunds](adr/0004-payments-cancellations-and-refunds.md) · [0005 incremental `fct_order_items`](adr/0005-incremental-fct-order-items.md).
- Worked analyses on the marts: [q0 order count reconciliation](../analyses/q0_order_count_reconciliation.sql), [q1 delivery vs reviews by state](../analyses/q1_delivery_vs_reviews_by_state.sql), [q2 repeat purchase](../analyses/q2_repeat_purchase.sql), [q3 seller performance](../analyses/q3_seller_performance.sql).
