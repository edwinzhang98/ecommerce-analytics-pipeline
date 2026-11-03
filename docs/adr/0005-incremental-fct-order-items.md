# ADR 0005: Incremental `fct_order_items`

**Status:** Accepted, 2026-11-03

## Context

`fct_order_items` has one row per unit sold: 112,650 rows across 98,666 orders. Its item attributes (price, freight, product, seller, shipping limit) are fixed at purchase. From the order it copies the purchase time and the customer, which do not change, and `order_status` and `is_net_order`, which can, so that item-level sums can be restricted to net orders without a join.

There is no performance case for incremental loading at this volume: the whole project (24 models, 4 seeds, 1 snapshot, 300 tests) builds in 8.9 seconds. The model is incremental to demonstrate the production pattern where a mistake is cheap. In a company warehouse the item fact is typically an early candidate for incremental loading, and the hard part is the guardrails: proving the result equals a full refresh, detecting drift, and knowing when to rebuild.

Why this model: `fct_orders` holds the mutable order state (status, lifecycle timestamps, latest review, payments) and is rebuilt on every run, like every other mart ([ADR 0001](./0001-layered-architecture.md)). In `fct_order_items` only `order_status` and `is_net_order` can change, and only while the order is open, i.e. in a status with `is_terminal_status = false` in the `order_status_mapping` seed ([ADR 0002](./0002-order-status-and-net-orders.md)). Today 1,729 orders are open and 97,712 terminal (delivered, canceled, unavailable).

## Decision

Config: `materialized='incremental'`, `incremental_strategy='delete+insert'`, `unique_key='order_item_key'` (surrogate key of `order_id` + `order_item_id`), `on_schema_change='fail'`, contract enforced, `not_null` and `primary_key` constraints on `order_item_key`.

Each incremental run re-processes the union of:

1. **New and recent orders:** `order_purchased_at >= max(order_purchased_at)` of the existing table minus `fct_order_items_lookback_days` (var, 3 days), so rows that land a little late are still picked up.
2. **Every order that was open at the last run:** orders whose stored `order_status` is not terminal in the seed, whatever their purchase date, because their status, and so `is_net_order`, may have moved. Today that is 1,904 item rows of 1,721 open orders.

Rows outside both sets are not expected to change: item attributes are fixed at purchase, and a terminal status is final by the seed's definition. Delete+insert replaces the re-processed rows by key, so a rerun with no new data leaves the table identical.

Three mechanics:

- The seed is referenced only inside the `is_incremental()` branch, which is false while dbt parses the project, so the model declares `-- depends_on: {{ ref('order_status_mapping') }}`. Without the hint, every incremental run would stop with a compilation error.
- `on_schema_change='fail'` stops an incremental run on any column change until a `--full-refresh`; under an enforced contract, column changes are deliberate anyway.
- `purchase_not_in_the_future` on `stg_olist__orders` guards the watermark: one future purchase timestamp would freeze the window.

## Alternatives considered

- **Full table every run.** The honest default at this volume and what every other mart does; rejected only because the pattern is the point. Reverting is one config line.
- **`merge` strategy.** Rejected: with the same `unique_key` it yields the same rows, since every item of a re-processed order is rewritten anyway, and delete+insert needs no column-level update logic.
- **Load-time (`_loaded_at`) or change-data-capture watermark.** Rejected: the loader replaces every raw table on each load (`create or replace table raw.<table>`) with one `_loaded_at` for all rows, so a load-time watermark selects everything, and the source has no change feed. A per-row change-time watermark would beat purchase time, catching late arrivals and status changes of any age; it is the first thing to adopt if the source provides one.
- **`microbatch` strategy.** Rejected: it re-processes event-time batches within a fixed lookback, but status changes are not confined to recent purchases (1,344 of the 1,939 changed rows in the check below were outside a 3-day window), and the oldest open order is the first order in the extract (2016-09-04), so a lookback covering every open order is the whole table.

## Consequences

Positive:

- Consumers see an ordinary mart: same contract, tests and public access.
- The pattern ships with its proof, re-run in CI on every pull request.

Negative and trade-offs:

