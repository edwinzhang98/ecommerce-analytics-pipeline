"""Olist analytics pipeline: demo app.

    streamlit run dashboard/app.py          (after `make all`)

Pages follow the story of the project, in the order they are presented. Every page reads the
parquet cache written by `make cache`; nothing is recomputed from raw data while presenting.
"""
import streamlit as st

st.set_page_config(page_title="Olist analytics pipeline", page_icon="📦", layout="wide",
                   initial_sidebar_state="expanded")

PAGES = [
    st.Page("app_pages/1_overview.py", title="Overview", icon=":material/account_tree:", url_path="overview", default=True),
    st.Page("app_pages/2_raw_data_issues.py", title="Raw data issues", icon=":material/report:", url_path="raw-data-issues"),
    st.Page("app_pages/3_model_lineage.py", title="Model lineage", icon=":material/schema:", url_path="model-lineage"),
    st.Page("app_pages/4_test_results.py", title="Test results", icon=":material/fact_check:", url_path="test-results"),
    st.Page("app_pages/5_business_questions.py", title="Business questions", icon=":material/query_stats:",
            url_path="business-questions"),
    st.Page("app_pages/6_dashboard.py", title="Dashboard", icon=":material/monitoring:", url_path="dashboard"),
    st.Page("app_pages/7_analyst_guide.py", title="Analyst guide", icon=":material/menu_book:", url_path="analyst-guide"),
]

with st.sidebar:
    st.caption("E-commerce analytics pipeline · Olist 2016-2018 · DuckDB + dbt")

st.navigation(PAGES).run()
