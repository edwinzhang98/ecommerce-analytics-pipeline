import streamlit as st

import components as ui
from olist_analytics import analysis, charts

ui.require_cache()
stats = ui.stats()

ui.header(
    "Overview",
    "Why did three analysts report three different order counts, and what did we build so that it cannot happen again?",
)

net_orders = ui.con().execute("select count(*) filter (where is_net_order) from marts.fct_orders").fetchone()[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Net orders (official KPI)", ui.fmt_int(net_orders),
          help="Orders placed minus canceled and unavailable. Defined in ADR 0002.")
c2.metric("dbt models", stats["models"], help="9 staging, 7 intermediate, 6 star-schema marts, 2 wide tables")
c3.metric("Tests passing", f"{stats['tests_passed']} / {stats['data_tests'] + stats['unit_tests']}",
          help="Data tests + unit tests in the last dbt build")
c4.metric("Raw-data issues documented", stats["dq_issues"], help=f"In {stats['dq_issue_classes']} classes; see Raw data issues")

st.subheader("1 · The problem: one question, four answers")
three = ui.sql_result("01_three_analysts_on_raw", "order_counts").set_index("analyst", drop=False)
ui.chart(charts.three_analysts(three.reset_index(drop=True)))
fanout_revenue, paid = float(three.loc["A", "revenue_reported_brl"]), float(three.loc["B", "revenue_reported_brl"])
st.markdown(ui.md_safe(
    "- **Analyst A** joined orders to items and payments before counting: one order with 3 items and 2 payments "
    f"becomes 6 rows. The same query overstates revenue by **{fanout_revenue / paid - 1:.0%}** "
    f"({ui.fmt_brl(fanout_revenue)} vs {ui.fmt_brl(paid)} actually paid).\n"
    "- **Analyst B** counted every row in `orders`, including canceled and unavailable orders.\n"
    "- **Analyst C** counted delivered orders only: a valid metric, but a different one under the same name."
))
ui.table_view(three.reset_index(drop=True), "Table view: the four queries and why they differ")

st.subheader("2 · What we built")
st.markdown(charts.architecture_svg(stats), unsafe_allow_html=True)
st.markdown(
    "Raw files land unchanged in DuckDB. dbt cleans each table in **staging**, rolls every child table up to one "
    "row per order in **intermediate** (so nothing can fan out), and publishes a tested **star schema** plus two "
    "wide tables in **marts**. Analysts, this app and the report read the marts only."
)

st.subheader("3 · The result: every path gives the same number")
q0 = analysis.q0_order_count_reconciliation(ui.con())
ui.chart(charts.query_paths(q0["query_paths"]))
ui.table_view(q0["named_order_metrics"], "Table view: the three named order metrics (allowed to differ, each has its own name)")
st.caption("The same five-path check runs in every `dbt build` "
           "(`tests/singular/assert_net_order_count_consistent_across_query_paths.sql`), so a regression fails CI.")

ui.how_to_read("""
**The first chart** shows four answers to "how many orders did we have?". Each was computed from the raw tables
and each looks reasonable on its own. The spread (from 96,478 to 117,601) is the reason the business stopped
trusting the numbers. It has two causes:
- **Grain errors.** Joining tables that hold several rows per order multiplies the rows ("fan-out").
- **Definition drift.** "Orders" means different things to different people.

**The diagram** is the pipeline, left to right. Only the blue *marts* box is meant for analysts.

**The last chart** is the fix. The question is now answered through five different routes in the marts: the order
table, the item table, a month-by-month sum, and two customer tables. All of them land on **98,207 net orders**,
because:
- every mart has a tested grain (one row per order, per item, per person, ...);
- "net orders" is defined once, in a reviewed status mapping.

*Placed* (99,441) and *delivered* (96,478) still exist, but as separately named metrics.

**Why it matters:** the numbers can now be trusted by construction, and a test fails if that ever stops being true.
""")