- **Late arrivals beyond the window are missed.** An order that first appears with a purchase time more than 3 days before the newest loaded purchase is skipped, and a row deleted from the source stays (delete+insert only replaces keys it re-delivers). Both are detected, not prevented: `fct_order_items_has_one_row_per_source_item` fails on the next build. Mitigation: that test runs in every build and in CI, and once the pipeline is scheduled, a periodic full refresh (for example weekly) bounds how long a gap lasts.
- **"Terminal never changes" is the seed's rule, not a source guarantee**: 6 canceled orders carry a delivery timestamp (DQ-14). A terminal order that changed status would be missed. `snp_olist__orders` would record the new version, and a stale `is_net_order` would fail `item_net_gmv_reconciles_with_order_net_gmv` and the query-path test below; a change between canceled and unavailable would leave only `order_status` stale, which no test catches.
- Widening the lookback costs rows per run, never correctness. Column changes, and reclassifying a terminal status in the seed (ADR 0002), need a full refresh.
- One more var, a seed dependency and a runbook to know, for no speed gain today.

## How this is verified

**Equivalence check.** [`scripts/check_incremental.py`](../../scripts/check_incremental.py) (`make incremental-check`, part of `make all`) uses its own DuckDB file and the loader's `--cutoff-date`, which keeps only orders purchased before the cutoff and hides later lifecycle events, so an order delivered later still reads `shipped` or `processing`. Results on the real data (`data/cache/incremental_check.json`, 46.6 seconds):

| Scenario A: extract as of 2018-07-01, then the full extract | Result |
|---|---|
| First extract, `--full-refresh` | 98,309 rows, watermark 2018-06-30 23:59:49 |
| Full extract, incremental run | 112,650 rows, equal to staging |
| Rows selected by the watermark rule | 14,961: 14,341 new, 620 inside the 3-day lookback |
| Existing rows whose status changed and were updated | 1,939 |
| of which older than the lookback window (caught by rule 2 only) | 1,344 |
| Rerun with no new data | 112,650 rows, checksum identical |
| `--full-refresh` on the same data | row-level checksum identical to the incremental result |
| Orders with a second version in `snp_olist__orders` | 1,717 |

Scenario B, late arrivals: 25 orders purchased 30-60 days before the cutoff are held back from the first extract (`--hold-back-orders`). On the full extract the incremental run misses their 26 rows (outside the window, and never loaded, so not open at the last run), `fct_order_items_has_one_row_per_source_item` fails as designed, and `--full-refresh` repairs the table to scenario A's checksum.

**CI.** The "Incremental model check" step of [`ci.yml`](../../.github/workflows/ci.yml) runs the script on the synthetic fixture on every pull request and push to `main`, and uploads `data/cache/incremental_check_ci.json`. The script exits non-zero unless the rerun and the full refresh match the incremental result, status changes outside the window were caught, the snapshot recorded history, and the scenario B gap was both detected and repaired.

**Every build.** The grain, key and relationship tests of `fct_order_items`, `item_gmv_reconciles_with_order_gmv` and `item_net_gmv_reconciles_with_order_net_gmv` (tolerance 0), and [`assert_net_order_count_consistent_across_query_paths`](../../dbt/tests/singular/assert_net_order_count_consistent_across_query_paths.sql) (distinct net orders in `fct_order_items` plus net orders without items must equal the 98,207 in `fct_orders`).

**Runbook** after a grain-test failure, a column change or a seed reclassification: `cd dbt && uv run dbt build --profiles-dir . --full-refresh -s fct_order_items`.

## References

- Model and tests: [`fct_order_items.sql`](../../dbt/models/marts/core/fct_order_items.sql), [`_core__models.yml`](../../dbt/models/marts/core/_core__models.yml), [`_olist__models.yml`](../../dbt/models/staging/olist/_olist__models.yml) (`purchase_not_in_the_future`), [`test_row_count_matches.sql`](../../dbt/tests/generic/test_row_count_matches.sql), [`test_sum_matches.sql`](../../dbt/tests/generic/test_sum_matches.sql); vars in [`dbt_project.yml`](../../dbt/dbt_project.yml)
- Status rule and history: [`order_status_mapping.csv`](../../dbt/seeds/order_status_mapping.csv), [`_seeds.yml`](../../dbt/seeds/_seeds.yml), [`snp_olist__orders.yml`](../../dbt/snapshots/snp_olist__orders.yml)
- Proof: [`scripts/check_incremental.py`](../../scripts/check_incremental.py), [`ingestion/load_raw.py`](../../ingestion/load_raw.py) (`--cutoff-date`, `--hold-back-orders`), [`Makefile`](../../Makefile), [`ci.yml`](../../.github/workflows/ci.yml)
- Docs: [data quality checks](../03_data_quality_checks.md), [assumptions](../assumptions.md) (A-28, A-29), [analyst guide](../analyst_guide.md); [ADR 0001](./0001-layered-architecture.md), [ADR 0002](./0002-order-status-and-net-orders.md)
