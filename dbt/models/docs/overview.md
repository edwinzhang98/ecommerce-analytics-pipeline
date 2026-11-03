{% docs __overview__ %}
# Olist analytics marts

**Purpose.** One trusted, tested, documented set of tables for every order, customer, product and seller question.
Analysts query the `marts` schema only. `raw`, `staging` and `intermediate` are implementation details.

**Layers**

| Layer | Schema | What it does |
|---|---|---|
| raw | `raw` | Lossless copy of the 9 source CSVs (all VARCHAR), loaded by `ingestion/load_raw.py`, plus `raw.load_audit`. |
| staging | `staging` | One model per source table: rename, cast types, normalise text, de-duplicate. No joins, no business logic. |
| intermediate | `intermediate` | Roll child tables up to the order grain before joining (no fan-out); order status and lifecycle logic; person-level customers; zip-prefix centroids. |
| marts | `marts` | Star schema (`fct_orders`, `fct_order_items`, `dim_customers`, `dim_products`, `dim_sellers`, `dim_date`) plus two wide business tables (`customer_360`, `seller_scorecard`). Contracts enforced. |

**The three order counts** (ADR 0002), all from `fct_orders`:
- *placed orders*: every order, any status
- *net orders*: the headline KPI; excludes `canceled` and `unavailable`
- *delivered orders*: status `delivered`

Docs in the repo: `docs/data_dictionary.md`, `docs/analyst_guide.md`, `docs/data_quality_report.md`, `docs/adr/`.
{% enddocs %}
