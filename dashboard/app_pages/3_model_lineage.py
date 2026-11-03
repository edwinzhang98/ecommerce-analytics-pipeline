from pathlib import Path

import streamlit as st

import components as ui
from olist_analytics import charts
from olist_analytics.config import REPO_ROOT

ui.require_cache()
ui.header(
    "Model lineage",
    "How does raw data become business-ready tables, and what depends on what?",
)

nodes, edges = ui.table("lineage_nodes"), ui.table("lineage_edges")
models = nodes[nodes["resource_type"] == "model"]

st.subheader("The whole project as dbt docs draws it")
shot = REPO_ROOT / "docs" / "images" / "dbt_lineage.png"
if shot.exists():
    st.image(str(shot), caption="dbt docs lineage graph (`make docs`, then open dbt/target/static_index.html)",
             use_container_width=True)
else:
    st.info("Screenshot not generated yet: run `make screenshots`.")

st.subheader("Explore one model: what it reads and what reads it")
order = ["marts (core)", "marts (business)", "intermediate", "staging"]
choices = models.assign(o=models["layer"].map({l: i for i, l in enumerate(order)})).sort_values(["o", "name"])["name"]
default = list(choices).index("fct_orders") if "fct_orders" in list(choices) else 0
picked = st.selectbox("Model", list(choices), index=default)
ui.chart(charts.lineage_graph(nodes, edges, picked), key="lineage")

card = nodes[nodes["name"] == picked].iloc[0]
a, b, c, d = st.columns(4)
a.metric("Layer", card["layer"])
b.metric("Materialized as", card["materialized"])
c.metric("Columns documented", f"{card['documented_columns']} / {card['columns']}")
d.metric("Tests on this model", int(card["tests"]))
st.markdown(f"**Description.** {card['description'] or '—'}")
st.caption(f"Source file: `dbt/{card['path']}` · contract enforced: {'yes' if card['contract'] else 'no'}"
           + (f" · access: {card['access']}" if card["access"] else ""))

st.subheader("Layers at a glance")
summary = (nodes[nodes["resource_type"].isin(["model", "source", "seed", "snapshot"])]
           .groupby("layer")
           .agg(nodes=("name", "count"), columns=("columns", "sum"), documented=("documented_columns", "sum"),
                tests=("tests", "sum"), contracts=("contract", "sum"))
           .reindex(["raw (source)", "seed", "snapshot", "staging", "intermediate", "marts (core)", "marts (business)"])
           .dropna(how="all").reset_index())
st.dataframe(summary, hide_index=True, use_container_width=True)

ui.how_to_read("""
**The screenshot** is the lineage graph dbt generates from the code itself (`ref()` and `source()` calls), so it
cannot drift from what actually runs. Green nodes on the left are the raw tables. Data flows to the right through
staging and intermediate into the marts.

**The explorer** answers "if I change this model, what breaks?" and "where does this number come from?".
- Pick a model (orange).
- Blue nodes are everything it reads from.
- Green nodes are everything that reads from it.

Example: `fct_orders` depends on 5 raw tables and 2 seeds, and feeds the two wide tables and the app.

**Layer rules** that keep the project maintainable:
- **staging:** one model per raw table; renames, types and cleaning only.
- **intermediate:** rolls every child table up to the order grain before anything is joined.
- **marts:** the only layer analysts use, with enforced contracts (fixed column names and types).

**Why it matters:** the lineage lets an analyst trace any number back to the raw rows it came from. It also lets
an engineer see the blast radius of a change before making it.
""")
