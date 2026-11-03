# `sql/`

Standalone DuckDB SQL that the data team runs outside dbt. [`data_quality/`](data_quality/) profiles the `raw`
schema exactly as loaded; [`metrics/`](metrics/) reproduces the order-count dispute and the customer-key trap on
raw, and shows the official monthly numbers from the marts. Business questions answered from the marts live in
[`analyses/`](../analyses/), and the checks that must hold on every build are dbt tests in [`dbt/`](../dbt/).
Analysts do not need this folder: they query `marts` ([analyst guide](../docs/analyst_guide.md)).

## What lives here

| Path | Contents | Reads |
|---|---|---|
| `data_quality/01_*.sql` to `08_*.sql` | Sanity checks on the raw tables, numbered in the order to run them on a new extract: load reconciliation, keys, nulls, value ranges, time coverage, referential integrity, payments, lifecycle. Results are written up in [03_data_quality_checks.md](../docs/03_data_quality_checks.md). | `raw` |
| `data_quality/issue_register.yml` | Every raw-data issue found: 21 issues in 9 classes, `DQ-01` to `DQ-21`. Each entry has a `count_sql`, the handling, advice for downstream users and the dbt tests that guard it, where there are any. | `raw` |
| `metrics/` | The order-count and customer-key diagnoses on raw (`01`, `03`) and the official monthly order metrics from the marts (`02`). | `raw`, `marts` |

