# ADR 0003: Grain, fan-out and customer identity

**Status:** Accepted, 2026-11-03

## Context

Analyst A's 117,601 counted the rows of `orders` joined to `order_items` and `order_payments`: an order with 3 items and 2 payments becomes 6 rows, and the same join reported R$20,308,134.71 of revenue against R$16,008,872.12 actually paid. The source has more traps of this kind:

- `customer_id` is issued per order: 99,441 ids for 96,096 people; 2,997 people have 2 or more ids, one has 17. Counted on `customer_id`, the repeat rate is 0% (DQ-01).
- `review_id` is not unique: 789 ids sit on 2-3 orders each, and 547 orders have 2-3 answers, 202 of them with different scores (DQ-02, DQ-03).
- `order_items` has no quantity column; one row is one unit (DQ-04).
- One checkout can become several orders in the same second: 290 groups, 582 orders (DQ-05).
- 1,278 orders (1.29%) contain items from more than one seller.
- The customer record is per order, so a person's address can change between orders; 252 people used more than one.

## Decision

**1. Every mart declares its grain (`meta.grain`) and a test proves it.**

| Mart | Grain | Rows | Grain test |
|---|---|---:|---|
| `fct_orders` | one row per order, any status | 99,441 | `fct_orders_has_one_row_per_source_order` |
| `fct_order_items` | one row per unit sold (order line) | 112,650 | `fct_order_items_has_one_row_per_source_item`, `unique_combination_of_columns (order_id, order_item_id)` |
| `dim_customers` | one row per person (`customer_unique_id`) | 96,096 | `dim_customers_has_one_row_per_person` (vs distinct `customer_unique_id` in staging) |
| `dim_products` | one row per product | 32,951 | `row_count_matches` vs `stg_olist__products` |
| `dim_sellers` | one row per seller | 3,095 | `row_count_matches` vs `stg_olist__sellers` |
| `dim_date` | one row per day, 2016-01-01 to 2018-12-31 | 1,096 | `is_continuous_date_spine` |
| `customer_360` | one row per person | 96,096 | `customer_360_has_one_row_per_person` (vs `dim_customers`) |
| `seller_scorecard` | one row per seller | 3,095 | `seller_scorecard_has_one_row_per_seller` (vs `dim_sellers`) |

**2. Aggregate children to the order grain before joining.** Items, payments and reviews are each reduced to one row per order (`int_order_items_aggregated_to_orders`, `int_payments_pivoted_to_orders`, `int_reviews_deduplicated_to_orders`) and left-joined in `int_orders_joined`, which is tested to keep one row per source order. Missing children become `has_items`, `has_payment` or `has_review` = false with amounts 0 (775, 1 and 768 orders) instead of vanishing in an inner join.

**3. A customer is a person: `customer_unique_id`.** It keys `dim_customers` and `customer_360` and is the foreign key on both facts. The per-order `customer_id` is not exposed in any mart; it stays upstream (staging, intermediate) for tracing records to the source.

**4. Two addresses, two meanings.** `fct_orders.delivery_*` is the address on the order's customer record, which Olist documents as the delivery location; logistics questions use it. `dim_customers.customer_*` is the address of the person's latest net order (latest order if they have none), so a canceled order's address never wins over a net order's; "where do our customers live" uses it. They differ for 43 orders at state level (40 delivered, 2 unavailable, 1 canceled; 39 people) and 269 at zip-prefix level.

**5. One review per order.** The most recently answered survey is kept (ties: survey date, then `review_id`), and `review_count` records how many answers there were. Review metrics are shares of orders, never counts of `review_id`.

**6. Split checkouts stay separate orders; repeat is measured in days.** Finance reconciles at order grain, and the source has no checkout id. A repeat customer has net orders on 2 or more distinct purchase days: 2,065 of 94,990 people with a net order (2.17%), against 2,888 (3.04%) counting orders and 2,638 (2.78%) counting distinct timestamps.

**7. Multi-seller orders count for every seller.** `seller_scorecard` builds order outcomes at seller x order grain, so a late delivery or bad review on a 2-seller order counts once for each seller (1,277 net orders, 1.3%). GMV stays item-level and sums exactly to net GMV. `late_handover_rate` uses single-seller orders only: the source has one carrier timestamp per order, and sellers in one order can have different shipping limits.

## Alternatives considered

- **Join at item grain and `count(distinct order_id)` everywhere.** Rejected: the distinct is easy to forget (Analyst A) and cannot de-duplicate sums. Aggregating first makes the safe join the only join.
- **Expose `customer_id` for traceability.** Rejected: it would be joined and counted by mistake, the DQ-01 trap.
- **Person address = first order, or most frequent.** Rejected: the first goes stale, and the most frequent has no winner for 226 of the 252 people with more than one address (two orders, two addresses). The latest net order is deterministic and current.
- **Keep every review (`fct_reviews`), or the first, worst or average score.** Rejected for now: the questions are order-level ("share of orders with a bad review"), and the latest answer is the customer's final opinion. A review fact can be added later without touching `fct_orders`.
- **Merge same-second orders into one checkout.** Rejected: it changes the grain Finance reconciles, with no checkout id to merge on. The repeat definition handles the effect instead.
- **Attribute a multi-seller order to its largest seller only.** Rejected: the source cannot say which seller caused a late delivery or a bad review, and attributing to all is transparent. The cost is a 1.4% over-count of seller-level order totals.

