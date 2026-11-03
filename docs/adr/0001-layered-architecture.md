# ADR 0001: Layered architecture (raw -> staging -> intermediate -> marts)

**Status:** Accepted, 2026-11-03

## Context

Three analysts got three order counts from the raw tables: 117,601, 99,441 and 96,478. One is a grain error ([ADR 0003](0003-grain-fan-out-and-customer-identity.md)), the other two a definition dispute ([ADR 0002](0002-order-status-and-net-orders.md)). The Analytics Lead asked for tested, documented marts that analysts query instead of raw. That needs layers with one job each, grain settled before any join, and a contract-protected interface.

## Decision

Four layers, one DuckDB schema each. `dbt/macros/generate_schema_name.sql` drops dbt's `<target>_` schema prefix, because each environment is its own DuckDB file.

| Layer | Built as | Job | Naming |
|---|---|---|---|
| `raw` | tables, by `ingestion/load_raw.py` | The 9 CSVs as delivered, every source column VARCHAR, plus `_source_file` and `_loaded_at`. `raw.load_audit` records size, md5, physical lines, parsed and expected rows per file. | source names |
| `staging` | views | 1:1 per source table: rename, cast, clean text, add surrogate keys. No joins, no business logic. Only geolocation is de-duplicated, after city-name cleaning (1,000,163 to 720,495 rows). | `stg_olist__<entity>` |
| `intermediate` | views | Children aggregated to the order grain before any join; status and lifecycle logic; one row per person; one point per zip prefix. | `int_<entity>_<verb>`, e.g. `int_orders_classified` |
| `marts` | tables (`fct_order_items` incremental) | Star schema (`fct_orders`, `fct_order_items`, `dim_customers`, `dim_products`, `dim_sellers`, `dim_date`) plus the wide `customer_360` and `seller_scorecard`. Contracts enforced, `access: public`. | `fct_`, `dim_`; wide tables named for their use |

