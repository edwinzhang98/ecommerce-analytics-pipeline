"""Business-question and dashboard computations, shared by the app, the report and the notebooks.

The business questions run the canonical SQL files in analyses/ with parameters, so the app's
sliders, the report and `scripts/run_sql.py` all execute exactly the same SQL.
"""
from __future__ import annotations

import duckdb
import pandas as pd

from olist_analytics.config import REPO_ROOT
from olist_analytics.sqlfile import run_sql_file

ANALYSES = REPO_ROOT / "analyses"

DEFAULTS = {
    "q1": {"bad_review_max_score": 2, "min_orders_per_state": 300, "complete_months_only": True},
    "q2": {"repeat_window_days": 180},
    "q3": {"min_seller_orders": 50, "late_handover_threshold_pct": 15, "bad_review_threshold_pct": 20},
}


def q0_order_count_reconciliation(con: duckdb.DuckDBPyConnection) -> dict[str, pd.DataFrame]:
    return run_sql_file(con, ANALYSES / "q0_order_count_reconciliation.sql")


def q1_delivery_vs_reviews(con: duckdb.DuckDBPyConnection, **params) -> dict[str, pd.DataFrame]:
    return run_sql_file(con, ANALYSES / "q1_delivery_vs_reviews_by_state.sql", {**DEFAULTS["q1"], **params})


def q2_repeat_purchase(con: duckdb.DuckDBPyConnection, **params) -> dict[str, pd.DataFrame]:
    return run_sql_file(con, ANALYSES / "q2_repeat_purchase.sql", {**DEFAULTS["q2"], **params})


def q3_seller_performance(con: duckdb.DuckDBPyConnection, **params) -> dict[str, pd.DataFrame]:
    return run_sql_file(con, ANALYSES / "q3_seller_performance.sql", {**DEFAULTS["q3"], **params})


def seller_points(con: duckdb.DuckDBPyConnection, min_seller_orders: int) -> pd.DataFrame:
    """Established sellers for the quadrant scatter (Q3)."""
    return con.execute(
        """
        select seller_id, seller_state, top_category, net_orders, gmv_brl,
               100 * late_handover_rate as late_handover_rate_pct,
               100 * bad_review_rate as bad_review_rate_pct, avg_review_score
        from marts.seller_scorecard
        where net_orders >= ? and late_handover_rate is not null and bad_review_rate is not null
        """,
        [min_seller_orders],
    ).df()


