import pandas as pd
import streamlit as st

import components as ui
from olist_analytics import charts

ui.require_cache()
ui.header(
    "Analyst guide",
    "Which table answers my question, how do I join it, and what must I never do?",
)

st.subheader("Which table for which question")
guide = pd.DataFrame([
    ("How many orders? Revenue? Delivery or review KPIs?", "fct_orders", "one row per order (any status)",
     "is_net_order, order_purchase_date, order_gmv_brl, is_late_delivery, review_score"),
    ("Sales by product, category or seller", "fct_order_items", "one row per unit sold",
     "is_net_order, item_total_brl, product_id, seller_id"),
    ("Who are the customers? RFM inputs", "dim_customers", "one row per person",
     "customer_unique_id, recency_days, frequency_orders, monetary_gmv_brl"),
    ("Everything about a customer in one row (CRM)", "customer_360", "one row per person",
     "customer_lifecycle_stage, days_to_second_purchase, top_category"),
    ("Seller ranking, SLA and reviews", "seller_scorecard", "one row per seller",
     "gmv_rank, late_handover_rate, bad_review_rate, net_orders"),
    ("Product attributes and English category", "dim_products", "one row per product", "product_category"),
    ("Seller location", "dim_sellers", "one row per seller", "seller_state, seller_region"),
    ("Calendar, holidays, complete months", "dim_date", "one row per day", "year_month, is_complete_data_month"),
], columns=["question", "table", "grain", "key columns"])
st.dataframe(guide, hide_index=True, use_container_width=True)

st.subheader("The star schema")
st.markdown(charts.star_schema_svg(ui.stats().get("mart_rows")), unsafe_allow_html=True)

st.subheader("How to join")
st.markdown("""
| from | to | on | cardinality |
|---|---|---|---|
| `fct_orders` | `dim_customers` | `customer_unique_id` | many orders → one person |
| `fct_orders` | `dim_date` | `order_purchase_date = date_day` | many → one |
| `fct_order_items` | `fct_orders` | `order_id` | many items → one order (safe) |
| `fct_order_items` | `dim_products` / `dim_sellers` | `product_id` / `seller_id` | many → one |
""")

do, dont = st.columns(2)
with do:
    st.markdown("""
**Do**
- Count orders with `count(*) filter (where is_net_order)` on `fct_orders`.
- Count people with `customer_unique_id`.
- Date every order metric by `order_purchase_date` (local São Paulo time).
- Filter trends to `dim_date.is_complete_data_month`.
- Sum `item_total_brl` only `where is_net_order` for product, category or seller GMV.
""")
with dont:
    st.markdown("""
**Don't**
- Don't query `raw`, `staging` or `intermediate`. Use the marts only.
- Don't join `fct_order_items` and then count orders or sum order amounts: that is the fan-out that started this.
- Don't call delivered orders "orders": say *delivered orders*.
- Don't count reviews by `review_id`: one answer can cover several orders. Review metrics are per order.
- Don't use `payment_total_brl` as revenue. It most likely includes card interest; GMV is the revenue measure.
""")

st.subheader("Try it: query the marts")
examples = {
    "Net orders and GMV by month": """select dim_date.year_month,
       count(*) filter (where fct_orders.is_net_order)               as net_orders,
       sum(fct_orders.order_gmv_brl) filter (where fct_orders.is_net_order) as net_gmv_brl
from marts.fct_orders
join marts.dim_date on fct_orders.order_purchase_date = dim_date.date_day
where dim_date.is_complete_data_month
group by 1 order by 1""",
    "Top categories by net GMV": """select dim_products.product_category, sum(fct_order_items.item_total_brl) as net_gmv_brl
from marts.fct_order_items
join marts.dim_products using (product_id)
where fct_order_items.is_net_order
group by 1 order by 2 desc limit 10""",
    "Repeat customers by region": """select customer_region,
       count(*) filter (where has_net_order) as customers,
       round(100.0 * count(*) filter (where is_repeat_customer) / count(*) filter (where has_net_order), 2) as repeat_rate_pct
from marts.dim_customers group by 1 order by 2 desc""",
    "The fan-out trap (wrong on purpose)": """-- counts item rows, not orders: compare with fct_orders
select count(*) as rows_not_orders,
       count(distinct order_id) as distinct_orders
from marts.fct_order_items""",
}
choice = st.selectbox("Example", list(examples))
sql = st.text_area("SQL (DuckDB dialect; tables in the `marts` schema)", examples[choice], height=190)
if st.button("Run query", type="primary"):
    try:
        result = ui.con().execute(sql).df()
        st.dataframe(result.head(500), hide_index=True, use_container_width=True)
        st.caption(f"{len(result):,} rows" + (" (first 500 shown)" if len(result) > 500 else ""))
        # quick look: chart the first numeric column against the first label column
        labels = [c for c in result.columns if not pd.api.types.is_numeric_dtype(result[c])]
        values = [c for c in result.columns if pd.api.types.is_numeric_dtype(result[c])]
        if labels and values and 1 < len(result) <= 40:
            ui.chart(charts.horizontal_bars(result.head(40), labels[0], values[0],
                                            f"{values[0]} by {labels[0]} (query result)", values[0],
                                            subtitle="Auto-chart of the query result: first label vs first number.",
                                            height=max(300, 26 * len(result) + 140)), key="playground")
    except Exception as exc:  # show the analyst the database error as-is
        st.error(f"Query failed: {exc}")
st.caption("Runs against a read-only copy of the marts held by this app. Full column definitions: "
           "docs/data_dictionary.md · full guide: docs/analyst_guide.md.")

ui.how_to_read("""
**This page is the short version of `docs/analyst_guide.md`.**

- **The diagram** is the star schema. Blue tables are facts (events: orders, items sold). White tables describe
  them (customers, products, sellers, dates). A line is a join key, and every join goes from many rows to one, so it
  cannot multiply rows.

- **The first table** maps everyday questions to the one mart that answers them, and states its *grain*: what one
  row means. Most wrong numbers come from forgetting the grain.
- **The join table** lists the only joins you need. Every one goes from many rows to one row, so a join can never
  multiply your rows.
- **Do / Don't** is the list of traps that produced the three different order counts.

**Try the query box.** Pick an example, edit it and run it. The last example shows the classic mistake: counting
rows of the item table instead of orders. The data dictionary documents every column of every mart.

**Why it matters:** the goal is that a new analyst can answer most questions on day one without asking anyone and
without touching raw data.
""")
