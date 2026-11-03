# 02 — Metric definitions

**Owner:** Analytics Engineering · **Decision owner:** Analytics Lead · **Sign-off:** Finance, for net orders and net GMV · **Values verified:** 2026-11-03, full extract, marts as built that day

Contents: [1 Purpose and conventions](#1-purpose-and-conventions) · [2 Semantic layer](#2-semantic-layer-metricflow) · [3 Order counts](#3-order-counts) · [4 Revenue and basket](#4-revenue-and-basket) · [5 Delivery](#5-delivery) · [6 Reviews](#6-reviews) · [7 Customers](#7-customers) · [8 Sellers](#8-sellers) · [9 Same name, different number](#9-same-name-different-number) · [10 Headline numbers and their source](#10-headline-numbers-and-their-source)

## 1. Purpose and conventions

### 1.1 Purpose

Three analysts reported 117,601, 99,441 and 96,478 "orders". One query double-counted through a join (fan-out); the other two were correct counts of different things under the same name ([request and scope](01_request_and_scope.md)). This document gives every metric one name, one definition and one query against the `marts` schema. A number that is not defined here is not an official number.

Each entry gives the definition, today's value, the source table and grain, what is included and excluded, edge cases, where the metric is used, whether the MetricFlow semantic layer has it, and the SQL. Every SQL block runs as-is in DuckDB against the `marts` schema (the warehouse, or the SQL playground on the app's Analyst guide page, one query at a time) and reproduces the values shown.

### 1.2 Conventions

| Topic | Rule |
|---|---|
| Date basis | `order_purchase_date`, the local calendar date of purchase. Every order-level metric is reported on it, delivery and review outcomes included: "late delivery rate, 2018-03" is the share of orders purchased in March 2018 that arrived late, whenever they arrived. |
| Time zone | Source timestamps carry no time zone and are assumed to be local `America/Sao_Paulo` time (DQ-21, [assumptions](assumptions.md)). `fct_orders.order_purchased_at_utc` exists only to join systems that log in UTC; the conversion applies the Brazilian daylight-saving rules of the period. Never build daily metrics on the UTC column. |
| Period | Totals cover the full extract (purchases 2016-09-04 to 2018-10-17). Trends, monthly averages and period comparisons use complete months only, 2017-01 to 2018-08 (`dim_date.is_complete_data_month`, DQ-19). |
| Money | BRL, nominal, as charged at purchase, `decimal(18,2)`. Revenue means GMV (items + freight); payments are a separate measure ([ADR 0004](adr/0004-payments-cancellations-and-refunds.md)). |
| Customer identity | A customer is a person, `customer_unique_id`. The source's per-order `customer_id` is not in the marts (DQ-01). |
| Geography | Orders and deliveries use `fct_orders.delivery_state` / `delivery_region`, the address on the order. "Where customers live" uses `dim_customers.customer_state`, the person's latest net-order address. They differ for 39 people whose orders went to more than one state ([ADR 0003](adr/0003-grain-fan-out-and-customer-identity.md)). |
| Status | `order_status` is a snapshot at extract time, so status-based metrics restate when statuses move. "Net orders as reported last month" needs the SCD2 snapshot `snp_olist__orders`, not `fct_orders`. |
| Data-quality flags | Flags never remove rows. Official values include flagged orders; `has_data_quality_flag` (2,428 orders, 1,653 of them net orders) is there for sensitivity checks. |
| Rates | A rate is a ratio of two counts over the same rows: sum the numerator and the denominator, then divide. Never average rates across months, states or sellers. |
| Small groups | Rates on subgroups carry a Wilson 95% interval in `analyses/` (macros `wilson_low` / `wilson_high`). By default Q1 leaves out states with fewer than 300 reviewed deliveries, and Q3 compares seller rates only for sellers with 50 or more net orders. |

The monthly pattern for any order metric (net orders here):

```sql
select
    dim_date.year_month,
    count(*) as net_orders
from marts.fct_orders as fct_orders
inner join marts.dim_date as dim_date
    on fct_orders.order_purchase_date = dim_date.date_day
where fct_orders.is_net_order
    and dim_date.is_complete_data_month
group by dim_date.year_month
order by dim_date.year_month;
```

### 1.3 Default populations

When a metric is quoted without a qualifier, these are its rows. Any other population must be named next to the number.

| Metric family | Default rows | Filter |
|---|---|---|
| Order counts, GMV, AOV | net orders | `fct_orders.is_net_order` |
| Delivery (late rate, delivery days, delay) | delivered orders with a delivery timestamp (96,470) | `fct_orders.is_late_delivery is not null` |
| Reviews | orders with a review, any status; latest answer per order (98,673) | `fct_orders.has_review` |
| Customers | people with at least one net order (94,990) | `dim_customers.has_net_order` |
| Sellers | net orders; order outcomes count for every seller in the order | `seller_scorecard` (built on net orders) |

Placed and delivered orders are separate, named metrics. Never relabel either one as "orders".

### 1.4 Owner and how to change a definition

