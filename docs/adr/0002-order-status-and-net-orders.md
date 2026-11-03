# ADR 0002: Order status and the official order KPI ("net orders")

**Status:** Accepted, 2026-11-03

## Context

"Orders" meant three things to three analysts, and each was defensible. The source `order_status` is a snapshot at extract time with eight values: delivered 96,478, shipped 1,107, canceled 625, unavailable 609, invoiced 314, processing 301, created 5, approved 2. An order KPI is a choice of which statuses count. It has to be made once, signed off by Finance, implemented in one place, and reversible without rewriting reports.

## Decision

Three named metrics, all from `fct_orders`, dated by `order_purchase_date` (the local purchase date, America/Sao_Paulo assumed; `order_purchased_at_utc` exists for UTC joins):

| Metric | Definition | Value |
|---|---|---:|
| placed orders | every order, any status: `count(*)` | 99,441 |
| **net orders** (official KPI) | placed minus `canceled` and `unavailable`: `count(*) filter (where is_net_order)` | **98,207** |
| delivered orders | status `delivered`: `count(*) filter (where is_delivered)` | 96,478 |

- **The definition is data.** `dbt/seeds/order_status_mapping.csv` sets, per status, the reporting group, `is_net_order` and `is_terminal_status`. `int_orders_classified` joins it, and the flag flows to both facts, the customer and seller marts, and the semantic-layer metrics.
- **Open orders count as net.** The 1,729 orders in a non-terminal status (shipped 1,107, invoiced 314, processing 301, created 5, approved 2) are 1.76% of net orders and R$315,753.28 (2.01%) of net GMV. They have not been canceled, and the source records no other outcome. Excluding them would shrink every recent month until its deliveries land, then restate it.
- **Net GMV** is items plus freight of net orders: R$15,735,527.03. Payments are a separate measure (ADR 0004).
- **Status wins over timestamps.** The 8 net orders without items (5 created, 2 invoiced, 1 shipped) stay in with GMV 0, including in the AOV denominator (DQ-08); the 6 canceled orders with a delivery timestamp stay out (DQ-14).
- **Changing the KPI means changing this one seed file**, in a pull request reviewed by the Analytics Lead with Finance.

## Alternatives considered

- **Delivered orders as the headline (96,478).** Rejected: it measures fulfilment. It under-counts any month with open orders (2018-08: 6,421 net, 6,351 delivered), restates recent months with every extract, and relies on statuses being updated after shipment. Kept as a named metric for ops and logistics.
- **Net orders excluding open orders.** Same as the above: the only terminal statuses are delivered, canceled and unavailable, so "net and terminal" is exactly "delivered".
- **Approved orders (`order_approved_at` not null, 99,281).** Rejected: the 160 orders without the timestamp are 141 canceled, 14 delivered and 5 created (DQ-14), so this metric drops 14 delivered orders but keeps 484 canceled and all 609 unavailable ones. Approval is a payment event, not a business outcome.
- **Placed orders (99,441).** Rejected: 1,234 orders (1.24%) never became sales; the canceled ones alone carry R$105,885.72 of GMV. Kept as a named metric for demand and funnel questions.
- **Hard-coding `where order_status not in ('canceled', 'unavailable')`.** Rejected: the list gets copied into every model, notebook and dashboard, which is how the drift started. A seed is reviewable as a diff and testable.

## Consequences

Positive:

- One number by any path: `fct_orders`, the star join, the monthly series, the customer tables and the item fact all return 98,207, and a test fails if they disagree. `is_net_order` is on both facts, so nobody filters statuses by hand.
- Reversible by data: if Finance decides to book on delivery, setting `is_net_order = false` on the five open statuses makes net orders equal delivered orders. Open orders are re-processed on every run, so no full refresh is needed.
- An unknown status cannot slip through: `accepted_values` on `stg_olist__orders.order_status` and `not_null` on `int_orders_classified.is_net_order` fail the build until the status is added to the seed and the accepted list.

Negative and trade-offs:

- **Net is not fulfilled, and most open orders look stale.** 1,623 of the 1,729 were purchased more than 90 days before the last purchase in the extract (2018-10-17), and the median open `shipped` order 283 days before it; only 71 date from 2018-08 onwards. This suggests the source stops updating some statuses. Net orders are an upper bound on fulfilled orders, at most 1,729 (1.76%) too high, and delivered orders a lower bound; both are published.
- **A seed change moves a lot at once:** `frequency_orders`, `monetary_gmv_brl`, `is_repeat_customer`, every scorecard rate, and the baselines that filter on `is_net_order` (e.g. `assert_net_orders_have_items`, `warn_if: ">8"`). Reclassifying a terminal status also needs `dbt build --full-refresh -s fct_order_items`, because the incremental model only re-processes open orders and its lookback window (ADR 0005); until then `item_net_gmv_reconciles_with_order_net_gmv` fails.
- `is_net_order` is the status at extract time. "Net orders as reported last month" needs the SCD2 snapshot `snp_olist__orders`, whose history starts at its first run.

## How this is verified

- Seed tests (`dbt/seeds/_seeds.yml`): `unique` and `not_null` on `order_status`, `not_null` and `accepted_values` on `order_status_group`, `not_null` on `is_net_order`. Downstream: `accepted_values` on `stg_olist__orders.order_status`, `not_null` on `order_status_group` and `is_net_order` in `int_orders_classified`.
- Unit test `test_late_delivery_and_status_logic` (`_int__models.yml`): a canceled order with a delivery timestamp is not net; a shipped order is net with null delivery metrics; delivery on the estimated day is on time, a day later is late; contradictory timestamps are flagged.
- `assert_net_order_count_consistent_across_query_paths`, the complaint written as a test. Six paths must agree: (1) `fct_orders where is_net_order`; (2) the star join `fct_orders` x `dim_customers` x `dim_date`; (3) monthly counts through `dim_date`, summed; (4) `sum(dim_customers.frequency_orders)`; (5) distinct net orders in `fct_order_items` plus net orders without items; (6) `stg_olist__orders` joined to the seed, bypassing every intermediate and mart model. On disagreement it returns every path with its count.
- `assert_complete_months_have_expected_volume`: every complete month has at least 500 net orders (50 on the CI fixture).
- Semantic layer: `placed_orders`, `net_orders` and `delivered_orders` in `_semantic_models.yml`; CI runs `mf query --metrics net_orders,net_gmv_brl`.
- Query side: `analyses/q0_order_count_reconciliation.sql` returns 98,207 and R$15,735,527.03 on five analyst paths; `sql/metrics/01_three_analysts_on_raw.sql` reproduces 117,601 / 99,441 / 96,478 on raw.

## References

- [`order_status_mapping.csv`](../../dbt/seeds/order_status_mapping.csv), [`_seeds.yml`](../../dbt/seeds/_seeds.yml), [`int_orders_classified.sql`](../../dbt/models/intermediate/int_orders_classified.sql), [`_int__models.yml`](../../dbt/models/intermediate/_int__models.yml), [`fct_orders.sql`](../../dbt/models/marts/core/fct_orders.sql), [`fct_order_items.sql`](../../dbt/models/marts/core/fct_order_items.sql), [`_semantic_models.yml`](../../dbt/models/semantic/_semantic_models.yml), [`snp_olist__orders.yml`](../../dbt/snapshots/snp_olist__orders.yml)
- [`assert_net_order_count_consistent_across_query_paths.sql`](../../dbt/tests/singular/assert_net_order_count_consistent_across_query_paths.sql), [`assert_complete_months_have_expected_volume.sql`](../../dbt/tests/singular/assert_complete_months_have_expected_volume.sql), [`assert_net_orders_have_items.sql`](../../dbt/tests/singular/assert_net_orders_have_items.sql)
- [`analyses/q0_order_count_reconciliation.sql`](../../analyses/q0_order_count_reconciliation.sql), [`sql/metrics/01_three_analysts_on_raw.sql`](../../sql/metrics/01_three_analysts_on_raw.sql), [`sql/metrics/02_official_order_counts_by_month.sql`](../../sql/metrics/02_official_order_counts_by_month.sql), [`issue_register.yml`](../../sql/data_quality/issue_register.yml) (DQ-08, DQ-14, DQ-19)
- [`docs/01_request_and_scope.md`](../01_request_and_scope.md), [`docs/02_metric_definitions.md`](../02_metric_definitions.md), [`docs/assumptions.md`](../assumptions.md); [ADR 0004](0004-payments-cancellations-and-refunds.md) (payments and cancellations), [ADR 0005](0005-incremental-fct-order-items.md) (incremental `fct_order_items`)
