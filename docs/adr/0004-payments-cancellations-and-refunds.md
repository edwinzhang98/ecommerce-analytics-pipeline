# ADR 0004: Payments, cancellations and refunds

**Status:** Accepted, 2026-11-03

## Context

The marts need one revenue measure, and the source offers two that do not agree: **items + freight** (`order_items.price + freight_value`, one row per unit) and **payments** (`order_payments.payment_value`, 103,886 rows; 2,961 orders have more than one, for example a voucher plus a card). Payments are rolled up to one row per order before any join ([ADR 0003](./0003-grain-fan-out-and-customer-identity.md)).

Reconciled on raw ([`07_payment_reconciliation.sql`](../../sql/data_quality/07_payment_reconciliation.sql)) over the 98,665 orders that have both:

| Check | Orders |
|---|---:|
| Payments within 1 cent of items + freight | 98,362 |
| Off by more than 1 cent | 303 |
| Off by more than R$1 | 249 |
| Overpaid by more than R$1 (of the 249) | 232 |
| Overpaid by more than R$1 and paid by credit card in installments (of the 232) | 229 |
| Underpaid by more than R$1 (of the 249) | 17 |

Net, payments exceed items + freight by R$2,870.39 on R$15,843,409.78 (0.02%), though 91 orders are overpaid by more than R$10. Since 229 of the 232 overpaid orders are card payments in installments, we read the gap as installment interest; the source has no interest field to confirm it, and installments alone do not imply a gap (51,170 of the 99,440 paid orders, 51.5%, use them).

Three more facts:

1. **No refund, chargeback or settlement data.** The source records payment amounts by method; whether money was later returned is not recorded.
2. **Canceled and unavailable orders keep their payment rows.** All 625 canceled orders (R$143,255.60) and all 609 unavailable orders (R$126,479.51) have payments; only 461 and 6 of them have items.
3. **Edge rows.** 9 payment rows have value 0 (3 of type `not_defined`, 6 vouchers) and 2 credit-card rows have 0 installments (DQ-11). One delivered order from 2016-09-15 (3 items, R$143.46) has no payment record (DQ-08).

## Decision

1. **GMV (items + freight) is the revenue measure.** `fct_orders.order_gmv_brl = items_subtotal_brl + freight_total_brl` and `fct_order_items.item_total_brl = item_price_brl + freight_value_brl`; item and order totals reconcile to the cent.
2. **Net GMV is the GMV of net orders** (`is_net_order`, [ADR 0002](./0002-order-status-and-net-orders.md)): R$15,735,527.03. The R$108,026.21 of item GMV on canceled and unavailable orders stays in the tables, with `is_net_order = false`, and out of net GMV. The MetricFlow metrics `net_gmv_brl` and `average_order_value_brl` use this definition.
3. **Payments are kept separately and unadjusted** in `fct_orders`. `payment_total_brl` is the sum of the order's payment rows as recorded (0 when there are none); `payment_gmv_difference_brl = payment_total_brl - order_gmv_brl`; `is_payment_mismatch` is true when the order has items and payments and the absolute difference exceeds `payment_mismatch_tolerance_brl` (var, 1.00), which absorbs small gaps (54 orders are off by more than 1 cent but at most R$1). Payment-mix columns (`primary_payment_type`, `max_payment_installments`, one amount column per method, `has_voucher_payment`) answer payment-method questions.
4. **No refund modelling.** A cancellation is not treated as a refund, and payments on canceled orders are not netted against anything.
5. **Edge rows stay as recorded**, under baseline tests. The order without payment stays a net order (`has_payment = false`, flag `no_payment`).

## Alternatives considered

- **Payments as revenue.** Over every status this is Analyst B's R$16,008,872.12 ([`01_three_analysts_on_raw.sql`](../../sql/metrics/01_three_analysts_on_raw.sql)); over net orders it is R$15,739,137.01, 0.02% above net GMV. Rejected even so: it includes what we read as installment interest (a financing charge, not merchandise value), it is missing for one delivered order, and it cannot be split by product, seller or category without an allocation rule.
- **Revenue net of interest.** Rejected: the source has no interest or fee field. The only estimate of interest is `payment_gmv_difference_brl`, so payments minus interest is GMV by construction, and the 17 underpaid orders would show negative interest.
- **Allocate payments to items pro rata.** Rejected: it creates a second item-level amount that differs from `item_total_brl` on every mismatched order, plus rounding residuals, so every product and seller total would need its own reconciliation. Seller payouts and commissions are not in the source; a payout question would get a new intermediate model, not a change to GMV.
- **Treat a cancellation as a refund.** Rejected: we do not know whether or when money was returned, and 6 canceled orders even carry a delivery timestamp (DQ-14). Negative revenue would present an inference as a fact; excluding canceled orders from net GMV does not.

