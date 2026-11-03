"""Plotly figures shared by the Streamlit app, the HTML report and the notebooks.

One theme, one palette (validated for colour-vision deficiency), thin marks, one y-axis per
chart, and a subtitle that states the chart's conclusion computed from its own data. Every
function takes DataFrames from olist_analytics.analysis / .data and returns a go.Figure, so the
app and the report draw identical charts.
"""
from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go

# ----------------------------------------------------------------------------- theme
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
DEEMPH = "#c3c2b7"          # de-emphasised marks ("the rest")
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"   # categorical slots 1-3 (validated)
SERIES = [BLUE, ORANGE, AQUA, "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
BAND = "rgba(42,120,214,0.12)"   # 10-12% wash of slot 1 for interval bands
FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'

TEMPLATE = go.layout.Template(
    layout=go.Layout(
        font=dict(family=FONT, color=INK_2, size=13),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        colorway=SERIES,
        title=dict(font=dict(size=16, color=INK), x=0, xanchor="left", y=0.97, yanchor="top"),
        margin=dict(l=8, r=16, t=84, b=8),
        xaxis=dict(gridcolor=GRID, linecolor=AXIS, zeroline=False, ticks="", showline=True,
                   title=dict(font=dict(color=INK_2, size=12)), automargin=True),
        yaxis=dict(gridcolor=GRID, linecolor=AXIS, zeroline=False, ticks="", showline=False,
                   title=dict(font=dict(color=INK_2, size=12)), automargin=True),
        legend=dict(orientation="h", x=0, xanchor="left", y=1.0, yanchor="bottom",
                    font=dict(color=INK_2), bgcolor="rgba(0,0,0,0)", title=dict(text="")),
        hoverlabel=dict(bgcolor="white", bordercolor=GRID, font=dict(family=FONT, color=INK, size=12)),
        bargap=0.45,
        separators=".,",
    )
)


def _finish(fig: go.Figure, title: str, subtitle: str | None = None, height: int = 380,
            legend: bool | None = None) -> go.Figure:
    """Title (with unit) + one-sentence conclusion as subtitle, consistent sizing."""
    fig.update_layout(
        template=TEMPLATE,
        height=height,
        title=dict(text=title, subtitle=dict(text=subtitle or "", font=dict(color=INK_2, size=13))),
    )
    if legend is not None:
        fig.update_layout(showlegend=legend)
    if legend:
        fig.update_layout(margin=dict(t=110))
        fig.update_layout(legend=dict(y=1.02))
    return fig


def _bar_style(fig: go.Figure) -> None:
    fig.update_traces(selector=dict(type="bar"), marker_cornerradius=4, marker_line_width=0)


def pct(x, digits: int = 1) -> str:
    """Percent with half-up rounding (9.25 -> 9.3), so charts and docs agree."""
    from decimal import ROUND_HALF_UP, Decimal
    q = Decimal(1).scaleb(-digits)
    return f"{Decimal(str(float(x))).quantize(q, rounding=ROUND_HALF_UP)}%"


def bar_width(n_categories: int, plot_px: int = 1000, target_px: int = 26) -> float:
    """Category-axis bar width as a fraction of the slot, so bars stay thin (~26px) at any count."""
    return max(0.08, min(0.6, target_px * max(n_categories, 1) / plot_px))


LOG_TICKS = dict(tickvals=[0.01, 0.1, 1, 10, 100], ticktext=["0.01", "0.1", "1", "10", "100"])


def fmt_int(n) -> str:
    return f"{int(round(float(n))):,}"


def fmt_brl(x, digits: int = 1) -> str:
    x = float(x)
    for div, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(x) >= div:
            return f"R${x / div:,.{digits}f}{suffix}"
    return f"R${x:,.0f}"


# ----------------------------------------------------------------------------- overview
def three_analysts(df: pd.DataFrame) -> go.Figure:
    """sql/metrics/01_three_analysts_on_raw.sql -> order_counts"""
    d = df.copy()
    d["label"] = d["analyst"].map(lambda a: f"Analyst {a}" if len(a) == 1 else "Agreed definition")
    d = d.iloc[::-1]
    colors = [BLUE if a == "Official" else DEEMPH for a in d["analyst"]]
    fig = go.Figure(go.Bar(
        y=d["label"], x=d["orders_reported"], orientation="h", marker_color=colors,
        text=[fmt_int(v) for v in d["orders_reported"]], textposition="outside", cliponaxis=False,
        customdata=d[["query", "why_it_differs"]], width=0.5,
        hovertemplate="<b>%{y}</b><br>%{customdata[0]}<br>%{x:,} orders<br>%{customdata[1]}<extra></extra>",
    ))
    _bar_style(fig)
    lo, hi = d["orders_reported"].min(), d["orders_reported"].max()
    fig.update_xaxes(title="orders reported", range=[0, hi * 1.15], tickformat=",")
    return _finish(fig, "“How many orders?” answered four ways on the raw tables (orders)",
                   f"Same data, a {fmt_int(hi - lo)}-order spread: joins fan out and each analyst filters differently.",
                   height=320, legend=False)


def query_paths(df: pd.DataFrame) -> go.Figure:
    """analyses/q0_order_count_reconciliation.sql -> query_paths"""
    d = df.iloc[::-1]
    n_distinct = d["net_orders"].nunique()
    fig = go.Figure(go.Bar(
        y=d["analyst"], x=d["net_orders"], orientation="h", marker_color=BLUE, width=0.5,
        text=[fmt_int(v) for v in d["net_orders"]], textposition="outside", cliponaxis=False,
        customdata=d[["query_path"]],
        hovertemplate="<b>%{y}</b><br>%{customdata[0]}<br>%{x:,} net orders<extra></extra>",
    ))
    _bar_style(fig)
    fig.update_xaxes(title="net orders", range=[0, d["net_orders"].max() * 1.15], tickformat=",")
    verdict = (f"All {len(d)} query paths return the same {fmt_int(d['net_orders'].iloc[0])} net orders."
               if n_distinct == 1 else f"Paths disagree ({n_distinct} different answers).")
    return _finish(fig, "Through the marts, every query path gives one answer (net orders)", verdict,
                   height=320, legend=False)


def architecture_svg(stats: dict) -> str:
    """Static architecture diagram (inline SVG) with live counts from project_stats.json."""
    layers = stats.get("models_by_layer", {})
    boxes = [
        ("9 raw CSVs", "Kaggle Olist release", "outside the repo"),
        ("Python EL", "load_raw.py", "raw schema + load audit"),
        ("staging", f"{layers.get('staging', 9)} views", "rename · cast · clean"),
        ("intermediate", f"{layers.get('intermediate', 7)} views", "roll up to order grain"),
        ("marts", f"{layers.get('marts (core)', 6)} star + {layers.get('marts (business)', 2)} wide",
         "contracts enforced"),
        ("consumers", "app · report · SQL", "read marts only"),
    ]
    w, h, gap, x0, y0 = 150, 86, 28, 16, 40
    parts = []
    for i, (head, line1, line2) in enumerate(boxes):
        x = x0 + i * (w + gap)
        accent = BLUE if head == "marts" else AXIS
        fill = "#eef4fc" if head == "marts" else "#ffffff"
        parts.append(
            f'<rect x="{x}" y="{y0}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{accent}" stroke-width="1.5"/>'
            f'<text x="{x + w / 2}" y="{y0 + 28}" text-anchor="middle" font-size="15" font-weight="600" fill="{INK}">{head}</text>'
            f'<text x="{x + w / 2}" y="{y0 + 50}" text-anchor="middle" font-size="12.5" fill="{INK_2}">{line1}</text>'
            f'<text x="{x + w / 2}" y="{y0 + 68}" text-anchor="middle" font-size="12" fill="{MUTED}">{line2}</text>'
        )
        if i < len(boxes) - 1:
            ax = x + w + 4
            parts.append(f'<line x1="{ax}" y1="{y0 + h / 2}" x2="{ax + gap - 10}" y2="{y0 + h / 2}" '
                         f'stroke="{MUTED}" stroke-width="1.5" marker-end="url(#arrow)"/>')
    span_x, span_w = x0 + 2 * (w + gap), 3 * w + 2 * gap
    tests = stats.get("data_tests", 0) + stats.get("unit_tests", 0)
    parts.append(
        f'<rect x="{span_x}" y="{y0 + h + 22}" width="{span_w}" height="44" rx="8" fill="#ffffff" '
        f'stroke="{AXIS}" stroke-width="1.2"/>'
        f'<text x="{span_x + span_w / 2}" y="{y0 + h + 49}" text-anchor="middle" font-size="12.5" fill="{INK_2}">'
        f'dbt build: {tests} tests · {stats.get("known_issue_tests", 0)} known-issue baselines · docs + lineage · '
        f'semantic layer · CI on every PR</text>'
    )
    parts.append(
        f'<text x="{x0}" y="{y0 - 16}" font-size="12.5" fill="{MUTED}">DuckDB warehouse · dbt Core '
        f'{stats.get("dbt_version", "")} · orchestrated by make all</text>'
    )
    total_w = x0 * 2 + len(boxes) * w + (len(boxes) - 1) * gap
    return (
        f'<svg viewBox="0 0 {total_w} {y0 + h + 80}" width="100%" role="img" '
        f'aria-label="Pipeline: raw CSVs, Python EL, dbt staging, intermediate, marts, consumers" '
        f'xmlns="http://www.w3.org/2000/svg" style="font-family:{FONT.replace(chr(34), chr(39))};max-width:1100px">'
        f'<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{MUTED}"/></marker></defs>'
        + "".join(parts) + "</svg>"
    )


# ----------------------------------------------------------------------------- raw data issues
def issues_by_class(issues: pd.DataFrame) -> go.Figure:
    d = issues.groupby("class", sort=False).size().reset_index(name="issues").iloc[::-1]
    fig = go.Figure(go.Bar(y=d["class"], x=d["issues"], orientation="h", marker_color=BLUE, width=0.5,
                           text=d["issues"], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x} issues<extra></extra>"))
    _bar_style(fig)
    fig.update_xaxes(title="issues found", dtick=1, range=[0, d["issues"].max() + 1])
    return _finish(fig, "Raw-data issues found, by class (count of issues)",
                   f"{len(issues)} issues in {issues['class'].nunique()} classes; every one is handled, flagged or tested.",
                   height=360, legend=False)


def monthly_coverage(df: pd.DataFrame) -> go.Figure:
    """sql/data_quality/05_time_ranges_and_coverage.sql -> monthly_coverage"""
    colors = [DEEMPH if sparse else BLUE for sparse in df["is_sparse_month"]]
    fig = go.Figure(go.Bar(x=df["year_month"], y=df["orders_placed"], marker_color=colors, width=bar_width(len(df)),
                           hovertemplate="%{x}: %{y:,} orders placed<extra></extra>"))
    _bar_style(fig)
    fig.update_yaxes(title="orders placed", tickformat="~s")
    fig.update_xaxes(type="category", tickangle=-45)
    sparse = df.loc[df["is_sparse_month"], "year_month"].tolist()
    return _finish(fig, "Orders per purchase month (orders placed)",
                   f"Gray months have fewer than 100 orders ({', '.join(sparse)}): trends use 2017-01 to 2018-08 only.",
                   height=360, legend=False)


def null_profile(df: pd.DataFrame) -> go.Figure:
    """sql/data_quality/03_null_profile.sql -> null_profile"""
    d = df.copy()
    d["column"] = d["table_name"] + "." + d["column_name"]
    d = d.iloc[::-1]
    fig = go.Figure(go.Bar(y=d["column"], x=d["null_pct"], orientation="h", marker_color=BLUE, width=0.55,
                           text=[f"{p:.2f}% ({fmt_int(n)})" for p, n in zip(d["null_pct"], d["null_count"])],
                           textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x:.2f}% null<extra></extra>"))
    _bar_style(fig)
    fig.update_xaxes(title="share of rows that are null (%, log scale)", type="log", range=[-2.3, 2.6], **LOG_TICKS)
    return _finish(fig, "Missing values in the raw tables (% of rows, log scale)",
                   "Review comments are optional (58-88% empty); the rest are small, specific gaps.",
                   height=440, legend=False)


def lifecycle_anomalies(df: pd.DataFrame) -> go.Figure:
    """sql/data_quality/08_lifecycle_consistency.sql -> lifecycle_anomalies"""
    d = df[df["orders"] > 0].sort_values("orders")
    fig = go.Figure(go.Bar(y=d["anomaly"], x=d["orders"], orientation="h", marker_color=BLUE, width=0.55,
                           text=[fmt_int(v) for v in d["orders"]], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x:,} orders<extra></extra>"))
    _bar_style(fig)
    fig.update_xaxes(title="orders", range=[0, d["orders"].max() * 1.18], tickformat=",")
    return _finish(fig, "Order timestamps that contradict the lifecycle (orders)",
                   "Mostly carrier pickups logged before payment approval: flagged in fct_orders, never dropped.",
                   height=380, legend=False)


def payment_mismatch_curve(curve: pd.DataFrame, tolerance: float, at: dict) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=curve["tolerance_brl"], y=curve["mismatched_orders"], mode="lines+markers",
                             line=dict(color=BLUE, width=2), marker=dict(size=8, line=dict(color=SURFACE, width=2)),
                             name="orders off by more than the tolerance",
                             hovertemplate="> R$%{x}: %{y:,} orders<extra></extra>"))
    fig.add_trace(go.Scatter(x=[tolerance], y=[at["mismatched_orders"]], mode="markers+text",
                             marker=dict(size=13, color=ORANGE, line=dict(color=SURFACE, width=2)),
                             text=[f"  {fmt_int(at['mismatched_orders'])} at R${tolerance:g}"], textposition="middle right",
                             textfont=dict(color=INK), name="selected tolerance", hoverinfo="skip"))
    fig.update_xaxes(title="tolerance (BRL, log scale)", type="log", **LOG_TICKS)
    fig.update_yaxes(title="orders where payments ≠ items + freight", tickformat=",", rangemode="tozero")
    share = 100 * at["mismatched_orders"] / max(at["orders_with_items_and_payments"], 1)
    return _finish(fig, "Orders whose payments differ from items + freight (orders)",
                   f"At R${tolerance:g}: {fmt_int(at['mismatched_orders'])} orders ({share:.2f}%); "
                   f"{fmt_int(at['overpaid_in_installments'])} are card payments in installments (interest).",
                   height=380, legend=False)


# ----------------------------------------------------------------------------- lineage & tests
LAYER_ORDER = ["raw (source)", "seed", "snapshot", "staging", "intermediate", "marts (core)",
               "marts (business)", "exposure"]


def _wrap_name(name: str, width: int = 24) -> str:
    if len(name) <= width:
        return name
    if "__" in name:
        head, tail = name.split("__", 1)
        return head + "__<br>" + _wrap_name(tail, width)
    cut = name.rfind("_", 0, width)
    return name[:cut] + "<br>" + _wrap_name(name[cut:], width) if cut > 0 else name


def lineage_graph(nodes: pd.DataFrame, edges: pd.DataFrame, selected: str | None = None) -> go.Figure:
    """Dependency explorer from the dbt manifest.

    With `selected`: the model plus everything upstream and downstream of it, fully labelled.
    Without: the whole DAG, labelled only at the marts and exposures (hover for the rest)."""
    col_of = {"raw (source)": 0, "seed": 0, "snapshot": 0, "staging": 1, "intermediate": 2,
              "marts (core)": 3, "marts (business)": 4, "exposure": 5}
    n = nodes[nodes["layer"].isin(col_of)].copy()
    n["col"] = n["layer"].map(col_of)
    parents = edges.groupby("child")["parent"].apply(list).to_dict()
    children = edges.groupby("parent")["child"].apply(list).to_dict()

    sel_uid, up, down = None, set(), set()
    if selected:
        match = n.loc[n["name"] == selected, "unique_id"]
        sel_uid = match.iloc[0] if len(match) else None
    if sel_uid:
        for graph, found in ((parents, up), (children, down)):
            stack = [sel_uid]
            while stack:
                for nxt in graph.get(stack.pop(), []):
                    if nxt not in found:
                        found.add(nxt); stack.append(nxt)
        n = n[n["unique_id"].isin(up | down | {sel_uid})].copy()

    # order nodes within each column by the average position of their parents (fewer crossings)
    rank: dict[str, float] = {}
    for col in sorted(n["col"].unique()):
        layer_nodes = n[n["col"] == col].copy()
        def bary(uid: str) -> float:
            ps = [rank[p] for p in parents.get(uid, []) if p in rank]
            return sum(ps) / len(ps) if ps else float("inf")
        layer_nodes["bary"] = layer_nodes["unique_id"].map(bary)
        layer_nodes = layer_nodes.sort_values(["bary", "layer", "name"])
        for i, uid in enumerate(layer_nodes["unique_id"]):
            rank[uid] = i
    n["row"] = n["unique_id"].map(rank)
    n["y"] = -(n["row"] - n.groupby("col")["row"].transform("max") / 2)
    pos = {r.unique_id: (r.col, r.y) for r in n.itertuples()}

    fig = go.Figure()
    xs, ys = [], []
    for e in edges.itertuples():
        if e.parent in pos and e.child in pos:
            (x1, y1), (x2, y2) = pos[e.parent], pos[e.child]
            xs += [x1, x2, None]
            ys += [y1, y2, None]
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", hoverinfo="skip", showlegend=False,
                             line=dict(color=BLUE if sel_uid else GRID, width=1.2 if sel_uid else 1)))
    if sel_uid:
        labels = [_wrap_name(x) for x in n["name"]]
        colors = [ORANGE if u == sel_uid else (BLUE if u in up else AQUA) for u in n["unique_id"]]
    else:
        labels = [x if layer in ("marts (core)", "marts (business)", "exposure") else ""
                  for x, layer in zip(n["name"], n["layer"])]
        colors = [BLUE] * len(n)
    fig.add_trace(go.Scatter(
        x=n["col"], y=n["y"], mode="markers+text", text=labels, textposition="middle right",
        textfont=dict(size=11, color=INK_2), showlegend=False, hovertext=n["name"],
        marker=dict(size=11, color=colors, line=dict(color=SURFACE, width=2)),
        customdata=n[["layer", "materialized", "tests", "columns"]],
        hovertemplate="<b>%{hovertext}</b><br>%{customdata[0]} · %{customdata[1]}<br>"
                      "%{customdata[3]} columns · %{customdata[2]} tests<extra></extra>",
    ))
    heads = {0: "sources · seeds", 1: "staging", 2: "intermediate", 3: "marts: core", 4: "marts: business", 5: "exposures"}
    top = n["y"].max() + 1.2
    for col in sorted(n["col"].unique()):
        fig.add_annotation(x=col, y=top, text=f"<b>{heads[col]}</b>", showarrow=False, xanchor="left",
                           font=dict(color=INK, size=12))
    fig.update_xaxes(visible=False, range=[-0.15, n["col"].max() + 0.95])
    fig.update_yaxes(visible=False, range=[n["y"].min() - 1, top + 0.8])
    tallest = int(n.groupby("col").size().max())
    if sel_uid:
        sub = (f"{selected} (orange) depends on {len(up)} upstream nodes (blue) and feeds {len(down)} "
               "downstream nodes (green).")
    else:
        sub = "Raw tables are read only by staging; analysts and the app read only the marts (labelled)."
    row_px = 48 if sel_uid else 34
    return _finish(fig, "Model lineage from the dbt manifest", sub, height=max(380, row_px * tallest + 170), legend=False)


