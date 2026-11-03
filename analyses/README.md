# Business-question analyses (`analyses/`)

Each `.sql` file in this folder answers one business question from the published marts only (schema `marts`). None of them reads `raw`, `staging` or `intermediate`. The conclusions sit next to each file in a `.md` with the same name.

Together they cover the two things the Analytics Lead asked for. Analysts now get one order count whichever way they query (Q0), and the marts are enough to answer real business questions without touching raw data (Q1–Q3).

## Files

| SQL | Question | Decision it supports | Decision owner | Write-up |
|---|---|---|---|---|
| [`q0_order_count_reconciliation.sql`](q0_order_count_reconciliation.sql) | Do the three analysts now get the same order count? | Adopt net orders as the headline order KPI; move analysts to marts only | Analytics Lead, Finance sign-off | [Q0](q0_order_count_reconciliation.md) |
| [`q1_delivery_vs_reviews_by_state.sql`](q1_delivery_vs_reviews_by_state.sql) | How do delivery time and lateness relate to bad reviews, and which states are worst? | Where logistics improvements start | Ops / logistics lead | [Q1](q1_delivery_vs_reviews_by_state.md) |
| [`q2_repeat_purchase.sql`](q2_repeat_purchase.sql) | What share of customers buy again, and how quickly? | Retention vs acquisition budget; whether first-order experience is a retention lever | CRM manager | [Q2](q2_repeat_purchase.md) |
| [`q3_seller_performance.sql`](q3_seller_performance.sql) | How concentrated is GMV across sellers, and how do sellers differ on handover and reviews? | Which sellers seller management works with first | Seller management lead | [Q3](q3_seller_performance.md) |

## Answers in one line

Numbers come from the build of 2026-11-03, with default parameters.

- **Q0.** Five different query paths through the marts all return 98,207 net orders and R$15,735,527.03 net GMV. Placed orders (99,441) and delivered orders (96,478) are published under their own names.
- **Q1.** Late deliveries get a bad review (1-2 stars) 62.42% of the time; on-time deliveries get one 9.25% of the time. RJ has the second-largest number of late deliveries, and more bad reviews than its lateness and delivery times predict.
- **Q2.** 2.17% of customers are repeat customers, and 2.00% of customers in fully observed cohorts return within 180 days. A late or badly reviewed first order goes with a slightly lower return rate, but the gap is too small to be a retention lever.
- **Q3.** The top 10% of sellers hold 66.7% of GMV. In single-seller orders, a late handover to the carrier goes with a 20.93% late-delivery rate, against 5.44% after an on-time handover. 15 established sellers clear both alert thresholds even at the low end of their 95% intervals.

All of these are associations in historical data, not measured effects of an intervention.

## How to run

You need a built warehouse first (`make all`, or `make setup load build`).

```bash
uv run python scripts/run_sql.py analyses/q0_order_count_reconciliation.sql
uv run python scripts/run_sql.py analyses/q1_delivery_vs_reviews_by_state.sql --var bad_review_max_score=1
uv run python scripts/run_sql.py analyses/q2_repeat_purchase.sql --var repeat_window_days=90
uv run python scripts/run_sql.py analyses/q3_seller_performance.sql --var min_seller_orders=100 --max-rows 15
```

- [`scripts/run_sql.py`](../scripts/run_sql.py) opens the DuckDB warehouse read-only (`duckdb_path` in `config.yaml`, or the `DUCKDB_PATH` environment variable). It prints every result set in the file as its own table.
- `--var name=value` overrides one `set variable` default. Repeat the flag to override several.
- `--max-rows` caps the rows printed per result (default 40). Q3's `pareto_curve` has one row per active seller, 3,053 rows.
- The files are plain DuckDB SQL, so any DuckDB client connected to the warehouse runs them too. To change a parameter there, edit its `set variable` line.

## Parameters

