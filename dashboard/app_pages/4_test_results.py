import pandas as pd
import streamlit as st

import components as ui
from olist_analytics import charts

ui.require_cache()
ui.header(
    "Test results",
    "How do we know the marts are right, and which known data problems are being watched?",
)

tests, stats = ui.table("tests"), ui.stats()
passed = int((tests["status"] == "pass").sum())
a, b, c, d = st.columns(4)
a.metric("Tests passing", f"{passed} / {len(tests)}")
b.metric("Known-issue baselines", stats["known_issue_tests"])
c.metric("Unit tests", stats["unit_tests"])
d.metric("Last dbt build", f"{stats['build_elapsed_seconds']} s")

left, right = st.columns(2)
with left:
    ui.chart(charts.tests_by_category(tests))
with right:
    ui.chart(charts.tests_by_layer(tests))

st.subheader("Known-issue baselines: problems we accept today, and when we will hear about them")
known = tests[tests["category"] == "known-issue baseline"][
    ["dq_issue", "test", "model", "failing_rows", "warn_if", "error_if", "status"]].sort_values(["dq_issue", "test"])
known = known.rename(columns={"failing_rows": "rows today", "warn_if": "warn when", "error_if": "fail when"})
st.dataframe(known, hide_index=True, use_container_width=True,
             column_config={"rows today": st.column_config.NumberColumn(format="%d")})
st.caption("Failing rows are stored in the `test_failures` schema, so anyone can inspect exactly which records "
           "are affected. CI plants each issue in a synthetic dataset and checks that every one of these tests "
           "detects it (ci/check_known_issues_detected.py).")

st.subheader("All tests")
f1, f2, f3 = st.columns([2, 2, 3])
cat = f1.multiselect("Category", sorted(tests["category"].unique()), placeholder="All categories")
layer = f2.multiselect("Layer", sorted(tests["layer"].unique()), placeholder="All layers")
search = f3.text_input("Search by test or model name", "")
view = tests
if cat:
    view = view[view["category"].isin(cat)]
if layer:
    view = view[view["layer"].isin(layer)]
if search:
    mask = view["test"].str.contains(search, case=False) | view["model"].fillna("").str.contains(search, case=False)
    view = view[mask]
st.dataframe(view[["test", "kind", "test_type", "category", "model", "column", "layer", "status", "seconds"]],
             hide_index=True, use_container_width=True, height=360)
st.caption(f"{len(view)} tests shown.")

st.subheader("Incremental model check (fct_order_items)")
inc = ui.json_file("incremental_check.json")
if inc:
    a_ = inc["scenario_a"]; b_ = inc["scenario_b"]
    x, y, z = st.columns(3)
    x.metric("Incremental == full refresh", "yes" if a_["incremental_equals_full_refresh"] else "NO")
    y.metric("Rows re-checked because their order was still open", ui.fmt_int(a_["of_which_outside_lookback_window"]),
             help="Rows older than the 3-day lookback whose order status changed between the two extracts")
    z.metric("Late-arriving rows caught by the grain test", ui.fmt_int(b_["rows_missed_by_incremental"]))
    st.markdown(
        f"Simulated an extract as of **{inc['cutoff']}**, then the full data. The incremental run added the new "
        f"orders and updated **{ui.fmt_int(a_['older_rows_whose_status_changed'])}** rows whose order changed status. "
        f"Running it again changed nothing. A full rebuild produced the identical table (row-level checksum). "
        f"In the late-data scenario, {b_['held_back_orders']} orders ({ui.fmt_int(b_['rows_missed_by_incremental'])} "
        "item rows) arriving outside the lookback window were missed on purpose. The grain test failed as designed, "
        "and a full refresh repaired it. "
        f"The snapshot recorded a second version for {ui.fmt_int(a_['orders_with_status_history_in_snapshot'])} orders."
    )
else:
    st.info("Run `make incremental-check` to produce this section.")

ui.how_to_read("""
**Every test is a question the data must answer correctly on every build.** The left chart sorts them by what they
check:
- **completeness / uniqueness:** keys are never null or duplicated.
- **referential integrity:** every order's customer exists in the customer table.
- **validity:** amounts are not negative; a parcel is not delivered before it was bought.
- **grain / fan-out:** each mart has exactly one row per order, item, person or seller.
- **reconciliation:** totals agree across tables, e.g. item GMV adds up to order GMV to the cent.
- **load integrity:** each raw table holds exactly what the loader read from its file.

**Known-issue baselines** are the honest part. Some raw problems cannot be fixed by us; for example, 1,359 orders
were picked up by the carrier before payment approval. Each such test passes at today's count, warns if the count
grows, and fails the build if it explodes. "Accepted" therefore never means "ignored".

**The incremental check** proves that the one table built incrementally ends up identical to a full rebuild. It
also shows that the safety net catches the case where incremental loading misses data.

**Why it matters:** "trustworthy" is not a claim, it is 300 checks that run on every change, including in CI on
every pull request.
""")