## Consequences

Positive:

- No documented join can fan out: fact to dimension and item to order are many-to-one, and every row count is pinned by a test, so a regression fails the build instead of a dashboard.
- GMV reconciles exactly (tolerance 0) across `fct_order_items`, `fct_orders`, `dim_customers` and `seller_scorecard`; `payment_total_brl` reconciles with staging to the cent.
- The grain tests also catch incremental drift: in `scripts/check_incremental.py` scenario B, 26 late rows make `fct_order_items_has_one_row_per_source_item` fail, and a full refresh repairs it.

Negative and trade-offs:

- `sum(seller_scorecard.net_orders)` is 99,542, not the 98,199 net orders with items, because a multi-seller order counts once per seller. Seller counts must never be summed into a marketplace total; `fct_orders` is the total.
- Only the latest review is kept: for the 202 orders whose answers disagree, the earlier score is not in the marts.
- Order and person geography differ for 43 orders; a report has to say which one it uses.
- Distinct days cannot tell a genuine same-day second purchase from a split checkout, so the three repeat definitions are published side by side.
- `dim_customers` includes 1,106 people whose only orders were canceled or unavailable (`has_net_order = false`); customer-level rates must filter on it.

## How this is verified

- Grain and fan-out (18 tests): `row_count_matches` on 10 models (`int_orders_classified`, `int_orders_joined`, `int_customers_aggregated_to_persons` and every mart except `dim_date`); `is_continuous_date_spine` on `dim_date`; `dbt_utils.unique_combination_of_columns` on the item, payment and review keys in source and staging, and on `fct_order_items`. `unique` and `not_null` on every primary key come on top.
- Reconciliation (6 tests): `item_gmv_reconciles_with_order_gmv` and `item_net_gmv_reconciles_with_order_net_gmv` (`fct_order_items` vs `fct_orders`), `customer_gmv_reconciles_with_net_order_gmv`, `seller_gmv_reconciles_with_net_order_gmv`, `fct_orders_payments_reconcile_with_staging` (`payment_total_brl` vs `stg_olist__order_payments`) and `assert_net_order_count_consistent_across_query_paths`.
- Referential integrity (19 `relationships` tests): every foreign key on both facts, plus `seller_scorecard`, staging keys and state codes. With unique dimension keys, a star join can neither drop nor duplicate rows.
- Reviews: unit test `test_review_dedup_keeps_latest_answer`; baselines `known_issue__review_id_shared_across_orders` (789) and `known_issue__orders_with_multiple_reviews` (547) warn if the source gets worse. The CI fixture (`ci/make_fixture.py`) plants both issues, and `ci/check_known_issues_detected.py` proves the tests detect them.
- Query side: `sql/metrics/03_customer_key_trap_on_raw.sql` (0% vs 3.04% repeat rate) and the `definition_sensitivity` result of `analyses/q2_repeat_purchase.sql` (3.04%, 2.78%, 2.17%).

## References

- [`int_orders_joined.sql`](../../dbt/models/intermediate/int_orders_joined.sql), [`int_order_items_aggregated_to_orders.sql`](../../dbt/models/intermediate/int_order_items_aggregated_to_orders.sql), [`int_payments_pivoted_to_orders.sql`](../../dbt/models/intermediate/int_payments_pivoted_to_orders.sql), [`int_reviews_deduplicated_to_orders.sql`](../../dbt/models/intermediate/int_reviews_deduplicated_to_orders.sql), [`int_customers_aggregated_to_persons.sql`](../../dbt/models/intermediate/int_customers_aggregated_to_persons.sql)
- [`_core__models.yml`](../../dbt/models/marts/core/_core__models.yml), [`_business__models.yml`](../../dbt/models/marts/business/_business__models.yml), [`dim_customers.sql`](../../dbt/models/marts/core/dim_customers.sql), [`seller_scorecard.sql`](../../dbt/models/marts/business/seller_scorecard.sql), [`test_row_count_matches.sql`](../../dbt/tests/generic/test_row_count_matches.sql), [`test_sum_matches.sql`](../../dbt/tests/generic/test_sum_matches.sql)
- [`scripts/check_incremental.py`](../../scripts/check_incremental.py), [`ci/make_fixture.py`](../../ci/make_fixture.py), [`ci/check_known_issues_detected.py`](../../ci/check_known_issues_detected.py)
- [`sql/metrics/03_customer_key_trap_on_raw.sql`](../../sql/metrics/03_customer_key_trap_on_raw.sql), [`analyses/q2_repeat_purchase.sql`](../../analyses/q2_repeat_purchase.sql), [`analyses/q3_seller_performance.sql`](../../analyses/q3_seller_performance.sql), [`issue_register.yml`](../../sql/data_quality/issue_register.yml) (DQ-01 to DQ-05)
- [`docs/data_quality_report.md`](../data_quality_report.md), [`docs/analyst_guide.md`](../analyst_guide.md); [ADR 0001](0001-layered-architecture.md) (layers), [ADR 0002](0002-order-status-and-net-orders.md) (net orders), [ADR 0005](0005-incremental-fct-order-items.md) (incremental `fct_order_items`)