- **Owner:** Analytics Engineering (`owner` in every mart's YAML `meta`). **Decision owner:** Analytics Lead. **Sign-off:** Finance, for net orders and net GMV.
- **Where definitions live in code:**

| Lever | File | Controls |
|---|---|---|
| Status semantics | [`dbt/seeds/order_status_mapping.csv`](../dbt/seeds/order_status_mapping.csv) | `is_net_order`, `is_terminal_status`, `order_status_group`: net, open and delivered orders |
| Thresholds used by the marts | `vars` in [`dbt/dbt_project.yml`](../dbt/dbt_project.yml) | `bad_review_max_score` (2), `payment_mismatch_tolerance_brl` (1.00), `complete_data_start_month` / `complete_data_end_month` (2017-01 / 2018-08) |
| Analysis parameters | `set variable` lines at the top of `analyses/q1`-`q3` | Q1 bad-review cut-off, minimum state size and complete-months switch; Q2 repeat window; Q3 established-seller minimum and quadrant thresholds |
| Metrics as code | [`dbt/models/semantic/_semantic_models.yml`](../dbt/models/semantic/_semantic_models.yml) | the 11 MetricFlow metrics (§2) |
| Column meaning | [`_core__models.yml`](../dbt/models/marts/core/_core__models.yml), [`_business__models.yml`](../dbt/models/marts/business/_business__models.yml), rendered as the [data dictionary](data_dictionary.md) | column descriptions |

- **Process:**
  1. Bring the proposal to the Analytics Lead with before/after numbers from the SQL in this document.
  2. A change to an official definition (net orders, net GMV, late delivery, bad review, repeat customer) gets an ADR that supersedes the current one; for the order KPI that is [ADR 0002](adr/0002-order-status-and-net-orders.md). Changing an analysis parameter does not.
  3. One pull request changes the seed or var, this document, the mart YAML descriptions and the semantic layer together. Reviewers: the Analytics Lead, plus Finance for net orders and net GMV.
  4. CI must stay green, including the reconciliation tests `assert_net_order_count_consistent_across_query_paths`, `item_net_gmv_reconciles_with_order_net_gmv`, `customer_gmv_reconciles_with_net_order_gmv` and `seller_gmv_reconciles_with_net_order_gmv`.
  5. Announce the change with the before/after numbers. Every mart except `fct_order_items` is rebuilt in full, so a new definition restates every past month.
- **Two traps:**
  - `fct_order_items` is incremental and only re-processes recent and open orders ([ADR 0005](adr/0005-incremental-fct-order-items.md)). A seed change that touches a terminal status (`delivered`, `canceled`, `unavailable`) needs `dbt build --full-refresh -s fct_order_items`; until then `item_net_gmv_reconciles_with_order_net_gmv` fails.
  - `bad_review_max_score` exists twice. The dbt var drives `is_bad_review` in the marts; Q1's SQL variable of the same name recomputes the flag from `review_score` for the app's bad-review selector and does not touch the marts. Keep them equal outside an explicit sensitivity check.

## 2. Semantic layer (MetricFlow)

[`dbt/models/semantic/_semantic_models.yml`](../dbt/models/semantic/_semantic_models.yml) holds the agreed definitions as code, so any tool that asks MetricFlow for `net_orders` gets the same number as the SQL in this document. It has two semantic models:

- **`orders`** on `fct_orders` (one row per order, any status). Time dimension `order_purchase_date`, so `metric_time` is the local purchase date. Entities `order` (`order_id`) and `customer` (`customer_unique_id`). Dimensions `order_status`, `order_status_group`, `delivery_state`, `delivery_region`, `primary_payment_type`, `is_net_order`.
- **`customers`** on `dim_customers` (one row per person). Entity `customer`; dimensions `customer_state`, `customer_region`, `is_repeat_customer`. It has no measures, so there are no customer metrics; through the `customer` entity, order metrics can be grouped by these attributes.

The 11 metrics, in the order the file defines them. Values are what the equivalent SQL returns on the full extract with no filter.

| Metric | Label | Type | Definition | Value |
|---|---|---|---|---:|
| `placed_orders` | Placed orders | simple | measure `count(order_id)` | 99,441 |
| `net_orders` | Net orders (official order KPI) | simple | measure `sum(case when is_net_order then 1 else 0 end)` | 98,207 |
| `delivered_orders` | Delivered orders | simple | measure `sum(case when is_delivered then 1 else 0 end)` | 96,478 |
| `net_gmv_brl` | Net GMV (BRL) | simple | measure `sum(case when is_net_order then order_gmv_brl else 0 end)` | 15,735,527.03 |
| `average_order_value_brl` | Average order value (BRL) | ratio | `net_gmv_brl` / `net_orders` | 160.23 |
| `late_delivery_rate` | Late delivery rate | ratio | `late_deliveries` / `measured_deliveries` | 6.77% |
| `late_deliveries` | Late deliveries | simple | measure `sum(case when is_late_delivery then 1 else 0 end)` | 6,534 |
| `measured_deliveries` | Measured deliveries | simple | measure `sum(case when is_late_delivery is not null then 1 else 0 end)` | 96,470 |
| `bad_review_rate` | Bad review rate | ratio | `bad_reviews` / `reviewed_orders` | 14.69% |
| `bad_reviews` | Bad reviews | simple | measure `sum(case when is_bad_review then 1 else 0 end)` | 14,494 |
| `reviewed_orders` | Reviewed orders | simple | measure `sum(case when has_review then 1 else 0 end)` | 98,673 |

Querying it (`make metrics` runs the first five by year; CI runs `net_orders,net_gmv_brl` as a smoke test):

```bash
cd dbt && uv run --group semantic mf query --metrics net_orders,late_delivery_rate --group-by metric_time__month
```

**Filters.** Only `net_orders`, `net_gmv_brl` and `average_order_value_brl` restrict to net orders inside the measure. `placed_orders`, `reviewed_orders`, `bad_reviews` and `bad_review_rate` count every status: `bad_review_rate` is 14.69% over all reviewed orders and 13.87% over net orders, the population of `customer_360` and `seller_scorecard`. Add a filter when you need the net-order version:

```bash
cd dbt && uv run --group semantic mf query --metrics bad_review_rate --group-by metric_time__month \
  --where "{{ Dimension('order__is_net_order') }} = true"
```

The late-delivery metrics need no filter: `is_late_delivery` is null except for delivered orders with a delivery timestamp.

**Not in the semantic layer:** open orders, cancellation rate, items subtotal, freight, payment total, units sold, on-time rate, delivery days, delay days, average review score, review coverage, and every customer and seller metric. They are mart columns or SQL in this document; customer and seller metrics live at person and seller grain in `customer_360` and `seller_scorecard`.

## 3. Order counts

Every order count comes from `marts.fct_orders`, one row per order in any status. What each status means comes from the seed ([ADR 0002](adr/0002-order-status-and-net-orders.md)):

| Status | Orders | Net order | Terminal |
|---|---:|:---:|:---:|
| `delivered` | 96,478 | yes | yes |
| `shipped` | 1,107 | yes | no |
| `invoiced` | 314 | yes | no |
| `processing` | 301 | yes | no |
| `created` | 5 | yes | no |
| `approved` | 2 | yes | no |
| `canceled` | 625 | no | yes |
| `unavailable` | 609 | no | yes |

### 3.1 Placed orders

Every order placed on the marketplace, whatever happened to it afterwards. Use it for demand and funnel questions, never as "orders".

**Value** 99,441 · **Source** `marts.fct_orders`, one row per order · **MetricFlow** `placed_orders`

- **Includes:** all eight statuses, including 625 canceled and 609 unavailable orders and the 775 orders without items (DQ-08).
- **Excludes:** nothing.
- **Edge cases:** An order counts on its purchase date even if it was canceled later. Every order placed after 2018-09-03 was canceled, so in the partial months 2018-09 (16 placed, 1 net) and 2018-10 (4 placed, 0 net) placed orders run far ahead of net orders.
- **Used in:** Q0 `named_order_metrics`, [`sql/metrics/02_official_order_counts_by_month.sql`](../sql/metrics/02_official_order_counts_by_month.sql), the Dashboard caption, `dim_customers.orders_placed` (per person).

```sql
select count(*) as placed_orders
from marts.fct_orders;
```

### 3.2 Net orders (official order KPI)

Orders placed minus those canceled or unavailable. When someone says "orders" without a qualifier, this is the number.

**Value** 98,207 · **Source** `marts.fct_orders.is_net_order`, one row per order · **MetricFlow** `net_orders`

- **Includes:** statuses `created`, `approved`, `invoiced`, `processing`, `shipped` and `delivered`, as set in [`order_status_mapping.csv`](../dbt/seeds/order_status_mapping.csv). The 1,729 open orders (§3.4) count.
- **Excludes:** `canceled` (625) and `unavailable` (609).
- **Edge cases:**
  - 8 net orders have no items and GMV 0 (DQ-08); they stay in the count.
  - An order is not a checkout. A basket with items from several sellers can become several orders in the same second (290 same-second groups covering 582 orders, DQ-05). Net orders count orders.
  - Flagged orders are included. The 6 canceled orders that carry a delivery timestamp stay excluded: status wins over timestamps (DQ-14).
- **Used in:** Overview and Dashboard tiles and charts; Q0 (five query paths); `sql/metrics/01` and `02`; `dim_customers.frequency_orders` (per person); the dbt test [`assert_net_order_count_consistent_across_query_paths`](../dbt/tests/singular/assert_net_order_count_consistent_across_query_paths.sql), which fails the build if six independent query paths disagree.

```sql
select count(*) as net_orders
from marts.fct_orders
where is_net_order;
```

### 3.3 Delivered orders

Orders whose status is `delivered`. A fulfilment metric for ops and logistics, not the order KPI.

**Value** 96,478 · **Source** `marts.fct_orders.is_delivered` · **MetricFlow** `delivered_orders`

- **Includes:** status `delivered`, with or without a delivery timestamp.
- **Excludes:** every other status, including open orders that may still arrive.
- **Edge cases:**
  - 8 delivered orders have no delivery timestamp (DQ-14). They count here but have no delivery metrics, so delivered orders are 8 more than measured deliveries (96,470, §5.1).
  - The 6 canceled orders with a delivery timestamp are not delivered orders.
  - Recent purchase months lag until deliveries land (2018-08: 6,351 delivered vs 6,421 net orders), so this series restates with every new extract.
- **Used in:** Q0, `sql/metrics/02`, `customer_360.delivered_orders`, `seller_scorecard.delivered_orders`.

```sql
select count(*) as delivered_orders
from marts.fct_orders
where is_delivered;
```

### 3.4 Open orders

Net orders whose status can still change: `created`, `approved`, `invoiced`, `processing` or `shipped`.

**Value** 1,729 (shipped 1,107, invoiced 314, processing 301, created 5, approved 2) · **Source** `marts.fct_orders.is_terminal_status = false` · **MetricFlow** no

- **Includes:** the five non-terminal statuses, by the seed's `is_terminal_status`.
- **Excludes:** the terminal statuses `delivered`, `canceled` and `unavailable`.
- **Edge cases:**
  - In a static extract, open orders never resolve. 1,584 of them were purchased before 2018-07-01, and all 1,107 `shipped` orders were past their estimated delivery date when the extract ends (2018-10-17). This suggests the source stopped updating some statuses ([ADR 0002](adr/0002-order-status-and-net-orders.md)). They are 1.76% of net orders and R$315,753.28 of net GMV.
  - They are the reason `fct_order_items` re-processes every order that was open at the last run ([ADR 0005](adr/0005-incremental-fct-order-items.md)).
- **Used in:** `fct_orders.is_terminal_status`, the incremental logic of `fct_order_items`, the README's limitations.

```sql
select count(*) as open_orders
from marts.fct_orders
where is_net_order
    and not is_terminal_status;
```

### 3.5 Cancellation rate

Share of placed orders that were canceled or unavailable: (canceled + unavailable) / placed orders. It equals 1 − net orders / placed orders.

**Value** 1.24% (1,234 / 99,441; canceled 0.63%, unavailable 0.61%); 1.19% in complete months (1,182 / 99,092) · **Source** `marts.fct_orders` · **MetricFlow** no (derive as 1 − `net_orders` / `placed_orders`)

- **Includes:** both failure statuses in the numerator, every placed order in the denominator.
- **Edge cases:**
  - Reported on the purchase date: a cancellation counts in the month the order was placed. The source has no cancellation timestamp, so lead time to cancellation cannot be measured; `snp_olist__orders` will record status changes once loads repeat.
  - The partial months 2018-09 and 2018-10 are almost entirely canceled orders; quote the rate on complete months.
  - A cancellation is not a refund. These 1,234 orders still carry R$269,735.11 of payments, and the source does not show whether the money was returned ([ADR 0004](adr/0004-payments-cancellations-and-refunds.md)).
- **Used in:** the Dashboard caption (canceled or unavailable count), `customer_360.canceled_or_unavailable_orders`.

```sql
select
    count(*) filter (where order_status = 'canceled') as canceled_orders,
    count(*) filter (where order_status = 'unavailable') as unavailable_orders,
    count(*) filter (where not is_net_order) as canceled_or_unavailable_orders,
    1.0 * count(*) filter (where not is_net_order) / count(*) as cancellation_rate
from marts.fct_orders;
```

## 4. Revenue and basket

Revenue is GMV: item prices plus freight, fixed at purchase. Net GMV is bookings. It is not cash, which also includes card installment interest, and not recognised revenue, because the source has no refunds ([ADR 0004](adr/0004-payments-cancellations-and-refunds.md)).

### 4.1 Net GMV

Gross merchandise value of net orders: item prices plus freight. The revenue measure for sales, AOV, category and seller questions.

**Value** R$15,735,527.03 · **Source** `marts.fct_orders.order_gmv_brl` (order grain) or `marts.fct_order_items.item_total_brl` (unit grain); both return the same total · **MetricFlow** `net_gmv_brl`

- **Includes:** net orders, open orders among them.
- **Excludes:** canceled and unavailable orders (R$108,026.21 of item GMV, kept in the tables and out of net GMV); installment interest; refunds, which the source does not record.
- **Edge cases:**
  - The 8 net orders without items contribute 0.
  - Freight is 14.2% of net GMV; use the items subtotal (§4.2) for price-only questions.
  - At unit grain, filter `fct_order_items.is_net_order` before summing. The test `item_net_gmv_reconciles_with_order_net_gmv` holds the two grains exactly equal (tolerance 0).
- **Used in:** Dashboard tile, monthly chart, state table and category chart; Q0; `sql/metrics/01` and `02`; `seller_scorecard.gmv_brl` and `dim_customers.monetary_gmv_brl`, which both sum to it exactly.

```sql
select sum(order_gmv_brl) as net_gmv_brl
from marts.fct_orders
where is_net_order;

-- the same total at unit grain, for product, category or seller cuts
select sum(item_total_brl) as net_gmv_brl
from marts.fct_order_items
where is_net_order;
```

### 4.2 Items subtotal

Sum of item prices of net orders, without freight.

**Value** R$13,494,400.74 · **Source** `marts.fct_orders.items_subtotal_brl`; unit grain `fct_order_items.item_price_brl` · **MetricFlow** no

- **Includes / excludes:** as net GMV, minus freight.
- **Edge cases:** Prices are per unit. The source has no quantity column, so 3 units of a product are 3 rows (DQ-04).
- **Used in:** `seller_scorecard.item_revenue_brl` and `avg_item_price_brl`.

```sql
select sum(items_subtotal_brl) as items_subtotal_brl
from marts.fct_orders
where is_net_order;
```

### 4.3 Freight

Freight charged to customers on net orders.

**Value** R$2,241,126.29 (14.2% of net GMV) · **Source** `marts.fct_orders.freight_total_brl`; unit grain `fct_order_items.freight_value_brl` · **MetricFlow** no

- **Includes / excludes:** as net GMV.
- **Edge cases:** Olist splits an order's freight across its item rows; the marts sum it per order. It is the shipping price charged to the customer (payments equal items + freight to the cent for 98,362 of 98,665 orders); the source has no carrier cost. Some units carry zero freight.
- **Used in:** `seller_scorecard.freight_brl`; part of every GMV figure.

```sql
select sum(freight_total_brl) as freight_brl
from marts.fct_orders
where is_net_order;
```

### 4.4 Payment total

What customers paid, as recorded in the payment rows (credit card, boleto, voucher, debit card).

**Value** R$15,739,137.01 on net orders; R$16,008,872.12 on all orders, equal to the source payments table (test `fct_orders_payments_reconcile_with_staging`) · **Source** `marts.fct_orders.payment_total_brl` · **MetricFlow** no

- **Includes:** every payment row of the order, card installment interest included.
- **Edge cases:**
  - Over the 98,665 orders that have both items and payments, payments exceed items + freight by R$2,870.39. 249 orders differ by more than R$1, and 229 of the 232 overpaid ones are card payments in installments (DQ-16).
  - Canceled and unavailable orders keep their payments (R$143,255.60 and R$126,479.51), and there is no refund data.
  - 1 net order has no payment record (`has_payment = false`).
  - Use it for cash and payment-mix questions only, never for AOV or seller revenue. Analyst B's "revenue" of R$16,008,872.12 was this all-status total.
- **Used in:** `customer_360.lifetime_paid_brl`; the payment-mix columns (`credit_card_amount_brl` and the rest); the tolerance check on the Raw data issues page (`payment_gmv_difference_brl`); [`sql/data_quality/07_payment_reconciliation.sql`](../sql/data_quality/07_payment_reconciliation.sql).

```sql
select
    sum(payment_total_brl) filter (where is_net_order) as payment_total_net_orders_brl,
    sum(payment_total_brl) as payment_total_all_orders_brl
from marts.fct_orders;
```

### 4.5 Average order value

Net GMV divided by net orders.

**Value** R$160.23; R$160.18 on the Dashboard default (2017-01 to 2018-08) · **Source** `marts.fct_orders` · **MetricFlow** `average_order_value_brl` (ratio `net_gmv_brl` / `net_orders`)

- **Includes / excludes:** as net GMV, in the numerator and the denominator.
- **Edge cases:**
  - It is a mean and large baskets pull it up: the median net order with items is R$105.28, the largest R$13,664.08.
  - The 8 net orders without items stay in the denominator with GMV 0 (without them AOV is R$160.24).
  - For a month, state or segment, recompute the ratio. Never average monthly AOVs.
  - Per person, `dim_customers.avg_order_value_brl` is `monetary_gmv_brl / frequency_orders`.
- **Used in:** Dashboard tile, `sql/metrics/02` (by month), `dim_customers` and `customer_360`.

```sql
select sum(order_gmv_brl) / count(*) as average_order_value_brl
from marts.fct_orders
where is_net_order;
```

### 4.6 Units sold

Item rows (units) in net orders.

**Value** 112,101 (of 112,650 item rows in all statuses) · **Source** `marts.fct_order_items`, one row per unit · **MetricFlow** no

- **Excludes:** the 549 item rows of canceled and unavailable orders.
- **Edge cases:** One row is one unit (DQ-04). Count rows for units and `count(distinct order_id)` for orders; 6,968 orders (7,088 order-product pairs) contain the same product on more than one row.
- **Used in:** `customer_360.total_items`, `seller_scorecard.items_sold`.

```sql
select count(*) as units_sold
from marts.fct_order_items
where is_net_order;
```

## 5. Delivery

Delivery metrics exist only for delivered orders with a delivery timestamp (`is_late_delivery is not null`, 96,470 orders), and are reported on the purchase date like every order metric.

### 5.1 Late delivery rate

Share of delivered orders that reached the customer on a later calendar day than the estimated delivery date shown at purchase.

**Value** 6.77% (6,534 / 96,470); 6.79% on the Dashboard default (2017-01 to 2018-08) · **Source** `marts.fct_orders.is_late_delivery` · **MetricFlow** `late_delivery_rate` = `late_deliveries` / `measured_deliveries`

- **Includes:** status `delivered` with a delivery timestamp.
- **Excludes:** the 8 delivered orders without a delivery timestamp, the 6 canceled orders that have one, and every order not yet delivered.
- **Edge cases:**
  - It compares dates, not times: delivered on the estimated day is on time (unit test `test_late_delivery_and_status_logic`).
  - Orders that never arrived are outside the rate. All 1,107 open `shipped` orders were past their estimate when the extract ends; counted as late, they would raise the rate to 7.83%. The published rate describes completed deliveries.
  - Estimates are generous (median promise 24 days, median delivery 10), so "late" means late against the promise, not slow.
  - Orders with contradictory timestamps stay in: 1,387 of the 96,470 (DQ-14 counts 1,410 across all statuses).
- **Used in:** Dashboard tile, monthly line and state table; Q1 (late share per state); Q3 `handover_vs_outcome`; `customer_360.late_delivery_rate`; `seller_scorecard.late_delivery_rate` (§8.5).

```sql
select
    count(*) filter (where is_late_delivery) as late_deliveries,
    count(*) as measured_deliveries,
    1.0 * count(*) filter (where is_late_delivery) / count(*) as late_delivery_rate
from marts.fct_orders
where is_late_delivery is not null;
```

### 5.2 On-time rate

Share of delivered orders that arrived on or before the estimated date: 1 − late delivery rate, on the same rows.

**Value** 93.23% · **Source** `marts.fct_orders.is_late_delivery = false` · **MetricFlow** no (1 − `late_delivery_rate`)

- **Includes:** early deliveries and the 1,292 that arrived on the estimated day.
- **Edge cases:** as for the late delivery rate.
- **Used in:** the "on time" groups of Q1 (`late_vs_on_time`) and Q2 (`repeat_by_first_experience`).

```sql
select 1.0 * count(*) filter (where not is_late_delivery) / count(*) as on_time_rate
from marts.fct_orders
where is_late_delivery is not null;
```

### 5.3 Delivery days

Calendar days from the purchase date to the delivery date. The headline is the median.

**Value** median 10 days; mean 12.50; 90th percentile 23; maximum 210 · **Source** `marts.fct_orders.delivery_days` · **MetricFlow** no

- **Includes:** delivered orders with a delivery timestamp.
- **Edge cases:**
  - Purchase to doorstep: payment approval, seller handling and carrier transit together, weekends and holidays included. The seller's step is measured separately by the late handover rate (§8.3).
  - Local calendar dates, so an order bought in the evening and delivered the next morning counts 1 day. One order counts 0.
- **Why the median.** The distribution has a long right tail: 43 deliveries took more than 120 days (DQ-13), up to 210, and the tail pulls the mean 2.5 days above the median. The median is what a typical customer waited and barely moves when a few extreme cases appear. The mean is published too (the Dashboard monthly line, `customer_360.avg_delivery_days`, `seller_scorecard.avg_delivery_days`, Q1 `avg_delivery_days`) and moves more when the tail grows. Label which one you quote.
- **Used in:** Dashboard tile "Median delivery time" and state table (median); Dashboard monthly line (mean); Q1 `by_state` (both).

```sql
select
    median(delivery_days) as median_delivery_days,
    avg(delivery_days) as avg_delivery_days
from marts.fct_orders
where delivery_days is not null;
```

### 5.4 Delivery delay days

Delivery date minus estimated delivery date, in days. Positive is late, negative is early, 0 is the estimated day.

**Value** median −12 (the typical order arrives 12 days before its estimate); among late deliveries, median 7 days late, mean 10.6 · **Source** `marts.fct_orders.delivery_delay_days` · **MetricFlow** no

- **Edge cases:** `is_late_delivery` is exactly `delivery_delay_days > 0` (no exceptions in the data). Same rows and caveats as §5.1.
- **Used in:** Q1 `by_delay`: the bad review rate in eight buckets from 15+ days early to 15+ days late.

```sql
select
    median(delivery_delay_days) as median_delay_days,
    median(delivery_delay_days) filter (where is_late_delivery) as median_days_late_when_late
from marts.fct_orders
where delivery_delay_days is not null;
```

## 6. Reviews

Olist sends a satisfaction survey for each order, scored 1-5. The marts keep the latest answer per order (`review_score`) and the number of answers (`review_count`). Review metrics are shares of orders, never counts of `review_id` (DQ-02, DQ-03), and are reported on the order's purchase date, not the answer date.

### 6.1 Bad review rate

Share of reviewed orders whose latest review is a bad review (1-2 stars).

**Value** 14.69% (14,494 / 98,673 reviewed orders, any status) · **Source** `marts.fct_orders.is_bad_review` · **MetricFlow** `bad_review_rate` = `bad_reviews` / `reviewed_orders`

The population changes the number, so name it whenever it is not the default:

| Population | Bad review rate | Used by |
|---|---:|---|
| All reviewed orders (default) | 14.69% (14,494 / 98,673) | MetricFlow `bad_review_rate` |
| Reviewed net orders | 13.87% (13,524 / 97,473) | `customer_360`, `seller_scorecard` |
| Reviewed delivered orders with a delivery date | 12.81% (12,272 / 95,824) | reference only |
| The same, complete months only | 12.80% (12,228 / 95,560) | Q1 |
| Reviewed canceled or unavailable orders | 80.8% (970 / 1,200) | reference only |

- **Includes:** every order with a review. A canceled order still produced a customer experience.
- **Edge cases:**
  - Bad means `review_score <= bad_review_max_score` (dbt var, default 2).
  - 547 orders have 2-3 answers; the latest is kept (DQ-03; unit test `test_review_dedup_keeps_latest_answer`). 64 surveys are dated before the purchase and are kept (DQ-15).
  - A review rates the whole order (product, seller and carrier), not one party.
- **Used in:** Q1, where late deliveries get a bad review 62.42% of the time vs 9.25% on time (an association); Q2 `repeat_by_first_experience`; Q3 `handover_vs_outcome`; `seller_scorecard.bad_review_rate` (§8.4); `customer_360.bad_review_orders`.

```sql
select
    count(*) filter (where is_bad_review) as bad_reviews,
    count(*) as reviewed_orders,
    1.0 * count(*) filter (where is_bad_review) / count(*) as bad_review_rate
from marts.fct_orders
where has_review;
-- for reviewed net orders, add:  and is_net_order
```

### 6.2 Average review score

Mean of the latest review score (1-5) over reviewed orders.

**Value** 4.09 over all reviewed orders; 4.12 over net orders; 4.09 on the Dashboard default (2017-01 to 2018-08, all statuses) · **Source** `marts.fct_orders.review_score` · **MetricFlow** no

- **Includes / excludes:** reviewed orders in any status (98,673); the 768 orders without a review are left out, not scored 0.
- **Edge cases:** The scale is ordinal and the distribution J-shaped (57.8% five stars, 11.5% one star), so the mean hides the split. Use the bad review rate for decisions and the average for trend context. Recompute from orders; never average per-month or per-seller averages.
- **Used in:** Dashboard tile and monthly table; Q1 `late_vs_on_time` (4.29 on time vs 2.27 late); `customer_360.avg_review_score` and `seller_scorecard.avg_review_score` (net orders); Q3 `watchlist`.

```sql
select avg(review_score) as avg_review_score
from marts.fct_orders
where has_review;
```

### 6.3 Review coverage

Share of orders with at least one survey answer.

**Value** 99.23% of placed orders (98,673 / 99,441); 99.25% of net orders · **Source** `marts.fct_orders.has_review` · **MetricFlow** no (derive as `reviewed_orders` / `placed_orders`)

- **Edge cases:** 768 orders have no review (DQ-08). With coverage this high, non-response barely matters: even if every unreviewed order were a bad review, the bad review rate over all placed orders would be 15.35%, under one point above 14.69%. 543 orders have 2 answers and 4 have 3.
- **Used in:** the denominator of every review metric (MetricFlow `reviewed_orders`).

```sql
select 1.0 * count(*) filter (where has_review) / count(*) as review_coverage
from marts.fct_orders;
```

## 7. Customers

A customer is a person, `customer_unique_id`. The source's `customer_id` is issued per order (99,441 ids for 96,096 people) and is not in the marts; counted on it, the repeat rate is 0% (DQ-01, [`sql/metrics/03_customer_key_trap_on_raw.sql`](../sql/metrics/03_customer_key_trap_on_raw.sql)).

### 7.1 Customers

People with at least one net order.

**Value** 94,990; 94,707 on the Dashboard default (2017-01 to 2018-08) · **Source** `marts.dim_customers.has_net_order`, one row per person; for a period or segment, `count(distinct customer_unique_id)` on `fct_orders` · **MetricFlow** no

- **Excludes:** the 1,106 people in `dim_customers` whose only orders were canceled or unavailable (the table has 96,096 rows).
- **Edge cases:** Distinct counts are not additive: recount for each period instead of summing months or states. For geography, see the convention in §1.2.
- **Used in:** the Dashboard caption and region split; the denominator of the repeat rate; Q2.

```sql
select count(*) as customers
from marts.dim_customers
where has_net_order;

-- for a period or segment, count people on the fact
select count(distinct customer_unique_id) as customers
from marts.fct_orders
where is_net_order;
```

### 7.2 Repeat customer and repeat rate

A repeat customer bought net orders on two or more different days. The repeat rate is repeat customers / customers (§7.1).

**Value** 2.17% (2,065 / 94,990) · **Source** `marts.dim_customers.is_repeat_customer` (`purchase_days >= 2`); `customer_360.customer_lifecycle_stage = 'repeat'` · **MetricFlow** no metric; `is_repeat_customer` is a dimension of the `customers` semantic model

Three defensible definitions on the same 94,990 customers:

| Definition | Repeat customers | Repeat rate |
|---|---:|---:|
| 2+ net orders | 2,888 | 3.04% |
| 2+ checkouts (distinct purchase timestamps) | 2,638 | 2.78% |
| **2+ purchase days (official)** | **2,065** | **2.17%** |

**Why purchase days.** A basket with items from several sellers can be split into one order per seller in the same second (DQ-05), so "2+ orders" counts a single purchase as a return. Distinct timestamps fix that, but still count a second checkout on the same day, such as adding a forgotten item, as coming back. Buying again on a different day is what retention work tries to change, and it is the most conservative of the three. Counting orders would overstate repeat buying by 40% (3.04% vs 2.17%).

- **Edge cases:**
  - Lifetime and unwindowed: a customer first seen in 2018-08 had at most about a month to return, one first seen in 2017-01 about 20 months. Compare cohorts or periods with §7.3, not with this rate.
  - `frequency_orders >= 2` (2,888) is not the repeat flag: it counts orders.
- **Used in:** Business questions tile "Customers who ever bought again"; Q2 `definition_sensitivity`; `customer_360.customer_lifecycle_stage` (repeat 2,065, one_time 92,925, no_net_order 1,106).

```sql
select
    count(*) filter (where is_repeat_customer) as repeat_customers,
    count(*) as customers,
    1.0 * count(*) filter (where is_repeat_customer) / count(*) as repeat_rate
from marts.dim_customers
where has_net_order;

-- the three definitions side by side (Q2 definition_sensitivity)
with

by_person as (

    select
        customer_unique_id,
        count(*) as net_orders,
        count(distinct order_purchased_at) as checkouts,
        count(distinct order_purchase_date) as purchase_days

    from marts.fct_orders
    where is_net_order
    group by customer_unique_id

)

select
    1.0 * count(*) filter (where net_orders >= 2) / count(*) as by_net_orders,
    1.0 * count(*) filter (where checkouts >= 2) / count(*) as by_checkouts,
    1.0 * count(*) filter (where purchase_days >= 2) / count(*) as by_purchase_days_official

from by_person;
```

### 7.3 Repeat rate within N days (cohorts)

Share of a first-purchase-month cohort whose second purchase day falls within N days of the first (default N = 180). Use it to compare cohorts or periods.

**Value** 2.00% pooled over the 14 fully observed cohorts at 180 days (1,126 / 56,337; cohorts 2017-01 to 2018-02), ranging from 1.66% to 2.60% by cohort · **Source** `marts.customer_360` (`first_net_order_month`, `days_to_second_purchase`) · **MetricFlow** no

- **Fully observed rule:** a cohort is reported only once its last customer has had the full N days before the data ends: latest first-purchase date + N ≤ `rfm_reference_date` (2018-09-03). Later cohorts would look artificially low; the app shows them in gray.
- **Edge cases:** N is a parameter (`repeat_window_days` in Q2; the app slider runs from 30 to 360 days). With about 2% repeaters, small cohorts are imprecise; Q2 gives a Wilson 95% interval per cohort (for example 1.01% to 2.94% for 2017-01, 752 customers).
- **Used in:** Q2 `cohort_repeat` and `repeat_by_first_experience`; Business questions tile "…within N days (fully observed cohorts)".

```sql
select
    first_net_order_month,
    count(*) as customers,
    1.0 * count(*) filter (where days_to_second_purchase <= 180) / count(*) as repeat_rate_180d
from marts.customer_360
where has_net_order
    and first_net_order_month between date '2017-01-01' and date '2018-08-01'
group by first_net_order_month
-- report a cohort only once its last customer has had the full 180 days
having max(cast(first_net_order_at as date)) + 180 <= max(rfm_reference_date)
order by first_net_order_month;
```

### 7.4 Time to second purchase

Days between a repeat customer's first and second purchase days (net orders).

**Value** median 74 days over 2,065 repeat customers; 10.3% return within 7 days, 54.9% within 90, 75.9% within 180, 95.8% within 365 · **Source** `marts.customer_360.days_to_second_purchase` (null for one-time customers) · **MetricFlow** no

- **Edge cases:**
  - At least 1 by construction: orders on the same day are one purchase day.
  - Right-censored: only customers who already came back are measured, and long gaps could only be observed for early cohorts. The figure is biased toward short gaps; read it as "among customers who returned within the extract".
  - The mean (114.9 days) is pulled up by gaps of up to 609 days; quote the median.
- **Used in:** Q2 `time_to_second_purchase`; the repeat window in §7.3.

```sql
select
    count(*) as repeat_customers,
    median(days_to_second_purchase) as median_days_to_second_purchase
from marts.customer_360
where days_to_second_purchase is not null;
```

### 7.5 RFM fields

Inputs for RFM segmentation, one row per person in `dim_customers` (repeated in `customer_360`). The marts provide the inputs; scores and segments belong to the analysis.

**Source** `marts.dim_customers` · **MetricFlow** no

| Field | Definition | Values (94,990 customers) |
|---|---|---|
| `rfm_reference_date` | The "today" of the extract: the last net-order purchase date | 2018-09-03 on every row |
| `recency_days` (R) | Days from the person's last net order to `rfm_reference_date` | 0 to 729; median 224, mean 243.3 |
| `frequency_orders` (F) | Number of net orders | sums to 98,207; 2+ for only 2,888 customers |
| `monetary_gmv_brl` (M) | GMV of the person's net orders, BRL | sums to R$15,735,527.03; median R$107.90, mean R$165.65 |
| `avg_order_value_brl` | `monetary_gmv_brl / frequency_orders` | per-person AOV; null for the 1,106 people without a net order |

- **Why this reference date.** The data is historical, so measuring against today would make every customer look lost. The last order of any status is 44 days later (2018-10-17), but every one of the 16 orders placed after 2018-09-03 was canceled; using that date would add 44 days to every recency.
- **Edge cases:**
  - The 1,106 people without a net order have null recency, frequency 0 and monetary 0. Filter `has_net_order`.
  - F counts orders, so a split checkout counts twice. For "came back", use `purchase_days` or `is_repeat_customer`. With F = 1 for almost everyone, frequency barely separates customers in this data.
  - M is GMV, not payments, so installment interest is excluded.
- **Reconciles:** `sum(frequency_orders)` equals net orders and `sum(monetary_gmv_brl)` equals net GMV (Q0 path C; test `customer_gmv_reconciles_with_net_order_gmv`).
- **Used in:** `customer_360`; Q0; Q2, which uses `rfm_reference_date` as the end of observation.

```sql
select
    customer_unique_id,
    rfm_reference_date,
    recency_days,
    frequency_orders,
    monetary_gmv_brl
from marts.dim_customers
where has_net_order;

-- how the marts derive them; reproduces dim_customers for all 94,990 customers
with

reference as (

    select max(order_purchase_date) as rfm_reference_date
    from marts.fct_orders
    where is_net_order

)

select
    fct_orders.customer_unique_id,
    any_value(reference.rfm_reference_date) as rfm_reference_date,
    date_diff('day', max(fct_orders.order_purchase_date), any_value(reference.rfm_reference_date))
        as recency_days,
    count(*) as frequency_orders,
    sum(fct_orders.order_gmv_brl) as monetary_gmv_brl

from marts.fct_orders as fct_orders
cross join reference
where fct_orders.is_net_order
group by fct_orders.customer_unique_id;
```

## 8. Sellers

Seller metrics come from `marts.seller_scorecard`, one row per seller, built on net orders. GMV is item-level and splits exactly between sellers. Delivery and review outcomes are recorded per order, so in the 1.3% of net orders with more than one seller the outcome counts for every seller in the order ([ADR 0003](adr/0003-grain-fan-out-and-customer-identity.md)). Rates on small sellers are noisy: filter on `net_orders` before ranking.

### 8.1 Active and established sellers

Active: at least one net order. Established: at least 50 net orders, the default population for comparing seller rates.

**Value** 3,053 active of 3,095 sellers; 428 established, holding 68.5% of net GMV · **Source** `marts.seller_scorecard.net_orders` · **MetricFlow** no

- **`net_orders` per seller** counts distinct net orders that contain at least one of the seller's items. Summed over sellers it gives 99,542, not the 98,199 net orders with items, because a multi-seller order counts once for each seller. Never sum it to get marketplace orders.
- **The threshold is a parameter, not a business tier:** `min_seller_orders` in Q3, default 50; the app slider runs from 10 to 300.

| Minimum net orders | 10 | 30 | **50** | 100 | 300 |
|---|---:|---:|---:|---:|---:|
| Established sellers | 1,261 | 634 | **428** | 210 | 56 |

- **Why 50:** a judgment call that trades coverage for precision. Even at 50 orders, an observed 10% rate has a Wilson 95% interval of 4.3% to 21.4%, so treat ranks near a threshold as provisional.
- **Edge cases:** The 42 inactive sellers have items only in canceled or unavailable orders.
- **Used in:** Q3 (`gmv_concentration` divides by active sellers; `seller_quadrants` and `watchlist` use established sellers); the app's quadrant scatter; the Dashboard region split (active sellers).

```sql
select
    count(*) filter (where net_orders > 0) as active_sellers,
    count(*) filter (where net_orders >= 50) as established_sellers
from marts.seller_scorecard;
```

### 8.2 Seller GMV, share, rank and cumulative share

- `gmv_brl`: GMV (price + freight) of the seller's items in net orders.
- `gmv_share`: `gmv_brl` / marketplace net GMV.
- `gmv_rank`: 1 = largest GMV; ties broken by `seller_id`.
- `cumulative_gmv_share`: running share of net GMV with sellers sorted by rank (the Pareto curve).
- "Top X% of sellers": the share held by the first ceil(X% × active sellers) ranks.

**Value** `gmv_brl` sums to R$15,735,527.03, exactly net GMV (test `seller_gmv_reconciles_with_net_order_gmv`); the largest seller holds 1.58%; the top 10% of active sellers (306) hold 66.7% · **Source** `marts.seller_scorecard` · **MetricFlow** no

| Top share of active sellers | 1% | 5% | 10% | 20% | 50% |
|---|---:|---:|---:|---:|---:|
| Sellers | 31 | 153 | 306 | 611 | 1,527 |
| Share of net GMV | 25.7% | 52.5% | 66.7% | 81.9% | 96.5% |

- **Edge cases:** GMV includes the freight on the seller's items (`item_revenue_brl` is price only). Inactive sellers have GMV 0 and rank last (3,054 to 3,095), so "top X%" divides by the 3,053 active sellers, not all 3,095.
- **Used in:** Q3 `gmv_concentration` and `pareto_curve`; Business questions tile "GMV held by the top 10% of sellers".

```sql
select seller_id, gmv_brl, gmv_rank, gmv_share, cumulative_gmv_share
from marts.seller_scorecard
order by gmv_rank;

-- share of net GMV held by the top 10% of active sellers (Q3 gmv_concentration)
with

active as (

    select * from marts.seller_scorecard
    where net_orders > 0

)

select max(cumulative_gmv_share) as gmv_share_top_10pct
from active
where gmv_rank <= (select ceil(count(*) * 0.10) from active);
```

### 8.3 Late handover rate

The seller's handover SLA: of the seller's single-seller net orders that were handed to the carrier, the share that reached the carrier after the seller's shipping limit.

**Value** 9.12% for the marketplace (8,787 / 96,305 handed-over single-seller net orders); median 4.96% among established sellers · **Source** `marts.seller_scorecard.late_handover_rate`, denominator `handed_over_orders`; built from `fct_orders.order_delivered_to_carrier_at` and `fct_order_items.shipping_limit_at` · **MetricFlow** no

- **Includes:** single-seller net orders with a carrier handover timestamp, whether delivered yet or still shipped.
- **Excludes:** multi-seller orders. The source has one carrier timestamp per order while each seller has its own shipping limit, so their SLA is ambiguous.
- **Edge cases:**
  - Timestamp against timestamp (pickup time vs limit time), unlike the calendar-day late delivery flag. The limit is the earliest `shipping_limit_at` among the seller's items in the order.
  - Null for 140 sellers (98 of them active) without a single-seller handover.
  - Orders with contradictory timestamps stay in (DQ-14). The 8 items whose limit is more than 90 days after purchase can only make a handover look on time (DQ-12).
  - Q3 flags a seller above 15% (`late_handover_threshold_pct`). Its quadrant averages (`avg_late_handover_rate_pct`) are unweighted means of seller rates.
- **What it goes with:** among delivered single-seller orders, 20.93% arrived late when the seller handed over late vs 5.44% when on time (95% intervals 20.08-21.80% and 5.29-5.59%); 9.1% of those orders were handed over late (Q3 `handover_vs_outcome`). This is an association: it does not separate the seller's delay from carrier or distance effects.
- **Used in:** Q3 `handover_vs_outcome`, `seller_quadrants` and `watchlist`; the app's quadrant scatter.

```sql
-- marketplace rate at order grain; seller_scorecard computes the same rule per seller
with

shipping_limits as (

    select order_id, min(shipping_limit_at) as shipping_limit_at
    from marts.fct_order_items
    group by order_id

)

select
    count(*) as handed_over_orders,
    1.0 * count(*) filter (
        where fct_orders.order_delivered_to_carrier_at > shipping_limits.shipping_limit_at
    ) / count(*) as late_handover_rate

from marts.fct_orders as fct_orders
inner join shipping_limits
    on fct_orders.order_id = shipping_limits.order_id
where fct_orders.is_net_order
    and fct_orders.distinct_seller_count = 1
    and fct_orders.order_delivered_to_carrier_at is not null;
```

### 8.4 Seller bad review rate

Share of the seller's reviewed net orders whose latest review is a bad review (1-2 stars).

**Value** median 13.0% among established sellers; 34 of them are above both 20% bad reviews and 15% late handover, with 5.2% of net GMV (Q3 `seller_quadrants`) · **Source** `marts.seller_scorecard.bad_review_rate`, denominator `reviewed_orders` · **MetricFlow** no; MetricFlow's `bad_review_rate` is the order-level metric (§6.1)

- **Includes:** net orders that contain the seller's items and have a review.
- **Edge cases:**
  - A multi-seller order's review counts for every seller in it.
  - The review rates the whole order, carrier and other sellers included: an outcome the seller influences, not one it controls.
  - Compare established sellers only (§8.1). Q3 flags a seller above 20% (`bad_review_threshold_pct`).
  - Seller rates weighted by `reviewed_orders` do not give the marketplace rate, because multi-seller orders count more than once; use §6.1 for the marketplace.
- **Used in:** Q3 `seller_quadrants` and `watchlist`; the app's quadrant scatter.

```sql
-- how seller_scorecard derives it; reproduces the column for all 3,053 active sellers
with

seller_orders as (

    select distinct seller_id, order_id
    from marts.fct_order_items
    where is_net_order

)

select
    seller_orders.seller_id,
    count(*) filter (where fct_orders.has_review) as reviewed_orders,
    1.0 * count(*) filter (where fct_orders.is_bad_review)
        / nullif(count(*) filter (where fct_orders.has_review), 0) as bad_review_rate

from seller_orders
inner join marts.fct_orders as fct_orders
    on seller_orders.order_id = fct_orders.order_id
group by seller_orders.seller_id;
```

### 8.5 Seller late delivery rate

Share of the seller's delivered net orders (with a delivery date) that arrived after the estimated date.

**Value** median 5.73% among established sellers · **Source** `marts.seller_scorecard.late_delivery_rate` · **MetricFlow** no

- **Edge cases:** The definition of §5.1, counted for every seller in a multi-seller order. It mixes the seller's handover with carrier transit; the late handover rate (§8.3) isolates the seller's own step.
- **Used in:** Q3 `watchlist`.

```sql
select seller_id, net_orders, delivered_orders, late_delivery_rate
from marts.seller_scorecard
where net_orders >= 50
order by late_delivery_rate desc;
```

## 9. Same name, different number

After the marts, most remaining disagreements are a different population or period, not an error. Each pair below is correct; the label says which one you have.

| Metric | Default | Also seen | Why they differ |
|---|---:|---:|---|
| Net orders | 98,207 | 97,910 | The Dashboard default covers complete months only (2017-01 to 2018-08). |
| Late delivery rate | 6.77% | 6.79% | Dashboard default, complete months. |
| Late delivery rate | 6.77% | 6.67% | Q1 counts reviewed deliveries in complete months (6,378 / 95,560). |
| Late delivery rate, AL | 21.41% | 21.46%; 20.87% | Full extract vs complete months (Dashboard state table) vs reviewed deliveries in complete months (Q1 `by_state`). |
| Bad review rate | 14.69% | 13.87% | All reviewed orders (MetricFlow) vs net orders (`customer_360`, `seller_scorecard`). |
| Average review score | 4.09 | 4.12 | All reviewed orders vs net orders. |
| Delivery days | 10 (median) | 12.50 (mean) | The Dashboard tile shows the median; the monthly line and `avg_delivery_days` columns show the mean. |
| Repeat rate | 2.17% | 3.04% | 2+ purchase days (official) vs 2+ orders, which counts split checkouts. |
| Repeat rate | 2.17% | 2.00% | Lifetime vs within 180 days for fully observed cohorts. |
| Customers | 94,990 | 96,096 | People with a net order vs every row of `dim_customers`. |
| Orders across sellers | 98,199 | 99,542 | Net orders with items vs `seller_scorecard.net_orders` summed (multi-seller orders count per seller). |
| Revenue | R$15,735,527.03 | R$16,008,872.12 | Net GMV vs payments in every status (Analyst B's number). |

## 10. Headline numbers and their source

Every headline metric number of the project (README, readout, app), with its value, its definition here, and the file and result set that produce it. Data-quality counts, test counts and the incremental-model proof are traced in [03 Data quality checks](03_data_quality_checks.md) and the [data quality report](data_quality_report.md). Repo SQL runs with `uv run python scripts/run_sql.py <file>`; a result set is a `-- result:` section of the file. "SQL in §x" means the query in that section of this document.

| Headline | Value | Defined in | Produced by (file → result set) |
|---|---|---|---|
| "Orders" after joining orders, items and payments (Analyst A) | 117,601 rows | the fan-out, not a metric ([ADR 0003](adr/0003-grain-fan-out-and-customer-identity.md)) | [`sql/metrics/01_three_analysts_on_raw.sql`](../sql/metrics/01_three_analysts_on_raw.sql) → `order_counts`, row A |
| Revenue from that join vs payments actually recorded | R$20,308,134.71 vs R$16,008,872.12 (+26.9%) | §4.4 | `sql/metrics/01_three_analysts_on_raw.sql` → `order_counts`, `revenue_reported_brl` of rows A and B |
| Placed orders | 99,441 | §3.1 | [`analyses/q0_order_count_reconciliation.sql`](../analyses/q0_order_count_reconciliation.sql) → `named_order_metrics`; [`sql/metrics/02_official_order_counts_by_month.sql`](../sql/metrics/02_official_order_counts_by_month.sql) → `totals` |
| Net orders, the official KPI | 98,207 | §3.2 | `analyses/q0_order_count_reconciliation.sql` → `named_order_metrics` and all five rows of `query_paths`; `sql/metrics/02_official_order_counts_by_month.sql` → `totals` |
| Delivered orders | 96,478 | §3.3 | `analyses/q0_order_count_reconciliation.sql` → `named_order_metrics`; `sql/metrics/02_official_order_counts_by_month.sql` → `totals` |
| Independent query paths that must return the same net order count | 6 | §3.2 | [`dbt/tests/singular/assert_net_order_count_consistent_across_query_paths.sql`](../dbt/tests/singular/assert_net_order_count_consistent_across_query_paths.sql) (returns rows only if the paths disagree; passes) |
| Open orders inside net orders | 1,729 | §3.4 | SQL in §3.4 |
| Canceled and unavailable orders | 1,234 (625 canceled, 609 unavailable), 1.24% of placed orders | §3.5 | SQL in §3.5 |
| Net GMV | R$15,735,527.03 | §4.1 | `analyses/q0_order_count_reconciliation.sql` → `query_paths`; `sql/metrics/02_official_order_counts_by_month.sql` → `totals`; `sql/metrics/01_three_analysts_on_raw.sql` → `order_counts`, row Official |
| Average order value | R$160.23 | §4.5 | SQL in §4.5 (MetricFlow `average_order_value_brl`) |
| Payments vs items + freight | +R$2,870.39 over 98,665 orders; 249 orders off by more than R$1 | §4.4 | [`sql/data_quality/07_payment_reconciliation.sql`](../sql/data_quality/07_payment_reconciliation.sql) → `summary` |
| Late delivery rate | 6.77% (6,534 / 96,470) | §5.1 | SQL in §5.1 (MetricFlow `late_delivery_rate`) |
| Late delivery rate among reviewed deliveries, complete months (Q1 baseline) | 6.67% (6,378 / 95,560) | §5.1, §9 | `analyses/q1_delivery_vs_reviews_by_state.sql` → `late_vs_on_time` (`reviewed_deliveries` of the late row over both rows) |
| Median delivery time | 10 days | §5.3 | SQL in §5.3 |
| Bad review rate, late vs on-time deliveries | 62.42% vs 9.25% (6.7x) | §6.1 | [`analyses/q1_delivery_vs_reviews_by_state.sql`](../analyses/q1_delivery_vs_reviews_by_state.sql) → `late_vs_on_time` |
| State correlation, late rate vs bad review rate | r = 0.937 across 21 states | §5.1, §6.1 | `analyses/q1_delivery_vs_reviews_by_state.sql` → `state_correlation` |
| States late most often (reviewed deliveries, complete months) | AL 20.87%, MA 17.21%, SE 15.11% | §5.1 | `analyses/q1_delivery_vs_reviews_by_state.sql` → `by_state` (ordered by `late_rate_pct`) |
| Repeat rate (official) | 2.17% (2,065 / 94,990) | §7.2 | [`analyses/q2_repeat_purchase.sql`](../analyses/q2_repeat_purchase.sql) → `definition_sensitivity`, row 3 |
| Repeat rate counted by orders / by checkouts | 3.04% / 2.78% | §7.2 | `analyses/q2_repeat_purchase.sql` → `definition_sensitivity`, rows 1 and 2 |
| Repeat rate counted on the per-order `customer_id` | 0.00% (vs 3.04% on `customer_unique_id`) | §7 | [`sql/metrics/03_customer_key_trap_on_raw.sql`](../sql/metrics/03_customer_key_trap_on_raw.sql) → `repeat_rate_by_key` |
| People behind the 99,441 customer ids | 96,096 | §7 | [`sql/data_quality/02_primary_keys.sql`](../sql/data_quality/02_primary_keys.sql) → `primary_keys` |
| Median time to second purchase | 74 days | §7.4 | `analyses/q2_repeat_purchase.sql` → `time_to_second_purchase` (`median_days_all_repeaters`) |
| Repeat within 180 days, fully observed cohorts | 2.00% (1,126 / 56,337) | §7.3 | `analyses/q2_repeat_purchase.sql` → `cohort_repeat`, rows with `is_fully_observed`, pooled |
| Net GMV held by the top 10% of sellers | 66.7% (306 of 3,053 active sellers) | §8.2 | [`analyses/q3_seller_performance.sql`](../analyses/q3_seller_performance.sql) → `gmv_concentration` |
| Late deliveries when the seller handed over late vs on time | 20.93% vs 5.44% | §8.3 | `analyses/q3_seller_performance.sql` → `handover_vs_outcome` |
| Late deliveries that followed an on-time handover (single-seller orders) | 72.2% (4,708 of 6,520) | §8.3 | `analyses/q3_seller_performance.sql` → `handover_vs_outcome` (`late_deliveries` of the on-time row over both rows) |
| Established sellers (50+ net orders) | 428 | §8.1 | `analyses/q3_seller_performance.sql` → `seller_quadrants` (sum of `sellers`) |
| Established sellers above both thresholds | 34, holding 5.2% of net GMV | §8.3, §8.4 | `analyses/q3_seller_performance.sql` → `seller_quadrants`, row 1 |
| Dashboard defaults, 2017-01 to 2018-08 | 97,910 net orders; R$15,683,706.74 net GMV; R$160.18 AOV; 6.79% late; 10 days median delivery; 4.09 average review | §3.2, §4.1, §4.5, §5.1, §5.3, §6.2 | [`src/olist_analytics/analysis.py`](../src/olist_analytics/analysis.py) → `dashboard_kpis()` |
