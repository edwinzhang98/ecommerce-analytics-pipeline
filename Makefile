# One-command pipeline:
#   make all  =  setup -> load (EL) -> dbt build (models + tests) -> dbt docs -> incremental check
#                -> cache -> notebooks -> report
# Then:  make dashboard   (or: uv run streamlit run dashboard/app.py)
# Every target runs inside the uv-managed virtualenv. `make help` lists them.
SHELL := /bin/bash
UV    ?= uv
PY    := $(UV) run python
DBT   := cd dbt && $(UV) run dbt
FLAGS := --profiles-dir .

# Optional overrides from .env (OLIST_RAW_DIR, DUCKDB_PATH, CACHE_DIR).
ifneq (,$(wildcard .env))
include .env
export
endif

.PHONY: help all setup load build docs cache notebooks report dashboard \
        incremental-check freshness lint metrics ci-local screenshots clean

help:  ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

all: setup load build docs incremental-check cache notebooks report  ## Full pipeline: raw CSVs -> marts -> tests -> docs -> app cache -> report
	@echo "Done. Start the app with: make dashboard"

setup:  ## Create the virtualenv (uv) and install dbt packages
	$(UV) sync
	$(DBT) deps $(FLAGS)

load:  ## EL: load the 9 raw CSVs into DuckDB (schema raw) and write the load audit
	$(PY) ingestion/load_raw.py

build:  ## dbt build: seeds, snapshot, models, data tests, unit tests, contracts
	$(DBT) build $(FLAGS)
	$(PY) -m olist_analytics.export artifacts

docs:  ## dbt docs: catalog + single-file static site (dbt/target/static_index.html)
	$(DBT) docs generate $(FLAGS) --static
	$(PY) -m olist_analytics.export artifacts

cache:  ## Export marts, DQ checks, test results and lineage to parquet for the app and report
	$(PY) -m olist_analytics.export cache

notebooks:  ## Execute the notebooks top to bottom and export them to reports/*.html
	$(PY) scripts/run_notebooks.py

report:  ## Build the standalone HTML report (reports/report.html)
	$(PY) -m olist_analytics.report

dashboard:  ## Start the Streamlit app
	$(UV) run streamlit run dashboard/app.py

incremental-check:  ## Prove fct_order_items: incremental == full refresh, status changes and late rows handled
	$(PY) scripts/check_incremental.py

freshness:  ## dbt source freshness (of the load)
	$(DBT) source freshness $(FLAGS)

lint:  ## Strict parse (deprecations = errors) + dbt_project_evaluator best-practice checks
	$(DBT) --warn-error parse $(FLAGS) --no-partial-parse --show-all-deprecations
	$(DBT) build $(FLAGS) --select package:dbt_project_evaluator dbt_project_evaluator_exceptions --vars '{run_project_evaluator: true}'
	$(PY) ci/check_run_results.py

metrics:  ## Query the semantic layer (MetricFlow) for the official order metrics
	cd dbt && $(UV) run --group semantic mf query --metrics placed_orders,net_orders,delivered_orders,net_gmv_brl,average_order_value_brl --group-by metric_time__year

ci-local:  ## Run the CI pipeline locally on the synthetic fixture (separate DuckDB file)
	$(PY) ci/make_fixture.py --out ci/fixture
	DUCKDB_PATH=$(CURDIR)/data/warehouse/ci.duckdb $(PY) ingestion/load_raw.py --raw-dir ci/fixture --expected ci/fixture/expected_row_counts.yml --duckdb-path $(CURDIR)/data/warehouse/ci.duckdb
	cd dbt && DUCKDB_PATH=$(CURDIR)/data/warehouse/ci.duckdb $(UV) run dbt build $(FLAGS) --target ci --vars '{min_net_orders_per_complete_month: 50}'
	DUCKDB_PATH=$(CURDIR)/data/warehouse/ci.duckdb $(PY) ci/check_known_issues_detected.py

screenshots:  ## Regenerate README screenshots (needs: uv sync --group screenshots && uv run playwright install chromium)
	$(UV) run --group screenshots python scripts/take_screenshots.py

clean:  ## Remove the warehouse, cache and dbt build output (raw CSVs are never touched)
	rm -rf data/warehouse data/cache dbt/target dbt/logs