def tests_by_category(tests: pd.DataFrame) -> go.Figure:
    d = tests.groupby("category").size().sort_values().reset_index(name="tests")
    fig = go.Figure(go.Bar(y=d["category"], x=d["tests"], orientation="h", marker_color=BLUE, width=0.55,
                           text=d["tests"], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x} tests<extra></extra>"))
    _bar_style(fig)
    fig.update_xaxes(title="tests", range=[0, d["tests"].max() * 1.15])
    passed = int((tests["status"] == "pass").sum())
    return _finish(fig, "What the tests check (number of tests)",
                   f"{passed} of {len(tests)} tests pass in the last dbt build.", height=400, legend=False)


def tests_by_layer(tests: pd.DataFrame) -> go.Figure:
    order = ["raw (source)", "seed", "snapshot", "staging", "intermediate", "marts (core)", "marts (business)",
             "cross-model"]
    d = tests.assign(layer=pd.Categorical(tests["layer"], order, ordered=True)).groupby(
        "layer", observed=True).size().reset_index(name="tests")
    d = d.iloc[::-1]
    fig = go.Figure(go.Bar(y=d["layer"].astype(str), x=d["tests"], orientation="h", marker_color=BLUE, width=0.55,
                           text=d["tests"], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x} tests<extra></extra>"))
    _bar_style(fig)
    fig.update_xaxes(title="tests", range=[0, d["tests"].max() * 1.18])
    return _finish(fig, "Where the tests sit (number of tests per layer)",
                   "Every layer is tested; the marts carry the most because analysts depend on them.",
                   height=320, legend=False)


# ----------------------------------------------------------------------------- Q1
def _ci(df: pd.DataFrame, rate: str, lo: str, hi: str) -> dict:
    return dict(type="data", symmetric=False, array=df[hi] - df[rate], arrayminus=df[rate] - df[lo],
                color=INK_2, thickness=1.2, width=4)


def q1_late_vs_on_time(df: pd.DataFrame, bad_max: int = 2) -> go.Figure:
    d = df.set_index("delivery_outcome").loc[["late", "on time"]].reset_index()
    fig = go.Figure(go.Bar(
        y=d["delivery_outcome"], x=d["bad_review_rate_pct"], orientation="h", marker_color=[ORANGE, BLUE],
        width=0.5, error_x=_ci(d, "bad_review_rate_pct", "ci_low_pct", "ci_high_pct"),
        text=[pct(v) for v in d["bad_review_rate_pct"]], textposition="inside", insidetextanchor="middle",
        textfont=dict(color="#ffffff"),
        customdata=d[["reviewed_deliveries", "ci_low_pct", "ci_high_pct"]],
        hovertemplate="%{y}: %{x:.1f}% bad reviews (95% CI %{customdata[1]:.1f}-%{customdata[2]:.1f}%)"
                      "<br>%{customdata[0]:,} reviewed deliveries<extra></extra>"))
    _bar_style(fig)
    fig.update_xaxes(title=f"orders with a review of {bad_max} stars or less (%)",
                     range=[0, d["ci_high_pct"].max() * 1.2])
    late, ok = d.iloc[0], d.iloc[1]
    return _finish(fig, "Bad-review rate: late vs on-time deliveries (%)",
                   f"{pct(late.bad_review_rate_pct)} of late orders get a bad review vs {pct(ok.bad_review_rate_pct)} "
                   f"on time ({late.bad_review_rate_pct / ok.bad_review_rate_pct:.1f}x). Association, not proof of cause.",
                   height=250, legend=False)


def q1_by_delay(df: pd.DataFrame, bad_max: int = 2) -> go.Figure:
    is_late = df["bucket_order"] >= 5
    fig = go.Figure()
    for flag, color, name in ((False, BLUE, "on time or early"), (True, ORANGE, "late")):
        d = df[is_late == flag]
        fig.add_trace(go.Bar(
            x=d["delay_bucket"], y=d["bad_review_rate_pct"], marker_color=color, name=name, width=bar_width(len(df)),
            error_y=_ci(d, "bad_review_rate_pct", "ci_low_pct", "ci_high_pct"),
            customdata=d[["reviewed_deliveries"]],
            hovertemplate="%{x}: %{y:.1f}% bad reviews<br>%{customdata[0]:,} reviewed deliveries<extra></extra>"))
    _bar_style(fig)
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=df["delay_bucket"].tolist())
    fig.update_yaxes(title=f"bad reviews (≤{bad_max} stars, %)", rangemode="tozero")
    early = df.loc[df["bucket_order"] <= 3, "bad_review_rate_pct"].mean()
    worst = df["bad_review_rate_pct"].max()
    return _finish(fig, "Bad-review rate by delivery vs the promised date (%)",
                   f"Early deliveries sit near {early:.0f}%; the rate jumps once a parcel is late and reaches {worst:.0f}%.",
                   height=400, legend=True)


def q1_states(df: pd.DataFrame, national: pd.DataFrame | None = None) -> go.Figure:
    fig = go.Figure()
    if national is not None and len(national) == 2:
        nat = national.set_index("delivery_outcome")
        p_late, p_ok = nat.loc["late", "bad_review_rate_pct"], nat.loc["on time", "bad_review_rate_pct"]
        xs = [0, df["late_rate_pct"].max() * 1.1]
        fig.add_trace(go.Scatter(x=xs, y=[p_ok + x / 100 * (p_late - p_ok) for x in xs], mode="lines",
                                 line=dict(color=MUTED, width=1.5, dash="dot"),
                                 name="expected from lateness alone", hoverinfo="skip"))
    size = 8 + 22 * (df["reviewed_deliveries"] / df["reviewed_deliveries"].max()) ** 0.5
    # label selectively: the most-late states and the biggest markets; the rest are on hover
    notable = set(df.nlargest(5, "late_rate_pct")["delivery_state"]) | set(
        df.nlargest(3, "reviewed_deliveries")["delivery_state"]) | set(df.nlargest(2, "excess_vs_expected_pp")["delivery_state"])
    labels = [s if s in notable else "" for s in df["delivery_state"]]
    fig.add_trace(go.Scatter(
        x=df["late_rate_pct"], y=df["bad_review_rate_pct"], mode="markers+text", text=labels,
        textposition="top center", textfont=dict(size=10.5, color=INK_2), name="delivery state",
        marker=dict(size=size, color=BLUE, opacity=0.85, line=dict(color=SURFACE, width=2)),
        customdata=df[["reviewed_deliveries", "avg_delivery_days", "excess_vs_expected_pp", "delivery_region"]],
        hovertext=df["delivery_state"],
        hovertemplate="<b>%{hovertext}</b> (%{customdata[3]})<br>late %{x:.1f}% · bad reviews %{y:.1f}%<br>"
                      "avg %{customdata[1]:.1f} days · %{customdata[0]:,} reviewed deliveries<br>"
                      "%{customdata[2]:+.1f} pp vs expected<extra></extra>"))
    fig.update_xaxes(title="late deliveries (%)", rangemode="tozero")
    fig.update_yaxes(title="bad reviews (%)")
    corr = df["late_rate_pct"].corr(df["bad_review_rate_pct"]) if len(df) > 2 else float("nan")
    worst = df.sort_values("late_rate_pct", ascending=False).head(3)["delivery_state"].tolist()
    sub = (f"Across {len(df)} states, late rate and bad-review rate move together (r = {corr:.2f}); "
           f"most often late: {', '.join(worst)}. Dotted line = what lateness alone predicts.")
    return _finish(fig, "By delivery state: lateness vs bad reviews (%)", sub, height=480, legend=True)


# ----------------------------------------------------------------------------- Q2
def q2_definitions(df: pd.DataFrame) -> go.Figure:
    d = df.iloc[::-1]
    colors = [BLUE if "official" in x else DEEMPH for x in d["definition"]]
    fig = go.Figure(go.Bar(y=d["definition"], x=d["repeat_rate_pct"], orientation="h", marker_color=colors,
                           width=0.5, text=[f"{v:.2f}%" for v in d["repeat_rate_pct"]], textposition="outside",
                           cliponaxis=False, customdata=d[["repeat_customers", "customers"]],
                           hovertemplate="%{y}<br>%{x:.2f}% (%{customdata[0]:,} of %{customdata[1]:,})<extra></extra>"))
    _bar_style(fig)
    fig.update_xaxes(title="customers who bought again (%)", range=[0, d["repeat_rate_pct"].max() * 1.25])
    hi, lo = df["repeat_rate_pct"].max(), df.loc[df["definition"].str.contains("official"), "repeat_rate_pct"].iloc[0]
    return _finish(fig, "Repeat-purchase rate under three definitions (% of customers)",
                   f"Counting split checkouts as repeat purchases overstates the rate by {hi / lo - 1:.0%}; "
                   f"the official definition gives {lo:.2f}%.", height=300, legend=False)


def q2_time_to_second(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Bar(x=df["time_to_second_purchase"], y=df["share_pct"], marker_color=BLUE,
                           width=bar_width(len(df)),
                           text=[f"{v:.0f}%" for v in df["share_pct"]], textposition="outside", cliponaxis=False,
                           customdata=df[["repeat_customers", "cumulative_share_pct"]],
                           hovertemplate="%{x}: %{y:.1f}% of repeaters (%{customdata[0]:,})<br>"
                                         "cumulative %{customdata[1]:.0f}%<extra></extra>"))
    _bar_style(fig)
    fig.update_xaxes(type="category")
    fig.update_yaxes(title="share of repeat customers (%)", range=[0, df["share_pct"].max() * 1.25])
    median = df["median_days_all_repeaters"].iloc[0]
    within_90 = df.loc[df["bucket_order"] == 3, "cumulative_share_pct"].iloc[0]
    return _finish(fig, "Time from first to second purchase day (% of repeat customers)",
                   f"Median {median:.0f} days; {within_90:.0f}% of repeaters return within 90 days.",
                   height=360, legend=False)


def q2_cohorts(df: pd.DataFrame, window: int) -> go.Figure:
    full, partial = df[df["is_fully_observed"]], df[~df["is_fully_observed"]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(full["cohort_month"]) + list(full["cohort_month"])[::-1],
                             y=list(full["ci_high_pct"]) + list(full["ci_low_pct"])[::-1], fill="toself",
                             fillcolor=BAND, line=dict(width=0), hoverinfo="skip", name="95% interval"))
    fig.add_trace(go.Scatter(x=full["cohort_month"], y=full["repeat_rate_pct"], mode="lines+markers",
                             line=dict(color=BLUE, width=2), marker=dict(size=8, line=dict(color=SURFACE, width=2)),
                             name="fully observed cohort", customdata=full[["customers", "repeat_customers"]],
                             hovertemplate="%{x}: %{y:.2f}% (%{customdata[1]:,} of %{customdata[0]:,})<extra></extra>"))
    if len(partial):
        fig.add_trace(go.Scatter(x=partial["cohort_month"], y=partial["repeat_rate_pct"], mode="markers",
                                 marker=dict(size=8, color=DEEMPH, line=dict(color=SURFACE, width=2)),
                                 name="not yet observed for the full window",
                                 hovertemplate="%{x}: %{y:.2f}% (incomplete window)<extra></extra>"))
    fig.update_xaxes(type="category", tickangle=-45)
    fig.update_yaxes(title=f"bought again within {window} days (%)", rangemode="tozero")
    avg = 100 * full["repeat_customers"].sum() / max(full["customers"].sum(), 1)
    return _finish(fig, f"Repurchase within {window} days, by first-purchase month (%)",
                   f"Fully observed cohorts average {avg:.2f}%; gray cohorts are too recent to judge.",
                   height=400, legend=True)


