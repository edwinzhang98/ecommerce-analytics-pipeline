import streamlit as st

import components as ui
from olist_analytics import analysis, charts
from olist_analytics.config import REPO_ROOT

ui.require_cache()
ui.header(
    "Business questions",
    "Do the marts support real analysis? Three questions answered live from the marts only, with parameters you can change.",
)
st.caption("Each tab runs the SQL file in `analyses/` against the marts. The controls change that SQL's parameters, "
           "so every number below is recomputed, not looked up.")


@st.cache_data(show_spinner=False)
def run_q1(bad_max: int, min_orders: int, complete_only: bool):
    return analysis.q1_delivery_vs_reviews(ui.con(), bad_review_max_score=bad_max,
                                           min_orders_per_state=min_orders, complete_months_only=complete_only)


@st.cache_data(show_spinner=False)
def run_q2(window: int):
    return analysis.q2_repeat_purchase(ui.con(), repeat_window_days=window)


@st.cache_data(show_spinner=False)
def run_q3(min_orders: int, late_pct: int, bad_pct: int):
    res = analysis.q3_seller_performance(ui.con(), min_seller_orders=min_orders,
                                         late_handover_threshold_pct=late_pct, bad_review_threshold_pct=bad_pct)
    res["points"] = analysis.seller_points(ui.con(), min_orders)
    return res


def show_sql(file_name: str) -> None:
    with st.expander(f"SQL: analyses/{file_name}"):
        st.code((REPO_ROOT / "analyses" / file_name).read_text(encoding="utf-8"), language="sql")


q1_tab, q2_tab, q3_tab = st.tabs([
    "Q1 · Delivery and reviews by state", "Q2 · Repeat purchase", "Q3 · Seller performance"])

# ------------------------------------------------------------------------------------------- Q1
with q1_tab:
    st.markdown("**How do delivery time and lateness relate to bad reviews, and which states are worst?** "
                "Decision: where logistics improvements should start.")
    c1, c2, c3 = st.columns(3)
    bad_max = c1.radio("A bad review is a score of…", [1, 2, 3], index=1, horizontal=True,
                       format_func=lambda v: f"≤ {v} star{'s' if v > 1 else ''}")
    min_orders = c2.slider("Hide states with fewer reviewed deliveries than", 50, 2000, 300, step=50)
    complete_only = c3.toggle("Complete months only (2017-01 to 2018-08)", value=True)
    q1 = run_q1(bad_max, min_orders, complete_only)
    lv = q1["late_vs_on_time"].set_index("delivery_outcome")
    late_rate, ok_rate = lv.loc["late", "bad_review_rate_pct"], lv.loc["on time", "bad_review_rate_pct"]
    corr = q1["state_correlation"].iloc[0]
    m1, m2, m3 = st.columns(3)
    m1.metric("Bad reviews, late deliveries", charts.pct(late_rate))
    m2.metric("Bad reviews, on-time deliveries", charts.pct(ok_rate))
    m3.metric("States: late rate vs bad reviews", f"r = {corr['corr_late_rate_vs_bad_review_rate']:.2f}",
              help=f"Correlation across {int(corr['states_included'])} states; lateness alone explains "
                   f"{corr['r_squared_late_rate']:.0%} of the state-to-state spread.")
    ui.chart(charts.q1_late_vs_on_time(q1["late_vs_on_time"], bad_max), key="q1a")
    ui.chart(charts.q1_by_delay(q1["by_delay"], bad_max), key="q1b")
    ui.chart(charts.q1_states(q1["by_state"], q1["late_vs_on_time"]), key="q1c")
    worst = q1["by_state"].sort_values("excess_vs_expected_pp", ascending=False).head(3)
    st.markdown(
        f"**Reading.** Late deliveries get a bad review **{late_rate / ok_rate:.1f}x** as often as on-time ones. "
        f"Across states, lateness tracks bad reviews closely (r = {corr['corr_late_rate_vs_bad_review_rate']:.2f}). "
        "The dotted line shows the bad-review rate each state would have if only its lateness differed. "
        f"States above it ({', '.join(worst['delivery_state'])}) have more bad reviews than their lateness predicts, "
        "so something besides lateness is going on there. This is an association: remote states also differ in "
        "products, prices and carriers.")
    ui.table_view(q1["by_state"], "Table view: by delivery state")
    show_sql("q1_delivery_vs_reviews_by_state.sql")

