"""Shared building blocks for every page: data access (cache only), page header, chart and table
helpers, and the "How to read this" box. Pages read the parquet cache written by `make cache`;
they never touch the warehouse, so the app starts fast and never recomputes the pipeline."""
from __future__ import annotations

import duckdb
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from olist_analytics import data

PLOTLY_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]}


@st.cache_resource(show_spinner=False)
def _base_connection() -> duckdb.DuckDBPyConnection:
    return data.cache_connection()


def con() -> duckdb.DuckDBPyConnection:
    """A cursor on the shared in-memory DuckDB whose `marts` views read the cached parquet."""
    return _base_connection().cursor()


@st.cache_data(show_spinner=False)
def table(name: str) -> pd.DataFrame:
    return data.read_table(name)


@st.cache_data(show_spinner=False)
def sql_result(file_stem: str, result: str) -> pd.DataFrame:
    return data.read_sql_result(file_stem, result)


@st.cache_data(show_spinner=False)
def stats() -> dict:
    return data.read_json("project_stats.json")


@st.cache_data(show_spinner=False)
def json_file(name: str) -> dict:
    return data.read_json(name)


def require_cache() -> None:
    if not data.cache_ready():
        st.error("The data cache is missing. Run `make all` (or `make build docs cache`) first, then reload.")
        st.stop()


def header(title: str, question: str) -> None:
    """Page title + the one sentence this page answers."""
    st.title(title)
    st.markdown(
        f"<div style='font-size:1.08rem;color:#52514e;border-left:3px solid #2a78d6;"
        f"padding:2px 0 2px 12px;margin:-6px 0 18px 0'>{question}</div>",
        unsafe_allow_html=True,
    )


def chart(fig: go.Figure, key: str | None = None) -> None:
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, key=key)


def table_view(df: pd.DataFrame, label: str = "Table view", **kwargs) -> None:
    """Every chart has a table twin (accessibility, and exact numbers for the reader)."""
    with st.expander(label):
        st.dataframe(df, use_container_width=True, hide_index=True, **kwargs)


def how_to_read(markdown: str) -> None:
    st.divider()
    with st.expander("How to read this", expanded=False):
        st.markdown(markdown)


def fmt_int(x) -> str:
    return f"{int(round(float(x))):,}"


def md_safe(text: str) -> str:
    """Escape dollar signs so Streamlit markdown does not render "R$1 ... R$2" as LaTeX."""
    return text.replace("$", "\\$")


def fmt_brl(x) -> str:
    x = float(x)
    if abs(x) >= 1e6:
        return f"R${x / 1e6:,.2f}M"
    if abs(x) >= 1e3:
        return f"R${x / 1e3:,.1f}K"
    return f"R${x:,.0f}"