def q2_first_experience(df: pd.DataFrame, window: int) -> go.Figure:
    fig = go.Figure()
    for dim, color in (("first review", ORANGE), ("first delivery", BLUE)):
        d = df[df["dimension"] == dim].iloc[::-1]
        fig.add_trace(go.Bar(y=[f"{dim}: {v}" for v in d["first_order"]], x=d["repeat_rate_pct"], name=dim,
                             orientation="h", marker_color=color, width=0.55,
                             error_x=_ci(d, "repeat_rate_pct", "ci_low_pct", "ci_high_pct"),
                             customdata=d[["customers", "repeat_customers"]],
                             hovertemplate="%{y}: %{x:.2f}% (%{customdata[1]:,} of %{customdata[0]:,})<extra></extra>"))
    _bar_style(fig)
    fig.update_xaxes(title=f"bought again within {window} days (%)", rangemode="tozero")
    fig.update_layout(legend=dict(traceorder="reversed"))
    late = df[(df["dimension"] == "first delivery") & (df["first_order"] == "late")]["repeat_rate_pct"]
    ok = df[(df["dimension"] == "first delivery") & (df["first_order"] == "on time")]["repeat_rate_pct"]
    sub = (f"A late first delivery goes with a lower repurchase rate ({late.iloc[0]:.2f}% vs {ok.iloc[0]:.2f}%); "
           "the intervals are wide, so treat it as a lead, not a finding." if len(late) and len(ok) else "")
    return _finish(fig, "Repurchase by how the first order went (%)", sub, height=330, legend=True)


