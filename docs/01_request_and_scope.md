# 01 — Request and scope

## The request (verbatim)

> Analytics Lead 说：「三个 analyst 算出来的订单数都不一样，业务已经不信我们的数了。把原始数据建成一套可信的、有测试、有文档的 marts，让 analyst 只查 marts 不碰 raw。」

*Translation:* "Our three analysts each came up with a different order count, and the business no longer trusts our numbers. Turn the raw data into a trustworthy, tested and documented set of marts, so analysts query only the marts and never touch raw."

- **Requested by:** Analytics Lead (my manager)
- **Received:** 2026-11-03
- **Standard deliverable for this kind of request:**
  - dbt project (layers, tests, docs)
  - data dictionary
  - modelling decision records
  - CI
  - analyst usage guide

## What is actually going wrong (diagnosis before building)

I reproduced the disagreement on the raw tables. Three reasonable-looking queries return three different "order counts":

| Who | Query they wrote | Result | Why it differs |
|---|---|---:|---|
| Analyst A (finance) | `count(*)` over `orders` joined to `order_items` and `order_payments` (built for a revenue report) | **117,601** | Fan-out: one order with 3 items and 2 payments becomes 6 rows. Revenue from the same join is R$20.31M against R$16.01M actually paid (+26.9%). |
| Analyst B (ops) | `count(*)` from `orders` | **99,441** | Counts every status, including 625 canceled and 609 unavailable orders. |
| Analyst C (marketing) | `count(*)` from `orders` where `order_status = 'delivered'` | **96,478** | Only delivered orders. Legitimate, but a different metric with the same name. |

So the problem is two problems:
1. **Grain errors.** Joining at the wrong grain double-counts orders and money.
2. **Definition drift.** "Orders" means different things to different people.

The second problem is solved by agreeing on definitions, not by code. The first is solved by modelling plus tests.

## Clarified analytical questions

1. **What is an order, and which count is official?** Define *placed*, *net* and *delivered* orders, the date basis (purchase timestamp, local time) and the exclusions. Publish all three under distinct names. → `docs/02_metric_definitions.md`, ADR 0002
2. **Can the marts be trusted?** Every raw-data issue is found, quantified, handled and documented, and every mart's grain is guaranteed by tests. → `docs/data_quality_report.md`, `docs/03_data_quality_checks.md`
3. **Do the marts support real analysis without touching raw?** Answer three business questions from marts only:
   - Q1. How do delivery time and lateness relate to bad reviews, by delivery state (the order's delivery address)?
   - Q2. What share of customers buy again, and how quickly?
   - Q3. How concentrated is GMV across sellers, and how do sellers differ on handover SLA and review outcomes?
4. **Can analysts self-serve?** They need to know which table answers which question, how to join, and what not to do. → `docs/analyst_guide.md`, `docs/data_dictionary.md`

## Decision maker and decision points

| Decision | Owner | When | What would change it |
|---|---|---|---|
| Adopt "net orders" as the single headline order KPI | Analytics Lead, with Finance sign-off | Before the next monthly business review | If Finance books revenue on delivery, the headline would switch to delivered orders. That is one seed change (ADR 0002). |
| Retire raw-table access for analysts (marts only) | Analytics Lead | After analysts have used the marts for one reporting cycle | Any recurring question the marts cannot answer goes onto the marts backlog before raw access is removed. |
| Accept the known data-quality baselines (e.g. 249 orders whose payments differ from items + freight by more than R$1) | Analytics Lead and source owner (Olist platform team) | With this release | If a baseline grows, the warn/error tests fire and the source owner is engaged. |

## In scope
- EL from the 9 CSV files into DuckDB (`raw`), with a load audit
- dbt staging / intermediate / marts (star schema + `customer_360`, `seller_scorecard`)
- Data tests, unit tests, model contracts, docs and lineage
- CI on pull requests
- Data dictionary, ADRs, data-quality report and analyst guide
- Three example analyses, a Streamlit app and an HTML report

## Out of scope (and why)
- **Real-time or scheduled orchestration (Airflow etc.).** The data is a static extract; `make all` is the orchestrator.
- **Refund and chargeback accounting.** The source has no refund table; see ADR 0004 for how canceled orders are treated.
- **Causal claims.** The business analyses report associations and intervals.
- **Forecasting and ML.**

## Success criteria
- Any analyst gets the same order count by any documented query path. Enforced by a dbt test.
- `dbt build` is green with tests on every mart key.
- Every mart column is documented.
- A new analyst can answer the three example questions using only `docs/analyst_guide.md` and the marts.
