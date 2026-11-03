"""Prove that the incremental model `fct_order_items` is correct (ADR 0005).

Runs in its own DuckDB file so it never touches the main warehouse.

Scenario A, normal batches:
  1. load the extract as it looked on --cutoff (orders delivered later are still "shipped" or
     "processing") and build fct_order_items with --full-refresh; snapshot order status
  2. load the full extract and run fct_order_items incrementally; snapshot again
     -> new orders are added, and open orders whose status changed are updated even when they are
        older than the lookback window (the "re-process open orders" rule)
     -> the snapshot holds a second version for every order whose status moved
  3. run it again with no new data (idempotency: nothing may change)
  4. rebuild with --full-refresh and compare: incremental == full refresh, row for row

Scenario B, late-arriving records beyond the lookback window:
  1. load the earlier extract but hold back some orders from 30-60 days before the cutoff
  2. load the full extract and run incrementally: the held-back orders are older than the
     lookback window, so the incremental run misses them (a known limit of watermark loads)
  3. the grain test `fct_order_items_has_one_row_per_source_item` must FAIL (it catches the drift)
  4. --full-refresh repairs it and the test passes again

Usage:
    uv run python scripts/check_incremental.py               # real data (config.yaml)
    uv run python scripts/check_incremental.py --raw-dir ci/fixture --expected ci/fixture/expected_row_counts.yml
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
from olist_analytics.config import load_settings  # noqa: E402

CHECKSUM_SQL = """
select
    count(*) as row_count,
    sum(item_total_brl) as total_brl,
    md5(string_agg(
        concat_ws('|', order_item_key, order_id, order_item_id, product_id, seller_id, customer_unique_id,
                  order_purchase_date, order_status, is_net_order, order_purchased_at, shipping_limit_at,
                  item_price_brl, freight_value_brl, item_total_brl),
        ',' order by order_item_key
    )) as checksum