# ----------------------------------------------------------------------------- Q3
def q3_pareto(curve: pd.DataFrame, tiers: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=curve["seller_share_pct"], y=curve["cumulative_gmv_share_pct"], mode="lines",
                             line=dict(color=BLUE, width=2), name="cumulative GMV",
                             hovertemplate="top %{x:.1f}% of sellers -> %{y:.1f}% of GMV<extra></extra>"))
    t = tiers[tiers["top_pct_of_sellers"].isin([5, 10, 20])]
    fig.add_trace(go.Scatter(x=t["top_pct_of_sellers"], y=t["gmv_share_pct"], mode="markers+text",
                             marker=dict(size=9, color=ORANGE, line=dict(color=SURFACE, width=2)),
                             text=[f"top {a}% → {b:.0f}%" for a, b in zip(t["top_pct_of_sellers"], t["gmv_share_pct"])],
                             textposition="bottom right", textfont=dict(color=INK), name="tiers", hoverinfo="skip"))
    fig.update_xaxes(title="share of active sellers, largest first (%)", range=[0, 100])
    fig.update_yaxes(title="share of net GMV (%)", range=[0, 102])
    top10 = tiers.loc[tiers["top_pct_of_sellers"] == 10, "gmv_share_pct"].iloc[0]
    return _finish(fig, "How concentrated is GMV? (cumulative % of net GMV)",
                   f"The top 10% of sellers hold {top10:.0f}% of GMV: seller management can focus on a short list.",
                   height=400, legend=False)


