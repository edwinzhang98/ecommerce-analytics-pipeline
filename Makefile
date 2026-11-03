# One-command pipeline. `make all` = setup -> load -> dbt build -> docs -> cache -> notebooks -> report.
# Every target runs inside the uv-managed virtualenv.
SHELL := /bin/bash
UV    ?= uv
DBT   := cd dbt && $(UV) run dbt
DBT_FLAGS := --profiles-dir .

# Load optional overrides from .env (OLIST_RAW_DIR, DUCKDB_PATH, CACHE_DIR).
ifneq (,$(wildcard .env))
include .env
export
endif

.PHONY: all setup load build docs cache notebooks report dashboard incremental-check ci-fixture ci clean help

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

all: setup load build docs cache notebooks report  ## Run the full pipeline end to end

setup:  ## Create the virtualenv and install dbt packages
	$(UV) sync
	$(DBT) deps $(DBT_FLAGS)

load:  ## EL: load the raw CSVs into DuckDB (schema raw)
	$(UV) run python ingestion/load_raw.py

build:  ## dbt build (seeds, models, data tests, unit tests)
	$(DBT) build $(DBT_FLAGS)

docs:  ## Generate dbt docs (target/index.html and a single-file static_index.html)
	$(DBT) docs generate $(DBT_FLAGS) --static

clean:  ## Remove generated warehouse, cache and dbt artifacts
	rm -rf data/warehouse data/cache dbt/target dbt/logs
