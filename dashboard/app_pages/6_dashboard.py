import streamlit as st

import components as ui
from olist_analytics import analysis, charts

ui.require_cache()
ui.header(
    "Dashboard",
    "How are orders, revenue, delivery and the customer and seller base doing, for the period and regions you pick?",
)

months = analysis.available_months(ui.con())
regions_all = ["Southeast", "South", "Northeast", "Center-West", "North"]
f1, f2 = st.columns([3, 2])
start, end = f1.select_slider("Purchase months (complete months only)", options=months,
                              value=(months[0], months[-1]))
regions = f2.multiselect("Delivery region", regions_all, placeholder="All regions")


@st.cache_data(show_spinner=False)
def load(start: str, end: str, regions: tuple):
    con, r = ui.con(), list(regions) or None
    return (analysis.dashboard_kpis(con, start, end, r), analysis.dashboard_monthly(con, start, end, r),
            analysis.dashboard_by_state(con, start, end, r), analysis.dashboard_categories(con, start, end, r))


kpis, monthly, states, cats = load(start, end, tuple(regions))
k = st.columns(6)
k[0].metric("Net orders", ui.fmt_int(kpis["net_orders"]))
k[1].metric("Net GMV", ui.fmt_brl(kpis["net_gmv_brl"]))
k[2].metric("Average order value", ui.fmt_brl(kpis["aov_brl"] or 0))
k[3].metric("Late deliveries", charts.pct(100 * (kpis["late_rate"] or 0)))
k[4].metric("Median delivery time", f"{kpis['median_delivery_days'] or 0:.0f} days")
k[5].metric("Average review", f"{kpis['avg_review_score'] or 0:.2f} / 5")
st.caption(f"{ui.fmt_int(kpis['placed_orders'])} orders placed in the period, of which "
           f"{ui.fmt_int(kpis['canceled_or_unavailable'])} canceled or unavailable; "
           f"{ui.fmt_int(kpis['customers'])} customers. Definitions: docs/02_metric_definitions.md.")

st.subheader("Orders and revenue")
a, b = st.columns(2)
with a:
    ui.chart(charts.monthly_bars(monthly, "net_orders", "Net orders per month (orders)", "net orders"), key="d1")
with b:
    ui.chart(charts.monthly_bars(monthly, "net_gmv_brl", "Net GMV per month (BRL)", "net GMV (BRL)", money=True),
             key="d2")

st.subheader("Delivery")
a, b = st.columns(2)
with a:
    ui.chart(charts.monthly_line(monthly, "late_rate_pct", "Late deliveries per month (% of delivered)",
                                 "late (%)", "%"), key="d3")
with b:
    ui.chart(charts.monthly_line(monthly, "avg_delivery_days", "Average delivery time per month (days)", "days"),
             key="d4")
ui.table_view(monthly, "Table view: monthly")

st.subheader("Where the orders go, and what sells")
a, b = st.columns(2)
with a:
    top_states = states.head(12)
    ui.chart(charts.horizontal_bars(top_states, "state", "net_orders", "Net orders by delivery state (top 12)",
                                    "net orders", subtitle=f"{top_states.iloc[0]['state']} alone takes "
                                    f"{top_states.iloc[0]['net_orders'] / max(states['net_orders'].sum(), 1):.0%} "
                                    "of orders in the selection."), key="d5")
with b:
    ui.chart(charts.horizontal_bars(cats, "category", "net_gmv_brl", "Top categories by net GMV (BRL)",
                                    "net GMV (BRL)", money=True,
                                    subtitle=f"Top 3: {', '.join(cats['category'].head(3))}."), key="d6")
ui.table_view(states, "Table view: all delivery states (late rate, median days)")

st.subheader("Customers and sellers (whole period)")
ui.chart(charts.region_split(analysis.dashboard_regions(ui.con())), key="d7")

ui.how_to_read("""
**The filters drive every number on the page.**
- Pick a range of complete months and, optionally, the regions the orders were delivered to.
- Tiles, charts and tables all recompute from `fct_orders` and `fct_order_items` for that slice.
- Months outside 2017-01 to 2018-08 are not offered because the data is incomplete there.

**Definitions** (the same everywhere in the project):
- **Net orders:** placed minus canceled and unavailable.
- **Net GMV:** item prices plus freight of net orders.
- **Late:** delivered on a later day than the date promised at purchase.
- **Delivery time:** calendar days from purchase to delivery, delivered orders only.

**What to look for.**
- **Two delivery crises.** November 2017 (the Black Friday peak) had 12% late deliveries. February-March 2018 had
  14-19% late with flat volume. In both, the average review score dips (3.91 and 3.75, against ~4.2 in normal
  months), the same link Q1 finds at order level. The data does not record why March 2018 went wrong; that is a
  question for the logistics team.
- **Geography.** Most orders go to the Southeast, and sellers are even more concentrated there. Customers in the
  North and Northeast wait longest.

**Why it matters:** this is the page an operations or category manager would open weekly. Because it reads the
tested marts, its numbers match every other report built on them.
""")