| File | Variable | Default | Meaning | Results it changes |
|---|---|---|---|---|
| Q0 | none | | | |
| Q1 | `bad_review_max_score` | `2` | A review with this score or lower is a bad review | all |
| Q1 | `min_orders_per_state` | `300` | States with fewer reviewed deliveries are hidden | `by_state`, `state_correlation` |
| Q1 | `complete_months_only` | `true` | Only orders purchased 2017-01 to 2018-08 | all |
| Q2 | `repeat_window_days` | `180` | A customer has returned if their second purchase day falls within this many days of the first | `cohort_repeat`, `repeat_by_first_experience` |
| Q3 | `min_seller_orders` | `50` | Net orders a seller needs to count as established | `seller_quadrants`, `watchlist` |
| Q3 | `late_handover_threshold_pct` | `15` | Late-handover rate (%) above which a seller is flagged | `seller_quadrants`, `watchlist` |
| Q3 | `bad_review_threshold_pct` | `20` | Bad-review rate (%) above which a seller is flagged | `seller_quadrants`, `watchlist` |

Q1's `bad_review_max_score` applies only inside Q1. Q2 and Q3 use the marts' `is_bad_review` flag, which is set by the dbt variable of the same name (also 2) in `dbt/dbt_project.yml`.

## One SQL file per question, used everywhere

| Where | How it runs the file |
|---|---|
| Terminal | `scripts/run_sql.py`, as above |
| Streamlit app | The Overview page shows Q0 ([`1_overview.py`](../dashboard/app_pages/1_overview.py)). The Business questions page runs Q1–Q3, and its controls set the parameters above ([`5_business_questions.py`](../dashboard/app_pages/5_business_questions.py)) |
| HTML report and notebooks | `reports/report.html`, [`notebooks/02_order_count_reconciliation.ipynb`](../notebooks/02_order_count_reconciliation.ipynb), [`notebooks/03_business_questions.ipynb`](../notebooks/03_business_questions.ipynb) |
| Every `dbt build` | Q0's order-count check also runs as a singular test: [`assert_net_order_count_consistent_across_query_paths.sql`](../dbt/tests/singular/assert_net_order_count_consistent_across_query_paths.sql) |

The app, the report and the notebooks all call [`src/olist_analytics/analysis.py`](../src/olist_analytics/analysis.py), which runs these files and holds the default parameters. So a number cannot differ between the terminal, the app and the report unless the data does.

Only the data source differs. `run_sql.py` and the notebooks open the warehouse read-only. The app and the report run the same SQL against an in-memory DuckDB whose `marts` schema is a set of views over the parquet cache ([`src/olist_analytics/data.py`](../src/olist_analytics/data.py)), so their numbers are as current as the last `make cache`.

## File conventions

- A header comment states the question, the inputs, the outputs and the run command, plus the decision, parameters and caveats where they apply.
- An optional preamble holds the `set variable` defaults and temp macros. One example is `wilson_low` / `wilson_high`, the 95% Wilson score interval for a rate.
- Each result set starts with a line `-- result: <name>`. [`src/olist_analytics/sqlfile.py`](../src/olist_analytics/sqlfile.py) splits the file on these markers.
- Tables are referenced as `marts.<table>`, not `{{ ref() }}`. That way the same file runs unchanged against the warehouse and against the parquet cache, which is why these are not dbt analyses (`dbt/analyses/` is empty). Their dependency on the marts is declared as the exposure `business_question_analyses` in [`dbt/models/exposures.yml`](../dbt/models/exposures.yml), so they appear in the lineage graph.

## Adding a question

1. Query the marts only. If a question needs raw data, the gap goes on the marts backlog, not into this folder.
2. Use the official definitions in [docs/02_metric_definitions.md](../docs/02_metric_definitions.md): `is_net_order`, `is_late_delivery`, `is_bad_review`, `is_repeat_customer` and `order_gmv_brl`. [docs/analyst_guide.md](../docs/analyst_guide.md) covers which table to use and how to join; [docs/data_dictionary.md](../docs/data_dictionary.md) lists every column.
3. Put each threshold in a `set variable` with a default. State the population and its filters in the header.
4. Report each rate with its counts and a 95% Wilson interval. Do not compare cohorts that have not been observed for the full window.
5. Write the conclusion in a `.md` with the same name, using the same sections as the existing write-ups: question, decision, population, method, results, conclusion, recommendations, next step and how to reproduce.
6. If the app or the report should show the analysis, add a function to `src/olist_analytics/analysis.py`, and add the marts it reads to the exposure.
