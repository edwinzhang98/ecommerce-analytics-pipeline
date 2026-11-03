# Q0. Do the three analysts now get the same order count?

**Answer: yes.** Five query paths through the marts return the same 98,207 net orders and R$15,735,527.03 net GMV. The paths go through the order fact, the item fact, the calendar, the customer dimension and the CRM table. The other two numbers that analysts used to call "orders" still exist, but as separately named metrics: 99,441 placed orders and 96,478 delivered orders.

SQL: [`q0_order_count_reconciliation.sql`](q0_order_count_reconciliation.sql). Numbers come from the build of 2026-11-03.

## Question

The original request: three analysts got three different order counts, and the business stopped trusting the numbers ([docs/01_request_and_scope.md](../docs/01_request_and_scope.md)). This file is the acceptance test for the marts. Analysts with different habits query the marts their own way: finance at item level, ops by month, marketing by customer. Do they get the same number?

## Decision it supports

| Decision | Owner |
|---|---|
| Adopt net orders as the single headline order KPI, with placed and delivered orders reported under their own names | Analytics Lead, with Finance sign-off |
| Retire raw-table access for analysts after one reporting cycle on the marts | Analytics Lead |

## Data and population

- **Tables.** `fct_orders` has one row per order in any status, and `fct_order_items` one row per item. The calendar is `dim_date`. `dim_customers` and `customer_360` have one row per person (`customer_unique_id`).
- **Population.** All 99,441 orders in the extract, purchased 2016-09-04 to 2018-10-17. No date filter, no parameters.
- **Net order.** `fct_orders.is_net_order` is true for every status except canceled and unavailable. The rule lives in the seed [`order_status_mapping.csv`](../dbt/seeds/order_status_mapping.csv), not in SQL ([ADR 0002](../docs/adr/0002-order-status-and-net-orders.md)).
- **Net GMV.** Items + freight (`order_gmv_brl`) of net orders. Payments are kept separately ([ADR 0004](../docs/adr/0004-payments-cancellations-and-refunds.md)).
- **Date basis for the monthly path.** The local purchase date, `order_purchase_date`.

## Method

**Before.** On the raw tables ([`sql/metrics/01_three_analysts_on_raw.sql`](../sql/metrics/01_three_analysts_on_raw.sql)), the three habits produce three counts, for two reasons:

- **Grain.** Joining orders to items and payments multiplies the rows.
- **Definition drift.** "Orders" meant every order to one analyst and delivered orders to another.

**After.** Each path below is a query an analyst could plausibly write against the marts. The paths use different tables and join patterns, so a model that dropped, duplicated or fanned out orders would make at least one of them disagree.

| # | Habit | Query | What agreement shows |
|---|---|---|---|
| 1 | Finance | `fct_orders where is_net_order`: count, and sum of `order_gmv_brl` | The documented way: one table, no join |
| 2 | Finance, item level | `fct_order_items` joined many-to-one to `fct_orders`; `count(distinct order_id)` plus the 8 net orders that have no items; GMV = sum of `item_total_brl` | The item grain does not inflate orders or money, and item amounts add up to order GMV |
| 3 | Ops | `fct_orders` joined to `dim_date`, counted by month, months summed | Every purchase date is in the calendar, and the monthly figures add up to the total |
| 4 | Marketing | Sum of `dim_customers.frequency_orders` and `monetary_gmv_brl` over people | The roll-up to people neither drops nor double-counts orders |
| 5 | CRM | The same sums over `customer_360` | The wide CRM table carries the same numbers |

Every path must return the same net orders and the same net GMV. The second result set lists the three named order metrics. They are allowed to differ, because each has its own name.

The count check also runs on every `dbt build`, as a singular test with six paths ([`assert_net_order_count_consistent_across_query_paths.sql`](../dbt/tests/singular/assert_net_order_count_consistent_across_query_paths.sql)). It shares four paths with this file (the order fact, the item fact, the monthly sum and `dim_customers`) and adds two:

- a star join of `fct_orders`, `dim_customers` and `dim_date`;
- a count straight from staging and the status seed, which bypasses every intermediate and mart model.

If the paths disagree, the test returns each one with its count and the build fails, in CI as well as locally. The test compares counts only. Net GMV is reconciled in the same build by `sum_matches` tests with zero tolerance, which compare `fct_order_items`, `dim_customers` and `seller_scorecard` with `fct_orders` (`item_net_gmv_reconciles_with_order_net_gmv`, `customer_gmv_reconciles_with_net_order_gmv`, `seller_gmv_reconciles_with_net_order_gmv`).

## Results

**Every path gives the same answer**

| # | Habit | Net orders | Net GMV (BRL) |
|---|---|---:|---:|
| 1 | Finance | 98,207 | 15,735,527.03 |
| 2 | Finance, item level | 98,207 | 15,735,527.03 |
| 3 | Ops | 98,207 | 15,735,527.03 |
| 4 | Marketing | 98,207 | 15,735,527.03 |
| 5 | CRM | 98,207 | 15,735,527.03 |

**The three named order metrics**

| Metric | Definition | Orders |
|---|---|---:|
| Placed orders | Every order, any status | 99,441 |
| Net orders (official KPI) | Placed orders minus canceled (625) and unavailable (609) | 98,207 |
| Delivered orders | Status delivered | 96,478 |

Net orders are the 96,478 delivered orders plus 1,729 open orders: 1,107 shipped, 314 invoiced, 301 processing, 5 created and 2 approved.

**Before and after**

| Analyst | Query on raw (before) | Reported as "orders" | On the marts (now) |
|---|---|---:|---|
| A, finance | Join orders → items → payments, count rows | 117,601 (revenue R$20,308,134.71) | 98,207 net orders, R$15,735,527.03 net GMV |
| B, ops | Count every order | 99,441 | 99,441 placed orders |
| C, marketing | Count delivered orders | 96,478 | 96,478 delivered orders |

