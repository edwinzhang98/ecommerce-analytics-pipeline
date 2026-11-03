# 00 — Project plan (one page)

**Owner:** Analytics Engineering · **Stakeholder:** Analytics Lead · **Consumers:** 3 analysts + business teams (ops, CRM, seller management)
**Written:** 2026-11-03, before any modelling work. Decisions taken without a sync are marked *(decided)* with the reason.

## Problem
Three analysts report three different order counts, so the business has stopped trusting our numbers. The deliverable is a set of tested, documented marts that become the only place analysts query. Raw tables become off-limits.

## Data
Olist Brazilian e-commerce marketplace (Kaggle `olistbr/brazilian-ecommerce`). It has 9 CSV files: 99,441 orders, 112,650 order items and 103,886 payments. Orders run from 2016-09-04 to 2018-10-17; the complete months are 2017-01 to 2018-08. The files stay outside the repo and are read through `config.yaml` / `.env`.

The first profiling pass found these issues to design for:
- `customer_id` is per order. The person is `customer_unique_id`: 96,096 people.
- `review_id` is not unique.
- Geolocation has ~1M rows for 19k zip prefixes, including points outside Brazil.
- 387 orders whose payments do not equal items + freight.
- 1,359 orders handed to the carrier before they were approved.
- 610 products have no category.

## Architecture
`CSV → Python EL (raw, all VARCHAR, load audit) → dbt staging (1:1, typed) → intermediate (aggregate to order grain, status logic) → marts (star schema + 2 wide tables) → tests → dbt docs → parquet cache → Streamlit + HTML report`

| Layer | Models (planned) |
|---|---|
| staging | 9 `stg_olist__*` views, one per source table |
| intermediate | `int_order_items_aggregated_to_orders`, `int_payments_pivoted_to_orders`, `int_reviews_deduplicated_to_orders`, `int_orders_joined`, `int_geolocation_aggregated_to_zip_prefixes`, `int_customers_aggregated_to_persons` |
| marts/core | `fct_orders`, `fct_order_items` (incremental), `dim_customers` (with RFM fields), `dim_products`, `dim_sellers`, `dim_date` |
| marts/business | `customer_360`, `seller_scorecard` |
| seeds | order-status mapping, Brazilian states/regions, missing category translations, national holidays |

## Data quality approach (a system, not a pile of tests)
1. **Load integrity.** The loader checks row counts against the known release and writes `raw.load_audit`; a dbt test compares the raw tables to that audit.
2. **Contracts at the edges.** Staging gets PK, not-null, accepted-values and relationship tests. Marts have enforced dbt model contracts.
3. **Known source issues as baselines.** Each documented raw issue gets a test that passes at today's known count, warns if it grows, and errors if it explodes.
4. **Modelling integrity.** Grain and fan-out guards, plus reconciliation across marts. The order count must agree in `fct_orders`, `fct_order_items` and `customer_360`.
5. **Unit tests** for the trickiest logic: late-delivery flag, review de-duplication, city cleaning.
6. **Data quality report**: every issue with its impact, how it is handled, and what downstream users should watch.

## Analysis outline (proof that the marts support analysis)
- **Q0 — the request itself.** Reproduce the three conflicting order counts from raw. Show that the marts give one answer by any query path.
- **Q1 — delivery and reviews by state.** How do delivery time and lateness relate to bad-review rate, by customer state? Reported as an association with intervals, not a causal effect.
- **Q2 — repeat purchase.** Repeat rate at person level, by first-purchase cohort and repeat window. Includes the sensitivity of the definition: orders vs checkouts vs purchase days.
- **Q3 — seller performance.** GMV concentration, seller handover SLA vs carrier delay, and review outcomes by seller.

## Deliverables
- dbt project
- Required docs: request/scope, metric definitions, data-quality checks, assumptions, readout, data dictionary, data quality report, analyst guide, 5 ADRs
- `analyses/` SQL with conclusions, plus `sql/` standalone checks
- 3 executed notebooks exported to HTML
- `reports/report.html`
- Streamlit app (7 pages in story order)
- Makefile (`make all`) and GitHub Actions CI
- README with lineage and dashboard screenshots

## Borrow vs add (from public reference projects)
- **Borrow**
  - Layering and naming from dbt Labs' `jaffle_shop_duckdb` and the dbt style guide.
  - The fan-trap write-up idea from `Keshetti-Nikhil/ecommerce-dbt-dimensional-modeling-warehouse`. We show our own fan-out numbers: 99,441 orders become 117,601 rows after joining items and payments, and revenue is inflated by 26.9%.
  - Test volume plus CI as a quality bar, from `devvdpatel/people-analytics-warehouse`.
  - Olist domain knowledge from the top Kaggle EDA notebooks (delivery vs review score).
- **Add** (what the references mostly lack)
  - Baseline-threshold DQ tests tied to a written DQ report.
  - ADRs.
  - An incremental model with a proven equivalence check.
  - Unit tests and model contracts.
  - Metric definitions that settle the order-count dispute.
  - Business analyses written conservatively.
  - A readout for non-technical stakeholders.

## Decisions taken up front
- *(decided)* **dbt Core 1.12 + dbt-duckdb, not dbt v2 (Fusion, released 2026-09).** The target stack is dbt-core + dbt-duckdb, and v2's DuckDB parity is still open. The YAML uses `arguments:` / `config:` syntax, so an upgrade is mechanical.
- *(decided)* **Official order KPI = "net orders"**: placed minus canceled and unavailable. "Placed" and "delivered" are published alongside it as separately named metrics. This is reversible: one seed row changes it. See ADR 0002.
- *(decided)* **CI runs on a generated synthetic fixture with the raw schema.** Raw data cannot be committed, and wiring Kaggle credentials into GitHub is out of scope. Full-volume validation runs locally (`make all`).
- *(decided)* **`fct_order_items` is the incremental model.** Item rows do not change after purchase; mutable order state lives in `fct_orders`. See ADR 0005.

## Risks
- **Data is static and historical (2016–2018).** Recency is computed against the last order date in the data, not today.
- **CI cannot see real volumes.** The baseline thresholds are validated locally.
- **The dashboard must stay fast (< 10 s).** Pages read a parquet cache only.
