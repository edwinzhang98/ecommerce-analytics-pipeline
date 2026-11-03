"""Read the cache written by `make cache` (parquet + JSON).

Shared by the Streamlit app, the HTML report and the notebooks, so all three show the same numbers.
`cache_connection()` returns an in-memory DuckDB whose `marts` schema is a set of views over the
cached parquet files: the SQL in analyses/ runs unchanged against it (and against the warehouse).
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

from olist_analytics.config import load_settings


def cache_dir() -> Path:
    return load_settings().cache_dir


def cache_ready(path: Path | None = None) -> bool:
    path = path or cache_dir()
    return (path / "project_stats.json").exists() and (path / "marts" / "fct_orders.parquet").exists()


def cache_connection(path: Path | None = None) -> duckdb.DuckDBPyConnection:
    path = path or cache_dir()
    con = duckdb.connect(":memory:")
    con.execute("create schema marts")
    for parquet in sorted((path / "marts").glob("*.parquet")):
        con.execute(f"create view marts.{parquet.stem} as select * from read_parquet('{parquet.as_posix()}')")
    return con


def read_table(name: str, path: Path | None = None) -> pd.DataFrame:
    """A cache table by name: dq_issues, tests, lineage_nodes, lineage_edges, load_audit."""
    return pd.read_parquet((path or cache_dir()) / f"{name}.parquet")


def read_sql_result(file_stem: str, result: str, path: Path | None = None) -> pd.DataFrame:
    """A result set of one of the sql/ files, e.g. ('05_time_ranges_and_coverage', 'monthly_coverage')."""
    return pd.read_parquet((path or cache_dir()) / "sql" / f"{file_stem}__{result}.parquet")


def read_json(name: str, path: Path | None = None) -> dict:
    target = (path or cache_dir()) / name
    return json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