def q3_handover(df: pd.DataFrame) -> go.Figure:
    d = df.sort_values("handover", ascending=False)
    colors = [BLUE if "on time" in h else ORANGE for h in d["handover"]]
    fig = go.Figure(go.Bar(y=d["handover"], x=d["late_delivery_rate_pct"], orientation="h", marker_color=colors,
                           width=0.5, error_x=_ci(d, "late_delivery_rate_pct", "late_ci_low_pct", "late_ci_high_pct"),
                           text=[pct(v) for v in d["late_delivery_rate_pct"]], textposition="inside",
                           insidetextanchor="middle", textfont=dict(color="#ffffff"),
                           customdata=d[["delivered_orders", "bad_review_rate_pct"]],
                           hovertemplate="%{y}: %{x:.1f}% late deliveries<br>%{customdata[0]:,} orders · "
                                         "%{customdata[1]:.1f}% bad reviews<extra></extra>"))
    _bar_style(fig)
    fig.update_xaxes(title="orders delivered after the estimate (%)", range=[0, d["late_ci_high_pct"].max() * 1.25])
    late = d[d["handover"].str.contains("late")].iloc[0]
    ok = d[d["handover"].str.contains("on time")].iloc[0]
    return _finish(fig, "Late delivery rate by the seller's handover to the carrier (%)",
                   f"When the seller misses its shipping deadline, {late.late_delivery_rate_pct:.0f}% of orders arrive late "
                   f"vs {ok.late_delivery_rate_pct:.0f}% otherwise (single-seller orders).", height=250, legend=False)