- **Raw is lossless.** VARCHAR keeps leading zeros (23,995 customer records have a zip prefix starting with 0), and no bad value can abort a load. The audit catches file traps: the reviews file has 104,719 physical lines but 99,224 rows, because comments contain line breaks (DQ-18).
- **Logic lives once, in intermediate.** `int_orders_joined` is the order-grain backbone of `fct_orders`, `fct_order_items` and, through `int_customers_aggregated_to_persons`, `dim_customers`. The wide marts read core marts only.
- **Marts are the interface.** Only marts are `access: public` (upstream keeps dbt's default, `protected`), and contracts pin the names and types of all 188 mart columns, all documented. Business numbers in `analyses/`, the app and the report come from marts; only the profiling SQL in `sql/data_quality/` and the `*_on_raw.sql` reproductions in `sql/metrics/` read raw.
- **Views upstream, tables for marts.** Views cost nothing to build and always reflect raw. Marts are tables because they are what gets queried, constraints and the incremental model need a table, and the parquet export reads them. The full `dbt build` (24 models, 4 seeds, 1 snapshot, 300 tests) takes 8.9 s.
- **Stack:** DuckDB 2.0.0, dbt Core 1.12.6, dbt-duckdb 1.11.1, Python 3.12.

## Alternatives considered

- **No intermediate layer.** Rejected: three core marts need the same fan-out-safe order backbone, and private copies drift.
- **Typing in the loader.** Rejected: a bad cast aborts the load, while in staging it fails inside `dbt build` with the row still queryable in `raw`.
- **dbt v2 / Fusion (released 2026-09).** Rejected for now: the agreed stack ([plan](../00_plan.md)) is dbt Core + dbt-duckdb, and v2's DuckDB support had not reached parity. The YAML already uses the v2-ready `arguments:` / `config:` syntax and CI parses with `--warn-error --show-all-deprecations`, so the upgrade should be mechanical.
- **Cloud warehouse (BigQuery, Snowflake, Postgres).** Rejected: a static 126 MB extract runs locally at zero cost with the same concepts (schemas, views, incremental models, contracts). Porting means a new `profiles.yml` and a few dialect functions (`date_diff`, `filter (where ...)`, `exclude`), not new layers or tests.
- **All tables, or all views.** Rejected: staging tables are a second copy of raw that nobody queries; mart views re-run every join per dashboard query and rule out constraints and the incremental model.
- **`fct_` / `dim_` names for the wide tables.** Rejected: `customer_360` and `seller_scorecard` are denormalised per-person and per-seller tables, named for the teams that use them. They are declared exceptions in `dbt/seeds/dbt_project_evaluator_exceptions.csv`, as is the source `raw.load_audit`, which only tests read.

## Consequences

Positive:

- One place to query, with grain guaranteed per layer; a test requires six query paths to agree on net orders (ADR 0002).
- 296 data tests and 4 unit tests run inside the 8.9 s build, cheap enough for every change.
- The same load and build run locally (`make all`) and in CI on a synthetic fixture, without credentials.

Negative and trade-offs:

- Views are recomputed on every build and every ad-hoc query; at 10-100x the volume, intermediate models would become tables.
- DuckDB has a single writer: a running `dbt build` locks the file, so the app reads a parquet cache (`src/olist_analytics/export.py`) and is only as fresh as the last `make cache`.
- Contracts make schema changes deliberate: a mart column change needs a YAML change, and on `fct_order_items` (`on_schema_change='fail'`) a full refresh.
- All typing sits in staging; a new source column stays untyped until a staging model declares it.
- CI never sees real volumes; the known-issue baselines are validated on the full data locally (`make all`).

## How this is verified

- Load: `row_count_matches_load_audit` on all 9 sources, `accepted_values: [ok]` on `raw.load_audit.status`, `dbt source freshness` on `_loaded_at`.
- Interface: `contract: enforced` on all 8 marts; the first CI check is `dbt --warn-error parse --show-all-deprecations`.
- Grain: `row_count_matches` on `int_orders_classified`, `int_orders_joined`, `int_customers_aggregated_to_persons` and every mart except `dim_date`, which has `is_continuous_date_spine` (ADR 0003).
- Conventions: `dbt_project_evaluator` runs in CI, and `ci/check_run_results.py` fails the build on any of its warnings (`make lint` locally). The two exposures in `dbt/models/exposures.yml` end the lineage at the marts.
- [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) runs, in order: parse, fixture, load, build, planted-issue detection, freshness, lint, semantic-layer smoke test, incremental check, docs.

## References

- [`ingestion/load_raw.py`](../../ingestion/load_raw.py), [`dbt/dbt_project.yml`](../../dbt/dbt_project.yml), [`generate_schema_name.sql`](../../dbt/macros/generate_schema_name.sql), [`_olist__sources.yml`](../../dbt/models/staging/olist/_olist__sources.yml), [`_int__models.yml`](../../dbt/models/intermediate/_int__models.yml), [`_core__models.yml`](../../dbt/models/marts/core/_core__models.yml), [`_business__models.yml`](../../dbt/models/marts/business/_business__models.yml), [`exposures.yml`](../../dbt/models/exposures.yml)
- [`dbt_project_evaluator_exceptions.csv`](../../dbt/seeds/dbt_project_evaluator_exceptions.csv), [`ci/check_run_results.py`](../../ci/check_run_results.py), [`src/olist_analytics/export.py`](../../src/olist_analytics/export.py)
- [`docs/00_plan.md`](../00_plan.md), [`docs/01_request_and_scope.md`](../01_request_and_scope.md), [`docs/data_dictionary.md`](../data_dictionary.md), [`docs/analyst_guide.md`](../analyst_guide.md)
- [ADR 0002](0002-order-status-and-net-orders.md) (net orders), [ADR 0003](0003-grain-fan-out-and-customer-identity.md) (grain and fan-out), [ADR 0005](0005-incremental-fct-order-items.md) (incremental `fct_order_items`)