## Conclusion

The order-count disagreement is resolved: every documented query path returns 98,207 net orders. The fix had two parts:

- **A modelling fix.** `fct_orders` has one row per order, and joins to it are many-to-one only.
- **A naming fix.** Three metrics, each with its own name, defined once: the status rule in the seed, the metrics in the semantic layer.

The grain is enforced by tests (`fct_orders_has_one_row_per_source_order`, `unique` on `order_id`, and the reconciliation tests above), not by convention.

This shows the marts agree with each other. It does not show that the source is right, or that net orders is the definition Finance wants. That is the sign-off below. Four points affect the number and belong in that conversation:

- **Open orders.** 1,729 net orders were still open when the extract was taken. 1,584 of them were purchased before July 2018, more than two months before the extract ends, so most look stalled rather than in transit. Whether stalled orders should count as net orders is the main open question for Finance.
- **Orders without items.** 8 net orders have no items. They count, with a GMV of 0 (DQ-08).
- **Sparse months.** The full extract includes months with almost no orders (DQ-19). For monthly reporting, use complete months only: 2017-01 to 2018-08 gives 97,910 net orders and R$15,683,706.74 net GMV.
- **GMV is not cash.** On orders with both items and payments, payments exceed items + freight by a net R$2,870.39. The gap is mostly card installment interest (DQ-16).

The DQ IDs refer to the issue register ([`sql/data_quality/issue_register.yml`](../sql/data_quality/issue_register.yml)) and the [data quality report](../docs/data_quality_report.md).

## Recommendations

**R1. Sign off net orders as the headline order KPI.**

- **Who:** Analytics Lead and Finance.
- **What:** Use net orders (`fct_orders.is_net_order`; semantic-layer metric `net_orders`) as the order count in the monthly business review. Publish placed and delivered orders only under those names.
- **Expected impact:** One order number in every report. A model change that breaks the agreement fails the build instead of reaching a dashboard.
- **How to measure:** The next monthly review quotes the three metric names. The reconciliation test stays green in CI. Nobody escalates "which number is right" in the next cycle.
- **Risk:** Finance may book revenue on delivery, or want stalled orders excluded.
  - Counting only delivered orders means setting `is_net_order = false` for the five open statuses in the status seed (ADR 0002). No report query changes.
  - Excluding stalled orders would need an age rule on top of the status mapping, released as a new version of the definition.

**R2. Move analysts to marts only after one reporting cycle.**

- **Who:** Analytics Lead, with the three analysts.
- **What:** Build every recurring report from the marts for one monthly cycle, then remove analyst access to `raw`.
- **Expected impact:** No new numbers built on raw. Questions the marts cannot answer become backlog items instead of side queries.
- **How to measure:** The number of recurring reports that still read `raw` (target: 0), and the backlog items raised during the cycle.
- **Risk:** Analysts lose their fallback for questions the marts do not cover yet. Clear those backlog items before removing access.

## Next step to validate

Replay one month. Each analyst rebuilds their published 2018-08 figures from the marts and reconciles them line by line. For 2018-08 the marts give:

| Metric | 2018-08 |
|---|---:|
| Placed orders | 6,512 |
| Net orders | 6,421 (70 still open) |
| Delivered orders | 6,351 |
| Net GMV | R$996,973.51 |

A line that does not reconcile is either a definition difference, which gets a name, or a defect, which gets a fix and a test. In the same exercise, Finance reconciles the month's net GMV against its own ledger.

## How to reproduce

```bash
uv run python scripts/run_sql.py analyses/q0_order_count_reconciliation.sql
uv run python scripts/run_sql.py sql/metrics/01_three_analysts_on_raw.sql    # the "before", on raw
cd dbt && uv run dbt test --profiles-dir . --select assert_net_order_count_consistent_across_query_paths
make metrics    # placed, net and delivered orders through the semantic layer (MetricFlow)
```

The app's Overview page and the order-count notebook ([`notebooks/02_order_count_reconciliation.ipynb`](../notebooks/02_order_count_reconciliation.ipynb)) run the same file.

Some numbers in the conclusion and the next step are not in the file's output. They come from these queries:

```sql
-- open orders, open orders purchased before 2018-07, net orders without items: 1,729 / 1,584 / 8
select
    count(*) filter (where is_net_order and not is_terminal_status) as open_orders,
    count(*) filter (where is_net_order and not is_terminal_status
                     and order_purchase_date < date '2018-07-01') as open_before_2018_07,
    count(*) filter (where is_net_order and not has_items) as net_orders_without_items
from marts.fct_orders;

-- complete months 2017-01 to 2018-08: 97,910 net orders, R$15,683,706.74
select count(*) as net_orders, sum(fct_orders.order_gmv_brl) as net_gmv_brl
from marts.fct_orders as fct_orders
inner join marts.dim_date as dim_date on fct_orders.order_purchase_date = dim_date.date_day
where fct_orders.is_net_order and dim_date.is_complete_data_month;

-- the 2018-08 replay figures
select
    count(*) as placed_orders,
    count(*) filter (where is_net_order) as net_orders,
    count(*) filter (where is_net_order and not is_terminal_status) as open_orders,
    count(*) filter (where is_delivered) as delivered_orders,
    sum(order_gmv_brl) filter (where is_net_order) as net_gmv_brl
from marts.fct_orders
where order_purchase_date between date '2018-08-01' and date '2018-08-31';
```

The R$2,870.39 payment gap comes from [`sql/data_quality/07_payment_reconciliation.sql`](../sql/data_quality/07_payment_reconciliation.sql).