def q3_quadrants(points: pd.DataFrame, late_threshold: float, bad_threshold: float) -> go.Figure:
    at_risk = (points["late_handover_rate_pct"] > late_threshold) & (points["bad_review_rate_pct"] > bad_threshold)
    fig = go.Figure()
    for flag, color, name in ((False, BLUE, "other established sellers"), (True, ORANGE, "late handover AND bad reviews")):
        d = points[at_risk == flag]
        size = 7 + 20 * (d["gmv_brl"].astype(float) / points["gmv_brl"].astype(float).max()) ** 0.5
        fig.add_trace(go.Scatter(
            x=d["late_handover_rate_pct"], y=d["bad_review_rate_pct"], mode="markers", name=name,
            marker=dict(size=size, color=color, opacity=0.8 if flag else 0.45, line=dict(color=SURFACE, width=1.5)),
            customdata=d[["seller_id", "seller_state", "net_orders", "gmv_brl", "top_category"]],
            hovertemplate="seller %{customdata[0]}<br>%{customdata[1]} · %{customdata[4]}<br>"
                          "late handover %{x:.1f}% · bad reviews %{y:.1f}%<br>%{customdata[2]:,} orders · "
                          "R$%{customdata[3]:,.0f} GMV<extra></extra>"))
    fig.add_vline(x=late_threshold, line=dict(color=MUTED, width=1, dash="dot"))
    fig.add_hline(y=bad_threshold, line=dict(color=MUTED, width=1, dash="dot"))
    fig.update_xaxes(title="orders handed to the carrier after the deadline (%)", rangemode="tozero")
    fig.update_yaxes(title="bad reviews (%)", rangemode="tozero")
    share = 100 * points.loc[at_risk, "gmv_brl"].astype(float).sum() / max(points["gmv_brl"].astype(float).sum(), 1)
    return _finish(fig, "Established sellers: handover SLA vs reviews (%)",
                   f"{int(at_risk.sum())} of {len(points)} sellers are above both thresholds, holding {share:.1f}% of "
                   "their GMV. Bubble size = GMV.", height=480, legend=True)