## Consequences

Positive:

- One revenue measure, additive across grains: `item_total_brl` summed by product, category or seller adds up to the order-level total, and every documented query path returns the same net GMV ([`q0_order_count_reconciliation.sql`](../../analyses/q0_order_count_reconciliation.sql): R$15,735,527.03 through `fct_orders`, `fct_order_items`, `dim_date`, `dim_customers` and `customer_360`).
- The payment gap is visible per order (`payment_gmv_difference_brl`) instead of being hidden in a total.

Negative and trade-offs:

- **Net GMV is bookings, not cash and not recognised revenue**: gross of refunds we cannot see, and without any installment interest. `payment_total_brl` is the closest proxy for cash, but it holds recorded payments, not settlements, and includes payments on canceled and unavailable orders.
- 249 orders (247 of them net orders) carry `is_payment_mismatch = true`. They stay in every metric; flags never remove rows.
- `not_defined` stays an accepted value of `primary_payment_type` (3 canceled orders); payment-mix analysis has to exclude it (DQ-11).
- The baseline of 249 is written into the test, so changing the tolerance var means re-deriving it.
- **What would change this decision:** refund or chargeback events (order, amount, timestamp, reason), capture or settlement status, or an interest and fee breakdown per payment. With those, refunds become their own fact table, net revenue becomes net GMV minus refunds, and this ADR is superseded.

## How this is verified

| Test | What it checks | Threshold |
|---|---|---|
| [`assert_payments_reconcile_with_order_gmv`](../../dbt/tests/singular/assert_payments_reconcile_with_order_gmv.sql) (DQ-16) | Orders with items and payments that differ by more than the tolerance | passes at 249, warns above, errors above 1,000; failing rows stored |
| `fct_orders_payments_reconcile_with_staging` (`sum_matches`) | `sum(payment_total_brl)` in `fct_orders` equals `sum(payment_value_brl)` in `stg_olist__order_payments`: the roll-up loses no payment | R$0.01 (the test's default) |
| `item_gmv_reconciles_with_order_gmv`, `item_net_gmv_reconciles_with_order_net_gmv` (`sum_matches`) | GMV is equal at item and order grain, in total and for net orders | 0 |
| `known_issue__net_orders_without_payment` (DQ-08) | Net orders without a payment record | passes at 1, warns above, errors above 10 |
| `known_issue__payment_type_not_defined`, `known_issue__payment_with_zero_installments` (DQ-11) | Edge rows in `stg_olist__order_payments` | pass at 3 and 2, warn above, error above 50 |

The known-issue tests must detect, not merely pass: CI builds a synthetic fixture ([`ci/make_fixture.py`](../../ci/make_fixture.py)) that plants payment/GMV mismatches, a `not_defined` row, a zero-installment card row and a net order without payment, and [`ci/check_known_issues_detected.py`](../../ci/check_known_issues_detected.py) fails the build unless every `known_issue` test passes and stores at least one detected row.

## References

- Models: [`stg_olist__order_payments.sql`](../../dbt/models/staging/olist/stg_olist__order_payments.sql), [`int_payments_pivoted_to_orders.sql`](../../dbt/models/intermediate/int_payments_pivoted_to_orders.sql), [`int_orders_joined.sql`](../../dbt/models/intermediate/int_orders_joined.sql), [`fct_orders.sql`](../../dbt/models/marts/core/fct_orders.sql); tests and column docs in [`_core__models.yml`](../../dbt/models/marts/core/_core__models.yml) and [`_olist__models.yml`](../../dbt/models/staging/olist/_olist__models.yml); vars in [`dbt_project.yml`](../../dbt/dbt_project.yml); metrics in [`_semantic_models.yml`](../../dbt/models/semantic/_semantic_models.yml)
- Raw checks and queries: [`07_payment_reconciliation.sql`](../../sql/data_quality/07_payment_reconciliation.sql), [`issue_register.yml`](../../sql/data_quality/issue_register.yml) (DQ-08, DQ-11, DQ-14, DQ-16), [`01_three_analysts_on_raw.sql`](../../sql/metrics/01_three_analysts_on_raw.sql), [`q0_order_count_reconciliation.sql`](../../analyses/q0_order_count_reconciliation.sql)
- Docs: [metric definitions](../02_metric_definitions.md), [data quality report](../data_quality_report.md), [assumptions](../assumptions.md) (A-14 to A-16), [request and scope](../01_request_and_scope.md) (refund and chargeback accounting out of scope); [ADR 0002](./0002-order-status-and-net-orders.md), [ADR 0003](./0003-grain-fan-out-and-customer-identity.md)
