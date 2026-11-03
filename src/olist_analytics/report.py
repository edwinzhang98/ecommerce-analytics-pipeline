"""Build reports/report.html: one self-contained file (plotly.js and images embedded) that tells the whole
project without running any code. It uses the same chart functions, SQL and default parameters as the
Streamlit app, so the figures match the app's.

    uv run python -m olist_analytics.report        (make report)
"""
from __future__ import annotations

import base64
import datetime as dt
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from jinja2 import Environment, FileSystemLoader, select_autoescape
from plotly.offline import get_plotlyjs

from olist_analytics import analysis, charts, data
from olist_analytics.config import REPO_ROOT, load_settings

TEMPLATES = Path(__file__).parent / "templates"
OUT = REPO_ROOT / "reports" / "report.html"
PLOTLY_CONFIG = {"displaylogo": False, "responsive": True}


def fig_html(fig: go.Figure) -> str:
    return fig.to_html(full_html=False, include_plotlyjs=False, config=PLOTLY_CONFIG)


def table_html(df: pd.DataFrame, max_rows: int = 40, formats: dict | None = None) -> str:
    view = df.head(max_rows).copy()
    for col, fmt in (formats or {}).items():
        if col in view:
            view[col] = view[col].map(lambda v, f=fmt: f.format(v) if pd.notna(v) else "")
    return view.to_html(index=False, classes="data", border=0, na_rep="", escape=True)


def image_data_uri(path: Path) -> str | None:
    if not path.exists():
        return None
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except Exception:  # not a git checkout
        return "n/a"


