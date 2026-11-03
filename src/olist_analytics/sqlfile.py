"""Run the repo's standalone SQL files from Python.

Convention used by every file in `sql/` and `analyses/`:
  * an optional preamble (e.g. `set variable min_orders = 30;` defaults, temp macros)
  * one or more result sections, each introduced by a line `-- result: <name>`
A file runs as-is in DuckDB; Python callers can override the defaults with `variables=`
(the app's sliders do exactly that), and get one DataFrame per named result.
"""
from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd

_RESULT_MARKER = re.compile(r"^--\s*result:\s*(\w+)\s*$", re.MULTILINE)


def split_sections(sql: str) -> tuple[str, dict[str, str]]:
    """Return (preamble, {result_name: sql})."""
    parts = _RESULT_MARKER.split(sql)
    preamble, sections = parts[0], {}
    for name, body in zip(parts[1::2], parts[2::2]):
        sections[name] = body
    return preamble, sections


def _execute_all(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame | None:
    """Execute every statement in `sql`; return the result of the last one that yields rows."""
    result = None
    for statement in duckdb.extract_statements(sql):
        rel = con.execute(statement.query)
        if statement.type == duckdb.StatementType.SELECT:
            result = rel.df()
    return result


def _sql_literal(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def run_sql_file(con: duckdb.DuckDBPyConnection, path: str | Path, variables: dict | None = None) -> dict[str, pd.DataFrame]:
    sql = Path(path).read_text(encoding="utf-8")
    preamble, sections = split_sections(sql)
    if preamble.strip():
        _execute_all(con, preamble)
    for name, value in (variables or {}).items():
        con.execute(f"set variable {name} = {_sql_literal(value)}")
    if not sections:  # a plain file: return the last result under the file's stem
        return {Path(path).stem: _execute_all(con, sql)}
    return {name: _execute_all(con, body) for name, body in sections.items()}