# ------------------------------------------------------------------------------------------- Q2
with q2_tab:
    st.markdown("**What share of customers buy again, and how quickly?** Decision: retention vs acquisition budget, "
                "and which first-order experiences to fix.")
    window = st.slider("Repeat window: a customer counts as returning if the second purchase day is within … days",
                       30, 360, 180, step=30)
    q2 = run_q2(window)
    defs = q2["definition_sensitivity"]
    official = defs[defs["definition"].str.contains("official")].iloc[0]
    full = q2["cohort_repeat"][q2["cohort_repeat"]["is_fully_observed"]]
    in_window = 100 * full["repeat_customers"].sum() / max(full["customers"].sum(), 1)
    m1, m2, m3 = st.columns(3)
    m1.metric("Customers who ever bought again", charts.pct(official["repeat_rate_pct"], 2),
              help="Person with net orders on 2+ different days (official definition)")
    m2.metric(f"…within {window} days (fully observed cohorts)", charts.pct(in_window, 2))
    m3.metric("Cohorts fully observed", f"{len(full)} of {len(q2['cohort_repeat'])}")
    ui.chart(charts.q2_definitions(defs), key="q2a")
    left, right = st.columns(2)
    with left:
        ui.chart(charts.q2_time_to_second(q2["time_to_second_purchase"]), key="q2b")
    with right:
        ui.chart(charts.q2_first_experience(q2["repeat_by_first_experience"], window), key="q2d")
    ui.chart(charts.q2_cohorts(q2["cohort_repeat"], window), key="q2c")
    inflation = defs["repeat_rate_pct"].max() / official["repeat_rate_pct"] - 1
    st.markdown(
        f"**Reading.** Repeat buying is rare: {charts.pct(official['repeat_rate_pct'], 2)} of customers ever came "
        "back on a different day. The definition matters: counting split checkouts as repeat purchases inflates the "
        f"rate by {inflation:.0%}. Cohorts are compared only after each has had the full window to return (the gray ones "
        "have not yet), so recent months do not look artificially bad. A late or badly rated first order goes with "
        "a lower return rate, but with this few returning customers the intervals overlap. That is a hypothesis to "
        "test, not a result.")
    ui.table_view(q2["cohort_repeat"], "Table view: cohorts")
    show_sql("q2_repeat_purchase.sql")

# ------------------------------------------------------------------------------------------- Q3
with q3_tab:
    st.markdown("**How concentrated is GMV across sellers, and which sellers combine late handover with bad "
                "reviews?** Decision: which sellers the seller-management team calls first.")
    c1, c2, c3 = st.columns(3)
    min_seller = c1.slider("Established sellers: at least … net orders", 10, 300, 50, step=10)
    late_pct = c2.slider("Late handover above … %", 5, 50, 15, step=5)
    bad_pct = c3.slider("Bad reviews above … %", 5, 50, 20, step=5)
    q3 = run_q3(min_seller, late_pct, bad_pct)
    tiers = q3["gmv_concentration"].set_index("top_pct_of_sellers")
    quad = q3["seller_quadrants"].set_index("quadrant")
    risk = quad.loc[quad.index.str.startswith("1.")]
    m1, m2, m3 = st.columns(3)
    m1.metric("GMV held by the top 10% of sellers", charts.pct(tiers.loc[10, "gmv_share_pct"], 0))
    m2.metric("Sellers above both thresholds", int(risk["sellers"].sum()) if len(risk) else 0)
    m3.metric("…their share of marketplace GMV",
              charts.pct(risk["share_of_marketplace_gmv_pct"].sum() if len(risk) else 0))
    left, right = st.columns(2)
    with left:
        ui.chart(charts.q3_pareto(q3["pareto_curve"], q3["gmv_concentration"]), key="q3a")
    with right:
        ui.chart(charts.q3_handover(q3["handover_vs_outcome"]), key="q3b")
    ui.chart(charts.q3_quadrants(q3["points"], late_pct, bad_pct), key="q3c")
    st.markdown("**Watchlist** (largest sellers above both thresholds)")
    st.dataframe(q3["watchlist"], hide_index=True, use_container_width=True)
    hv = q3["handover_vs_outcome"].set_index("handover")["late_delivery_rate_pct"]
    ratio = hv[hv.index.str.contains("late")].iloc[0] / hv[hv.index.str.contains("on time")].iloc[0]
    st.markdown(
        "**Reading.** GMV is concentrated, so a short list of sellers moves the needle. Handing parcels to the "
        f"carrier after the seller's own deadline goes with {ratio:.1f}x the late-delivery rate. That gives seller "
        "management a lever the seller controls (handover), separate from the carrier's transit time. Thresholds "
        "are adjustable because the right cut-off is a business choice, not a statistical one.")
    ui.table_view(q3["seller_quadrants"], "Table view: quadrants")
    show_sql("q3_seller_performance.sql")

ui.how_to_read("""
**Each tab is one business question**, answered with SQL that reads the marts only. The SQL is shown under each
tab, and it is the same file that `scripts/run_sql.py` runs from the command line.

**Q1 · delivery and reviews.**
- Bars compare how often late and on-time deliveries get a 1-2 star review. The thin whiskers are 95% intervals:
  with ~90,000 reviews the uncertainty is tiny.
- The middle chart shows that the jump happens the moment a parcel is late.
- In the scatter, each bubble is a state. The dotted line is what lateness alone would predict. A state far above
  it has an extra problem worth a closer look.

**Q2 · repeat purchase.**
- Fewer than 3% of customers ever come back.
- The first chart shows how the definition changes the answer.
- The cohort line compares acquisition months fairly: a month only counts once its customers have had the full
  window to return.
- Move the window slider to see the effect.

**Q3 · sellers.**
- The curve shows how much GMV the biggest sellers hold.
- The bars show that a missed seller deadline goes with late deliveries.
- The scatter places every established seller by handover delays and bad reviews. Orange sellers cross both
  thresholds and are the call list.

**Caution:** these are associations in historical data, not experiments. They tell us where to look and what to
test next. They do not prove what would happen if we changed something.
""")