def build() -> Path:
    settings = load_settings()
    if not data.cache_ready(settings.cache_dir):
        raise SystemExit("Cache missing: run `make build docs cache` first.")
    con = data.cache_connection(settings.cache_dir)
    stats = data.read_json("project_stats.json")
    inc = data.read_json("incremental_check.json")

    # ---------------------------------------------------------------- data for every section
    three = data.read_sql_result("01_three_analysts_on_raw", "order_counts")
    a = three.set_index("analyst")
    q0 = analysis.q0_order_count_reconciliation(con)
    named = q0["named_order_metrics"].set_index("metric")["orders"]
    issues = data.read_table("dq_issues")
    tests = data.read_table("tests")
    audit = data.read_sql_result("01_row_counts_vs_load_audit", "row_counts")
    coverage = data.read_sql_result("05_time_ranges_and_coverage", "monthly_coverage")
    nulls = data.read_sql_result("03_null_profile", "null_profile")
    lifecycle = data.read_sql_result("08_lifecycle_consistency", "lifecycle_anomalies")
    curve = analysis.payment_mismatch_curve(con)
    at1 = analysis.payment_mismatch_at(con, 1.0)
    q1 = analysis.q1_delivery_vs_reviews(con)
    q2 = analysis.q2_repeat_purchase(con)
    q3 = analysis.q3_seller_performance(con)
    points = analysis.seller_points(con, analysis.DEFAULTS["q3"]["min_seller_orders"])
    months = analysis.available_months(con)
    kpis = analysis.dashboard_kpis(con, months[0], months[-1])
    monthly = analysis.dashboard_monthly(con, months[0], months[-1])
    cats = analysis.dashboard_categories(con, months[0], months[-1])
    regions = analysis.dashboard_regions(con)
    nodes, edges = data.read_table("lineage_nodes"), data.read_table("lineage_edges")

    lv = q1["late_vs_on_time"].set_index("delivery_outcome")
    corr = q1["state_correlation"].iloc[0]
    defs = q2["definition_sensitivity"]
    official = defs[defs["definition"].str.contains("official")].iloc[0]
    tiers = q3["gmv_concentration"].set_index("top_pct_of_sellers")["gmv_share_pct"]
    hv = q3["handover_vs_outcome"].set_index("handover")["late_delivery_rate_pct"]
    hv_late = hv[hv.index.str.contains("late")].iloc[0]
    hv_ok = hv[hv.index.str.contains("on time")].iloc[0]
    quad = q3["seller_quadrants"].set_index("quadrant")
    risk = quad[quad.index.str.startswith("1.")].iloc[0]
    timing = analysis.repeat_timing_full_year(con)
    clear = analysis.clear_flagged_sellers(con, **analysis.DEFAULTS["q3"])
    hv_tbl = q3["handover_vs_outcome"]
    late_after_ok_handover = (hv_tbl.loc[hv_tbl["handover"].str.contains("on time"), "late_deliveries"].sum()
                              / hv_tbl["late_deliveries"].sum())
    known = tests[tests["category"] == "known-issue baseline"][
        ["dq_issue", "test", "failing_rows", "warn_if", "error_if", "status"]].sort_values(["dq_issue", "test"])

    numbers = {
        "placed": int(named["placed orders"]), "net": int(named["net orders (official KPI)"]),
        "delivered": int(named["delivered orders"]),
        "fanout_rows": int(a.loc["A", "orders_reported"]),
        "fanout_revenue": float(a.loc["A", "revenue_reported_brl"]), "paid": float(a.loc["B", "revenue_reported_brl"]),
        "net_gmv": float(q0["query_paths"]["net_gmv_brl"].iloc[0]),
        "bad_late": lv.loc["late", "bad_review_rate_pct"], "bad_ok": lv.loc["on time", "bad_review_rate_pct"],
        "bad_late_lo": lv.loc["late", "ci_low_pct"], "bad_late_hi": lv.loc["late", "ci_high_pct"],
        "bad_ok_lo": lv.loc["on time", "ci_low_pct"], "bad_ok_hi": lv.loc["on time", "ci_high_pct"],
        "corr": corr["corr_late_rate_vs_bad_review_rate"], "r2": corr["r_squared_late_rate"],
        "states_n": int(corr["states_included"]),
        "worst_states": ", ".join(q1["by_state"].sort_values("late_rate_pct", ascending=False).head(3)["delivery_state"]),
        "excess_states": ", ".join(q1["by_state"].loc[q1["by_state"]["ci_low_pct"] > q1["by_state"]["expected_bad_review_rate_pct"],
                                                    "delivery_state"]),
        "repeat": official["repeat_rate_pct"], "repeat_orders": defs["repeat_rate_pct"].max(),
        "median_second": q2["time_to_second_purchase"]["median_days_all_repeaters"].iloc[0],
        "top10": tiers.loc[10], "top5": tiers.loc[5], "top20": tiers.loc[20],
        "hv_late": hv_late, "hv_ok": hv_ok, "hv_ratio": hv_late / hv_ok,
        "risk_sellers": int(risk["sellers"]), "risk_share": risk["share_of_marketplace_gmv_pct"],
        "median_full_year": timing["median_days"], "clear_sellers": clear["clearly_above_both"],
        "late_after_ok_handover": 100 * late_after_ok_handover,
        "mismatch": int(at1["mismatched_orders"]), "mismatch_base": int(at1["orders_with_items_and_payments"]),
        "mismatch_installments": int(at1["overpaid_in_installments"]),
    }

    figures = {
        "three": charts.three_analysts(three), "paths": charts.query_paths(q0["query_paths"]),
        "issues": charts.issues_by_class(issues), "coverage": charts.monthly_coverage(coverage),
        "nulls": charts.null_profile(nulls), "lifecycle": charts.lifecycle_anomalies(lifecycle),
        "payments": charts.payment_mismatch_curve(curve, 1.0, at1),
        "lineage": charts.lineage_graph(nodes, edges, "fct_orders"),
        "tests_cat": charts.tests_by_category(tests), "tests_layer": charts.tests_by_layer(tests),
        "q1a": charts.q1_late_vs_on_time(q1["late_vs_on_time"]), "q1b": charts.q1_by_delay(q1["by_delay"]),
        "q1c": charts.q1_states(q1["by_state"], q1["late_vs_on_time"]),
        "q2a": charts.q2_definitions(defs), "q2b": charts.q2_time_to_second(q2["time_to_second_purchase"]),
        "q2c": charts.q2_cohorts(q2["cohort_repeat"], analysis.DEFAULTS["q2"]["repeat_window_days"]),
        "q2d": charts.q2_first_experience(q2["repeat_by_first_experience"], analysis.DEFAULTS["q2"]["repeat_window_days"]),
        "q3a": charts.q3_pareto(q3["pareto_curve"], q3["gmv_concentration"]), "q3b": charts.q3_handover(q3["handover_vs_outcome"]),
        "q3c": charts.q3_quadrants(points, analysis.DEFAULTS["q3"]["late_handover_threshold_pct"],
                                   analysis.DEFAULTS["q3"]["bad_review_threshold_pct"]),
        "m_orders": charts.monthly_bars(monthly, "net_orders", "Net orders per month (orders)", "net orders"),
        "m_gmv": charts.monthly_bars(monthly, "net_gmv_brl", "Net GMV per month (BRL)", "net GMV (BRL)", money=True),
        "m_late": charts.monthly_line(monthly, "late_rate_pct", "Late deliveries per month (% of delivered)", "late (%)", "%"),
        "m_days": charts.monthly_line(monthly, "avg_delivery_days", "Average delivery time per month (days)", "days"),
        "cats": charts.horizontal_bars(cats, "category", "net_gmv_brl", "Top categories by net GMV (BRL)", "net GMV (BRL)",
                                       money=True, subtitle=f"Top 3: {', '.join(cats['category'].head(3))}."),
        "regions": charts.region_split(regions),
    }

    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
    env.filters["int"] = lambda v: f"{int(round(float(v))):,}"
    env.filters["pct"] = lambda v, d=1: charts.pct(v, d)
    env.filters["brl"] = lambda v: charts.fmt_brl(v, 2)
    html = env.get_template("report.html.j2").render(
        generated=dt.date.today().isoformat(), commit=git_commit(), stats=stats, inc=inc, n=numbers, kpis=kpis,
        months=(months[0], months[-1]),
        plotly_js=get_plotlyjs(),
        figs={k: fig_html(v) for k, v in figures.items()},
        architecture_svg=charts.architecture_svg(stats),
        star_svg=charts.star_schema_svg(stats.get("mart_rows")),
        lineage_png=image_data_uri(REPO_ROOT / "docs" / "images" / "dbt_lineage.png"),
        tables={
            "audit": table_html(audit[["table_name", "physical_data_lines", "parsed_rows", "expected_rows", "reconciles"]],
                                formats={"physical_data_lines": "{:,}", "parsed_rows": "{:,}", "expected_rows": "{:,.0f}"}),
            "issues": table_html(issues[["id", "class", "table", "title", "affected", "unit", "handling"]],
                                 formats={"affected": "{:,}"}),
            "known": table_html(known, formats={"failing_rows": "{:,.0f}"}),
            "named": table_html(q0["named_order_metrics"], formats={"orders": "{:,}"}),
            "states": table_html(q1["by_state"][["delivery_state", "delivery_region", "reviewed_deliveries", "avg_delivery_days",
                                                 "late_rate_pct", "bad_review_rate_pct", "expected_bad_review_rate_pct",
                                                 "excess_vs_expected_pp"]]),
            "quadrants": table_html(q3["seller_quadrants"], formats={"gmv_brl": "R${:,.0f}"}),
            "watchlist": table_html(q3["watchlist"].head(10), formats={"gmv_brl": "R${:,.0f}"}),
        },
    )
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    return OUT


def main() -> int:
    path = build()
    print(f"wrote {path.relative_to(REPO_ROOT)} ({path.stat().st_size / 1e6:.1f} MB)")
    render = REPO_ROOT / "scripts" / "render_docs_tables.py"
    subprocess.run([sys.executable, str(render)], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