The checks read `raw` on purpose: they describe the source as delivered, before any cleaning. Once a check finds
an issue, a dbt test takes over ([From check to test](#from-check-to-test)), so a regression shows up in every
build, as a warning or an error, instead of waiting for someone to rerun a script.

The register is the single source of truth for issue counts. `make cache` re-runs every `count_sql`, every
`data_quality/*.sql` file and `metrics/01` and `03`, and writes the results to `data/cache/`, which the
Streamlit app and `reports/report.html` read. The issue table in
[data_quality_report.md](../docs/data_quality_report.md) is rendered from the register by
[`render_docs_tables.py`](../scripts/render_docs_tables.py), so published counts follow the data.

## File convention

Every file follows the same four conventions. The business questions in `analyses/` follow them too (their
headers name the decision the answer feeds and list any parameters), and
[`sqlfile.py`](../src/olist_analytics/sqlfile.py) splits both into their result sections.

1. **Header comment** with `Purpose`, `Inputs` (schema-qualified tables), `Output` (one line per result) and
   `Run` (the exact command):

   ```sql
   -- =====================================================================================
   -- 05 Time ranges of every timestamp, and monthly order coverage
   -- Purpose : what period the extract really covers, and which months are incomplete.
   -- Inputs  : raw.orders, raw.order_items, raw.order_reviews
   -- Output  : result 1 `time_ranges`: one row per timestamp column (min, max, nulls)
   --           result 2 `monthly_coverage`: orders per purchase month, all months in range
   -- Run     : uv run python scripts/run_sql.py sql/data_quality/05_time_ranges_and_coverage.sql
   -- =====================================================================================
   ```

2. **Parameters, when a file has any.** A preamble of `set variable <name> = <default>;` lines, read in the
   queries with `getvariable('<name>')`, plus any `create or replace temp macro` helpers. The defaults let the
   file run as-is; callers override them. No file in `sql/` takes parameters today. The analyses do, for example
   `set variable repeat_window_days = 180;` in [`q2_repeat_purchase.sql`](../analyses/q2_repeat_purchase.sql).

3. **Result sections.** Each result starts with a line `-- result: <name>` (letters, digits and underscores)
   followed by one query. A file can return several results, and the runner returns one table per section. The
   names are an interface: the app reads cached results by file and result name (for example
   `05_time_ranges_and_coverage` / `monthly_coverage`), so renaming a section means updating its readers.

4. **Plain, read-only DuckDB SQL.** Schema-qualified names (`raw.orders`, `marts.fct_orders`) and no Jinja or
   `ref()`, so a file runs in any DuckDB client. Queries only, plus session state (variables, temp macros):
   nothing writes to the warehouse. Lower-case keywords and CTEs, as in the dbt models.

## How to run

`data_quality/` and `metrics/01` and `03` need the `raw` schema (`make load`); `metrics/02` needs the marts
(`make build`).

```bash
uv run python scripts/run_sql.py sql/data_quality/07_payment_reconciliation.sql
uv run python scripts/run_sql.py analyses/q2_repeat_purchase.sql --var repeat_window_days=90
```

- The runner opens the warehouse named in `config.yaml` (`duckdb_path`, overridden by `DUCKDB_PATH` in the
  environment or `.env`) read-only and prints each result as `== <name> (<n> rows)`.
- `--var name=value` overrides a `set variable` default; repeat it for several. Values are read as integer,
  float, `true` / `false`, or text.
- `--max-rows N` caps the rows printed per result (default 40).

Without Python, use the DuckDB CLI (the project uses DuckDB 2.0.0) or paste the file into any DuckDB client opened
on the warehouse file. The `set variable` defaults then apply.

```bash
duckdb -readonly data/warehouse/olist.duckdb -f sql/data_quality/07_payment_reconciliation.sql
```

A read-only session still holds a lock on the file. Close it before `make load` or `make build`, which need
write access.

## Files

| File | Reads | Results | Purpose |
|---|---|---|---|
| [`data_quality/01_row_counts_vs_load_audit.sql`](data_quality/01_row_counts_vs_load_audit.sql) | `raw` | `row_counts` | Per table: physical lines vs parsed rows vs the release's known row count vs rows in `raw`. |
| [`data_quality/02_primary_keys.sql`](data_quality/02_primary_keys.sql) | `raw` | `primary_keys` | Rows vs distinct values per candidate key: `review_id` and `order_id` in reviews are not unique, `customer_unique_id` repeats across customer records, and geolocation repeats rows. |
| [`data_quality/03_null_profile.sql`](data_quality/03_null_profile.sql) | `raw` | `null_profile` | Exact null count and share for every raw column that has nulls. |
| [`data_quality/04_value_ranges_and_outliers.sql`](data_quality/04_value_ranges_and_outliers.sql) | `raw` | `value_ranges` | Min, p01, median, p99 and max of amounts, installments, review scores, product weight and length, and coordinates, with a count of values that break a plausibility rule. |
| [`data_quality/05_time_ranges_and_coverage.sql`](data_quality/05_time_ranges_and_coverage.sql) | `raw` | `time_ranges`, `monthly_coverage` | First and last value and null count of every timestamp column; placed and net orders per purchase month, flagging months with fewer than 100 orders. |
| [`data_quality/06_referential_integrity.sql`](data_quality/06_referential_integrity.sql) | `raw` | `referential_integrity` | Orphan keys, parents without children (orders without items, payments or reviews) and zip or category lookups that do not resolve. |
| [`data_quality/07_payment_reconciliation.sql`](data_quality/07_payment_reconciliation.sql) | `raw` | `summary`, `difference_buckets` | Payments vs items + freight per order: totals, and orders by size of the gap. |
| [`data_quality/08_lifecycle_consistency.sql`](data_quality/08_lifecycle_consistency.sql) | `raw` | `lifecycle_anomalies` | Lifecycle timestamps out of order, and statuses that contradict the timestamps. |
| [`data_quality/issue_register.yml`](data_quality/issue_register.yml) | `raw` | one count per issue (run by `make cache`) | The 21 known issues with count query, handling, downstream advice and guarding tests. |
| [`metrics/01_three_analysts_on_raw.sql`](metrics/01_three_analysts_on_raw.sql) | `raw` | `order_counts` | The three conflicting "order counts" (fan-out join, all statuses, delivered only) next to the official net count, with the revenue each query would report. |
| [`metrics/02_official_order_counts_by_month.sql`](metrics/02_official_order_counts_by_month.sql) | `marts` | `monthly_order_metrics`, `totals` | Placed, net and delivered orders, net GMV and AOV per month on the local purchase date, with the complete-month flag: the query behind the monthly business review. |
| [`metrics/03_customer_key_trap_on_raw.sql`](metrics/03_customer_key_trap_on_raw.sql) | `raw` | `repeat_rate_by_key` | Share of customers with 2+ net orders, counted on `customer_id` (0%) vs `customer_unique_id` (3.04%): why the marts expose only the person key (DQ-01). The official repeat rate, on distinct purchase days, is 2.17%. |

`metrics/01` and `03` read `raw` to reproduce what went wrong. Nothing should be built on them.

## From check to test

Each raw check has dbt tests that hold the same line on every `dbt build`. The exact tests per issue are in the
register's `dbt_tests` field.

| Check | Guarded in dbt by |
|---|---|
| 01 load reconciliation | `row_count_matches_load_audit` on all 9 sources |
| 02 keys | `unique` and `not_null` on staging keys; `dim_customers_has_one_row_per_person`; `known_issue__review_id_shared_across_orders`, `known_issue__orders_with_multiple_reviews` |
| 03 nulls | `not_null` on required columns; `known_issue__products_missing_category`, `known_issue__products_missing_weight` |
| 04 value ranges | `non_negative`, `dbt_utils.accepted_range`; `known_issue__geolocation_points_outside_brazil`, `known_issue__payment_with_zero_installments`, `known_issue__products_with_zero_weight` |
| 05 time coverage | `assert_complete_months_have_expected_volume`, `assert_shipping_limit_within_90_days_of_purchase`; load freshness runs separately (`make freshness`) |
| 06 referential integrity | `relationships` from every fact to its dimensions; `assert_net_orders_have_items`, `known_issue__net_orders_without_payment`; `known_issue__customer_zip_prefix_missing_from_geolocation`, `known_issue__seller_zip_prefix_missing_from_geolocation`; `assert_all_product_categories_translated` |
| 07 payments | `assert_payments_reconcile_with_order_gmv`, `fct_orders_payments_reconcile_with_staging` |
| 08 lifecycle | The 7 lifecycle `known_issue__*` tests, for example `known_issue__carrier_pickup_before_approval` |

## Adding a check

- Number it after the last file in its folder, copy the header and fill in all four fields.
- Add one `-- result:` section per table you want back, and parameters as `set variable` defaults.
- Run it with `scripts/run_sql.py` against the full extract before committing.
- `make cache` picks up new `data_quality/*.sql` files automatically. A new `metrics/` file must be added to
  `export_sql_results` in [`export.py`](../src/olist_analytics/export.py) to reach the app.
- A new issue gets the next ID (`DQ-22`) in the register, with a `count_sql`, plus a dbt test (a `known_issue`
  baseline if the issue is accepted), so the build watches it from then on.