# ----------------------------------------------------------------------------- dashboard
def monthly_bars(df: pd.DataFrame, column: str, title: str, axis_title: str, money: bool = False) -> go.Figure:
    fig = go.Figure(go.Bar(x=df["year_month"], y=df[column], marker_color=BLUE, width=bar_width(len(df)),
                           hovertemplate="%{x}: " + ("R$%{y:,.0f}" if money else "%{y:,}") + "<extra></extra>"))
    _bar_style(fig)
    fig.update_xaxes(type="category", tickangle=-45)
    fig.update_yaxes(title=axis_title, tickformat="~s", rangemode="tozero")
    peak = df.loc[df[column].idxmax()] if len(df) else None
    sub = (f"Peak {peak.year_month}: " + (fmt_brl(peak[column]) if money else fmt_int(peak[column]))
           + (" (Black Friday month)" if peak is not None and str(peak.year_month).endswith("-11") else "")) if peak is not None else ""
    return _finish(fig, title, sub, height=340, legend=False)


def monthly_line(df: pd.DataFrame, column: str, title: str, axis_title: str, suffix: str = "") -> go.Figure:
    fig = go.Figure(go.Scatter(x=df["year_month"], y=df[column], mode="lines+markers",
                               line=dict(color=BLUE, width=2), marker=dict(size=7, line=dict(color=SURFACE, width=2)),
                               hovertemplate="%{x}: %{y:.1f}" + suffix + "<extra></extra>"))
    fig.update_xaxes(type="category", tickangle=-45)
    fig.update_yaxes(title=axis_title, rangemode="tozero")
    if len(df):
        lo, hi = df.loc[df[column].idxmin()], df.loc[df[column].idxmax()]
        sub = f"Lowest {lo.year_month} ({lo[column]:.1f}{suffix}), highest {hi.year_month} ({hi[column]:.1f}{suffix})."
    else:
        sub = ""
    return _finish(fig, title, sub, height=340, legend=False)