def payment_mismatch_curve(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Orders whose payments differ from items + freight by more than each tolerance (Raw Data Issues page)."""
    return con.execute(
        """
        with tolerances as (
            select unnest([0.01, 0.10, 0.50, 1, 2, 5, 10, 20, 50, 100]) as tolerance_brl
        )
        select
            tolerances.tolerance_brl,
            count(*) filter (where abs(fct_orders.payment_gmv_difference_brl) > tolerances.tolerance_brl)
                as mismatched_orders
        from tolerances
        cross join marts.fct_orders as fct_orders
        where fct_orders.has_items and fct_orders.has_payment
        group by tolerances.tolerance_brl
        order by tolerances.tolerance_brl
        """
    ).df()


def payment_mismatch_at(con: duckdb.DuckDBPyConnection, tolerance_brl: float) -> dict:
    row = con.execute(
        """
        select
            count(*) filter (where abs(payment_gmv_difference_brl) > ?) as mismatched_orders,
            count(*) as orders_with_items_and_payments,
            count(*) filter (where abs(payment_gmv_difference_brl) > ? and payment_gmv_difference_brl > 0
                             and max_payment_installments > 1) as overpaid_in_installments,
            coalesce(sum(payment_gmv_difference_brl) filter (where abs(payment_gmv_difference_brl) > ?), 0)
                as net_difference_brl
        from marts.fct_orders
        where has_items and has_payment
        """,
        [tolerance_brl, tolerance_brl, tolerance_brl],
    ).fetchone()
    keys = ["mismatched_orders", "orders_with_items_and_payments", "overpaid_in_installments", "net_difference_brl"]
    return dict(zip(keys, row))


# ----------------------------------------------------------------------------- dashboard
def _filters(start_month: str, end_month: str, regions: list[str] | None) -> tuple[str, list]:
    clauses = ["dim_date.year_month between ? and ?"]
    params: list = [start_month, end_month]
    if regions:
        clauses.append(f"fct_orders.delivery_region in ({', '.join('?' for _ in regions)})")
        params += regions
    return " and ".join(clauses), params


def dashboard_kpis(con, start_month: str, end_month: str, regions: list[str] | None = None) -> dict:
    where, params = _filters(start_month, end_month, regions)
    row = con.execute(
        f"""
        select
            count(*) filter (where fct_orders.is_net_order) as net_orders,
            coalesce(sum(fct_orders.order_gmv_brl) filter (where fct_orders.is_net_order), 0) as net_gmv_brl,
            avg(fct_orders.order_gmv_brl) filter (where fct_orders.is_net_order) as aov_brl,
            avg(case when fct_orders.is_late_delivery then 1.0 when not fct_orders.is_late_delivery then 0.0 end)
                as late_rate,
            median(fct_orders.delivery_days) as median_delivery_days,
            avg(fct_orders.review_score) as avg_review_score,
            count(distinct fct_orders.customer_unique_id) filter (where fct_orders.is_net_order) as customers,
            count(*) as placed_orders,
            count(*) filter (where not fct_orders.is_net_order) as canceled_or_unavailable
        from marts.fct_orders as fct_orders
        inner join marts.dim_date as dim_date on fct_orders.order_purchase_date = dim_date.date_day
        where {where}
        """,
        params,
    ).fetchone()
    keys = ["net_orders", "net_gmv_brl", "aov_brl", "late_rate", "median_delivery_days", "avg_review_score",
            "customers", "placed_orders", "canceled_or_unavailable"]
    return dict(zip(keys, row))


def dashboard_monthly(con, start_month: str, end_month: str, regions: list[str] | None = None) -> pd.DataFrame:
    where, params = _filters(start_month, end_month, regions)
    return con.execute(
        f"""
        select
            dim_date.year_month,
            count(*) filter (where fct_orders.is_net_order) as net_orders,
            coalesce(sum(fct_orders.order_gmv_brl) filter (where fct_orders.is_net_order), 0) as net_gmv_brl,
            100 * avg(case when fct_orders.is_late_delivery then 1.0 when not fct_orders.is_late_delivery then 0.0 end)
                as late_rate_pct,
            avg(fct_orders.delivery_days) as avg_delivery_days,
            avg(fct_orders.review_score) as avg_review_score
        from marts.fct_orders as fct_orders
        inner join marts.dim_date as dim_date on fct_orders.order_purchase_date = dim_date.date_day
        where {where}
        group by dim_date.year_month
        order by dim_date.year_month
        """,
        params,
    ).df()


def dashboard_by_state(con, start_month: str, end_month: str, regions: list[str] | None = None) -> pd.DataFrame:
    where, params = _filters(start_month, end_month, regions)
    return con.execute(
        f"""
        select
            fct_orders.delivery_state as state,
            any_value(fct_orders.delivery_region) as region,
            count(*) filter (where fct_orders.is_net_order) as net_orders,
            coalesce(sum(fct_orders.order_gmv_brl) filter (where fct_orders.is_net_order), 0) as net_gmv_brl,
            100 * avg(case when fct_orders.is_late_delivery then 1.0 when not fct_orders.is_late_delivery then 0.0 end)
                as late_rate_pct,
            median(fct_orders.delivery_days) as median_delivery_days
        from marts.fct_orders as fct_orders
        inner join marts.dim_date as dim_date on fct_orders.order_purchase_date = dim_date.date_day
        where {where}
        group by fct_orders.delivery_state
        order by net_orders desc
        """,
        params,
    ).df()


def dashboard_categories(con, start_month: str, end_month: str, regions: list[str] | None = None,
                         top_n: int = 12) -> pd.DataFrame:
    where, params = _filters(start_month, end_month, regions)
    return con.execute(
        f"""
        select
            dim_products.product_category as category,
            count(*) as items,
            sum(fct_order_items.item_total_brl) as net_gmv_brl
        from marts.fct_order_items as fct_order_items
        inner join marts.fct_orders as fct_orders on fct_order_items.order_id = fct_orders.order_id
        inner join marts.dim_date as dim_date on fct_orders.order_purchase_date = dim_date.date_day
        inner join marts.dim_products as dim_products on fct_order_items.product_id = dim_products.product_id
        where fct_order_items.is_net_order and {where}
        group by dim_products.product_category
        order by net_gmv_brl desc
        limit {int(top_n)}
        """,
        params,
    ).df()


def dashboard_regions(con) -> pd.DataFrame:
    """Where customers and sellers are (share of each by macro-region)."""
    return con.execute(
        """
        with customers as (
            select customer_region as region, count(*) as n from marts.dim_customers where has_net_order group by 1
        ),
        sellers as (
            select seller_region as region, count(*) as n from marts.seller_scorecard where net_orders > 0 group by 1
        )
        select
            coalesce(customers.region, sellers.region) as region,
            round(100.0 * coalesce(customers.n, 0) / sum(coalesce(customers.n, 0)) over (), 1) as customers_pct,
            round(100.0 * coalesce(sellers.n, 0) / sum(coalesce(sellers.n, 0)) over (), 1) as sellers_pct
        from customers
        full outer join sellers on customers.region = sellers.region
        order by customers_pct desc
        """
    ).df()


def available_months(con) -> list[str]:
    return [r[0] for r in con.execute(
        "select distinct year_month from marts.dim_date where is_complete_data_month order by 1").fetchall()]