from marts.fct_order_items
"""


def run(cmd: list[str], env: dict, cwd: Path, expect_failure: bool = False) -> subprocess.CompletedProcess:
    print("  $", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if (proc.returncode != 0) != expect_failure:
        print(proc.stdout[-4000:], proc.stderr[-2000:], sep="\n")
        state = "failed" if proc.returncode else "unexpectedly succeeded"
        raise SystemExit(f"Command {state}: {' '.join(cmd)}")
    return proc


def snapshot(db_path: Path) -> dict:
    con = duckdb.connect(str(db_path), read_only=True)
    row_count, total, checksum = con.execute(CHECKSUM_SQL).fetchone()
    staged = con.execute("select count(*) from staging.stg_olist__order_items").fetchone()[0]
    watermark = con.execute("select max(order_purchased_at) from marts.fct_order_items").fetchone()[0]
    con.close()
    return {"rows": row_count, "staged_rows": staged, "total_brl": float(total or 0),
            "checksum": checksum, "watermark": str(watermark)}


def item_statuses(db_path: Path) -> dict[str, tuple]:
    con = duckdb.connect(str(db_path), read_only=True)
    rows = con.execute("select order_item_key, order_status, order_purchased_at from marts.fct_order_items").fetchall()
    con.close()
    return {key: (status, purchased_at) for key, status, purchased_at in rows}


def snapshot_versions(db_path: Path) -> dict:
    con = duckdb.connect(str(db_path), read_only=True)
    orders_with_history, versions = con.execute(
        """
        select count(*) filter (where n > 1), sum(n)
        from (select order_id, count(*) as n from snapshots.snp_olist__orders group by order_id)
        """
    ).fetchone()
    con.close()
    return {"orders_with_2plus_versions": int(orders_with_history or 0), "snapshot_rows": int(versions or 0)}


def rows_in_window(db_path: Path, watermark: str, lookback_days: int) -> int:
    con = duckdb.connect(str(db_path), read_only=True)
    n = con.execute(
        f"""
        select count(*)
        from staging.stg_olist__order_items as items
        inner join staging.stg_olist__orders as orders on items.order_id = orders.order_id
        where orders.order_purchased_at >= timestamp '{watermark}' - interval {lookback_days} day
        """
    ).fetchone()[0]
    con.close()
    return n


def main() -> int:
    settings = load_settings()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw-dir", type=Path, default=settings.raw_data_dir)
    parser.add_argument("--expected", type=Path, default=REPO_ROOT / "ingestion" / "expected_row_counts.yml")
    parser.add_argument("--cutoff", default="2018-07-01", help="Purchase-date cutoff of the simulated earlier extract.")
    parser.add_argument("--hold-back-orders", type=int, default=25)
    parser.add_argument("--lookback-days", type=int, default=3, help="Must match var fct_order_items_lookback_days.")
    parser.add_argument("--db", type=Path, default=REPO_ROOT / "data" / "warehouse" / "incremental_check.duckdb")
    parser.add_argument("--out", type=Path, default=settings.cache_dir / "incremental_check.json")
    args = parser.parse_args()
    # dbt runs from dbt/ and the loader from the repo root: use absolute paths everywhere
    args.db, args.raw_dir, args.expected, args.out = (
        p.expanduser().resolve() for p in (args.db, args.raw_dir, args.expected, args.out)
    )

    args.db.parent.mkdir(parents=True, exist_ok=True)
    if args.db.exists():
        args.db.unlink()
    env = {**os.environ, "DUCKDB_PATH": str(args.db)}
    dbt_dir = REPO_ROOT / "dbt"
    dbt = ["uv", "run", "dbt"]
    flags = ["--profiles-dir", "."]
    select_models = ["--select", "+fct_order_items"]
    load = ["uv", "run", "python", "ingestion/load_raw.py", "--raw-dir", str(args.raw_dir), "--duckdb-path", str(args.db)]
    started = time.perf_counter()
    result: dict = {"cutoff": args.cutoff, "lookback_days": args.lookback_days}

    print("\nScenario A: normal batches")
    run(load + ["--cutoff-date", args.cutoff], env, REPO_ROOT)
    run(dbt + ["seed"] + flags, env, dbt_dir)
    run(dbt + ["run"] + flags + select_models + ["--full-refresh"], env, dbt_dir)
    run(dbt + ["snapshot"] + flags, env, dbt_dir)
    batch_1 = snapshot(args.db)
    statuses_1 = item_statuses(args.db)
    run(load + ["--expected", str(args.expected)], env, REPO_ROOT)
    in_window = rows_in_window(args.db, batch_1["watermark"], args.lookback_days)
    run(dbt + ["run"] + flags + select_models, env, dbt_dir)
    run(dbt + ["snapshot"] + flags, env, dbt_dir)
    incremental = snapshot(args.db)
    statuses_2 = item_statuses(args.db)
    changed = [k for k, v in statuses_1.items() if statuses_2.get(k, (None,))[0] != v[0]]
    window_start = max(v[1] for v in statuses_1.values()) - timedelta(days=args.lookback_days)
    changed_outside_window = [k for k in changed if statuses_1[k][1] < window_start]
    history = snapshot_versions(args.db)
    run(dbt + ["run"] + flags + select_models, env, dbt_dir)
    rerun = snapshot(args.db)
    run(dbt + ["run"] + flags + ["--select", "fct_order_items", "--full-refresh"], env, dbt_dir)
    full_refresh = snapshot(args.db)
    result["scenario_a"] = {
        "batch_1_rows": batch_1["rows"],
        "batch_1_watermark": batch_1["watermark"],
        "new_or_recent_rows_in_lookback_window": in_window,
        "older_rows_whose_status_changed": len(changed),
        "of_which_outside_lookback_window": len(changed_outside_window),
        "orders_with_status_history_in_snapshot": history["orders_with_2plus_versions"],
        "rows_after_incremental": incremental["rows"],
        "rows_after_rerun": rerun["rows"],
        "rows_after_full_refresh": full_refresh["rows"],
        "staged_rows": full_refresh["staged_rows"],
        "rerun_identical": rerun["checksum"] == incremental["checksum"],
        "incremental_equals_full_refresh": incremental["checksum"] == full_refresh["checksum"],
        "checksum": full_refresh["checksum"],
    }

    print("\nScenario B: late-arriving records outside the lookback window")
    run(load + ["--cutoff-date", args.cutoff, "--hold-back-orders", str(args.hold_back_orders)], env, REPO_ROOT)
    run(dbt + ["run"] + flags + select_models + ["--full-refresh"], env, dbt_dir)
    run(load + ["--expected", str(args.expected)], env, REPO_ROOT)
    run(dbt + ["run"] + flags + select_models, env, dbt_dir)
    late = snapshot(args.db)
    grain_test = ["test"] + flags + ["--select", "fct_order_items_has_one_row_per_source_item"]
    run(dbt + grain_test, env, dbt_dir, expect_failure=True)
    run(dbt + ["run"] + flags + ["--select", "fct_order_items", "--full-refresh"], env, dbt_dir)
    run(dbt + grain_test, env, dbt_dir)
    repaired = snapshot(args.db)
    result["scenario_b"] = {
        "held_back_orders": args.hold_back_orders,
        "rows_missed_by_incremental": late["staged_rows"] - late["rows"],
        "grain_test_failed_as_expected": True,
        "rows_after_full_refresh": repaired["rows"],
        "repaired_equals_scenario_a": repaired["checksum"] == full_refresh["checksum"],
    }
    result["seconds"] = round(time.perf_counter() - started, 1)

    a, b = result["scenario_a"], result["scenario_b"]
    ok = (a["rerun_identical"] and a["incremental_equals_full_refresh"]
          and a["rows_after_full_refresh"] == a["staged_rows"]
          and a["of_which_outside_lookback_window"] > 0 and a["orders_with_status_history_in_snapshot"] > 0
          and b["rows_missed_by_incremental"] > 0 and b["repaired_equals_scenario_a"])
    result["passed"] = bool(ok)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    args.db.unlink(missing_ok=True)

    print(f"""
Scenario A (normal):
  batch 1 (orders < {args.cutoff}): {a['batch_1_rows']:,} rows, watermark {a['batch_1_watermark']}
  incremental run: {a['new_or_recent_rows_in_lookback_window']:,} rows in the lookback window + open orders
    -> {a['rows_after_incremental']:,} rows; {a['older_rows_whose_status_changed']:,} existing rows changed status and were updated,
       {a['of_which_outside_lookback_window']:,} of them older than the lookback window (caught by the open-order rule)
  snapshot captured a second version for {a['orders_with_status_history_in_snapshot']:,} orders
  re-run with no new data identical: {a['rerun_identical']}
  incremental == full refresh (row-level checksum): {a['incremental_equals_full_refresh']}
Scenario B (late-arriving, {b['held_back_orders']} orders older than the lookback):
  incremental missed {b['rows_missed_by_incremental']} rows -> grain test failed as designed
  full refresh repaired it, equal to scenario A: {b['repaired_equals_scenario_a']}
Result: {'PASS' if ok else 'FAIL'}  ({result['seconds']}s, written to {args.out})""")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