def horizontal_bars(df: pd.DataFrame, label: str, value: str, title: str, axis_title: str,
                    money: bool = False, subtitle: str = "", height: int = 420) -> go.Figure:
    d = df.iloc[::-1]
    text = [fmt_brl(v) if money else fmt_int(v) for v in d[value]]
    fig = go.Figure(go.Bar(y=d[label], x=d[value], orientation="h", marker_color=BLUE, width=0.55, text=text,
                           textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: " + ("R$%{x:,.0f}" if money else "%{x:,}") + "<extra></extra>"))
    _bar_style(fig)
    fig.update_xaxes(title=axis_title, tickformat="~s", range=[0, float(d[value].max()) * 1.2])
    return _finish(fig, title, subtitle, height=height, legend=False)


def region_split(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for column, color, name in (("customers_pct", BLUE, "customers"), ("sellers_pct", ORANGE, "sellers")):
        fig.add_trace(go.Bar(x=df["region"], y=df[column], name=name, marker_color=color, width=0.14,
                             hovertemplate="%{x}: %{y:.1f}% of " + name + "<extra></extra>"))
    _bar_style(fig)
    fig.update_layout(barmode="group", bargroupgap=0.08)
    fig.update_yaxes(title="share (%)", rangemode="tozero")
    se = df.set_index("region")
    sub = ""
    if "Northeast" in se.index:
        sub = (f"The Northeast has {se.loc['Northeast', 'customers_pct']:.0f}% of customers but "
               f"{se.loc['Northeast', 'sellers_pct']:.0f}% of sellers: its parcels travel far.")
    return _finish(fig, "Where customers and sellers are (% by macro-region)", sub, height=360, legend=True)


def safe_float(x) -> float:
    try:
        v = float(x)
        return v if math.isfinite(v) else float("nan")
    except (TypeError, ValueError):
        return float("nan")
