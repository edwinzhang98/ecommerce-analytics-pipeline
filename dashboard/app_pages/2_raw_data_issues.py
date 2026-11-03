import streamlit as st

import components as ui
from olist_analytics import analysis, charts

ui.require_cache()
ui.header(
    "Raw data issues",
    "What is wrong with the raw data, how big is each problem, and what did we do about it?",
)

issues = ui.table("dq_issues")
classes = list(dict.fromkeys(issues["class"]))
picked = st.multiselect("Issue class", classes, default=classes, placeholder="All classes")
shown = issues[issues["class"].isin(picked or classes)]

left, right = st.columns([3, 2], gap="large")
with left:
    st.subheader(f"Issue register ({len(shown)} of {len(issues)})")
    event = st.dataframe(
        shown[["id", "class", "table", "title", "affected", "unit"]], hide_index=True, use_container_width=True,
        on_select="rerun", selection_mode="single-row", height=420,
        column_config={"affected": st.column_config.NumberColumn("affected", format="%d")},
    )
    rows = event.selection.rows if event and event.selection else []
    chosen = shown.iloc[rows[0]] if rows else shown.iloc[0]
with right:
    st.subheader(f"{chosen['id']} · {chosen['title']}")
    st.markdown(f"**Affected:** {ui.fmt_int(chosen['affected'])} {chosen['unit']}  \n**Table:** `{chosen['table']}`")
    st.markdown(ui.md_safe(f"**What we found.** {chosen['detail']}"))
    st.markdown(ui.md_safe(f"**How it is handled.** {chosen['handling']}"))
    st.markdown(ui.md_safe(f"**What analysts should know.** {chosen['downstream']}"))
    if chosen["dbt_tests"]:
        st.caption(f"Guarded by: {chosen['dbt_tests']}")
st.caption("Select a row to see the details. Counts are recomputed from the raw tables on every `make cache`.")

ui.chart(charts.issues_by_class(issues))

st.subheader("Try it: how many orders fail the payment check?")
st.markdown("Payments should equal items + freight. Move the tolerance and the count is recomputed from `fct_orders`.")
tolerance = st.select_slider("Tolerance (BRL)", options=[0.01, 0.10, 0.50, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0],
                             value=1.0, format_func=lambda v: f"R${v:g}")
curve = analysis.payment_mismatch_curve(ui.con())
at = analysis.payment_mismatch_at(ui.con(), tolerance)
m1, m2, m3 = st.columns(3)
m1.metric("Orders off by more than the tolerance", ui.fmt_int(at["mismatched_orders"]))
m2.metric("…of which card payments in installments", ui.fmt_int(at["overpaid_in_installments"]))
m3.metric("Net difference on those orders", ui.fmt_brl(at["net_difference_brl"]))
ui.chart(charts.payment_mismatch_curve(curve, tolerance, at))
st.caption(ui.md_safe("The production test uses R$1 and alerts if more than 249 orders fail (today's baseline)."))

c1, c2 = st.columns(2)
with c1:
    coverage = ui.sql_result("05_time_ranges_and_coverage", "monthly_coverage")
    ui.chart(charts.monthly_coverage(coverage))
with c2:
    lifecycle = ui.sql_result("08_lifecycle_consistency", "lifecycle_anomalies")
    ui.chart(charts.lifecycle_anomalies(lifecycle))
nulls = ui.sql_result("03_null_profile", "null_profile")
ui.chart(charts.null_profile(nulls))

st.subheader("Load audit: did every file arrive whole?")
audit = ui.sql_result("01_row_counts_vs_load_audit", "row_counts")
st.dataframe(audit, hide_index=True, use_container_width=True)
st.caption("`order_reviews` has 5,495 more physical lines than rows (comments contain line breaks). Counting with "
           "`wc -l` would be wrong, so the loader records both numbers.")

ui.how_to_read(ui.md_safe("""
**The register** lists every problem found while profiling the 9 raw files. Each one gets a number, a size and a
decision: fixed in the pipeline, kept with a flag, or monitored by a test. Select a row to read the details. The
right-hand panel says what an analyst should keep in mind.

**The bar chart** groups the issues by kind. The dangerous ones are not the biggest. For example, `customer_id`
looks like a customer key but is issued per order. Counting customers with it says nobody ever buys twice.

**The payment slider** is a live check. Customers' payments should equal what they bought (items + freight). A
handful of orders differ, mostly because card payments split into installments include interest. Move the
tolerance and watch how many orders fail. At R$1 it is 249 orders out of 98,665 (0.25%). That is the baseline the
automated test watches.

**Coverage chart:** the extract is thin at both ends (gray months), so trends use 2017-01 to 2018-08 only.

**Lifecycle chart:** orders whose timestamps contradict each other (e.g. picked up by the carrier before the
payment was approved). They are flagged, not deleted, so totals never silently change.

**Why it matters:** an analyst who knows these traps will not repeat them, and the tests stop them coming back
unnoticed.
"""))
