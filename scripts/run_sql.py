"""Run a standalone SQL file from sql/ or analyses/ against the DuckDB warehouse and print every result.

Usage:
    uv run python scripts/run_sql.py analyses/q1_delivery_vs_reviews_by_state.sql
    uv run python scripts/run_sql.py analyses/q2_repeat_purchase.sql --var repeat_window_days=90
The warehouse is opened read-only. Alternatively paste the file into any DuckDB client.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
from olist_analytics.config import load_settings  # noqa: E402
from olist_analytics.sqlfile import run_sql_file  # noqa: E402


def parse_var(text: str):
    name, _, value = text.partition("=")
    for cast in (int, float):
        try:
            return name, cast(value)
        except ValueError:
            pass
    return name, {"true": True, "false": False}.get(value.lower(), value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sql_file", type=Path)
    parser.add_argument("--var", action="append", default=[], help="Override a `set variable` default: name=value")
    parser.add_argument("--max-rows", type=int, default=40)
    args = parser.parse_args()
    con = duckdb.connect(str(load_settings().duckdb_path), read_only=True)
    results = run_sql_file(con, args.sql_file, dict(parse_var(v) for v in args.var))
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)
    for name, df in results.items():
        print(f"\n== {name} ({0 if df is None else len(df)} rows)")
        if df is not None:
            print(df.head(args.max_rows).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
