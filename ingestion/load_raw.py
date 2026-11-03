"""EL step: load the 9 raw Olist CSV files into the DuckDB `raw` schema.

Design choices (see docs/adr/0001-layered-architecture.md):
  * Every column lands as VARCHAR. `raw` is a lossless copy of the files; typing,
    renaming and cleaning happen in dbt staging. This keeps leading zeros in zip
    codes and never lets a bad value break the load.
  * Each table gets `_source_file` and `_loaded_at` metadata columns.
  * Every load writes one row per table to `raw.load_audit`: file size, md5,
    physical line count, parsed row count and the expected row count. A full load
    fails loudly if the parsed row count differs from `expected_row_counts.yml`.
  * `--cutoff-date` loads only orders purchased before that date (plus their
    child rows). It simulates an earlier extract so the incremental model can be
    demonstrated (see scripts/check_incremental.py). `--hold-back-orders N`
    additionally leaves out N older orders, to simulate records that arrive late.

Usage:
    uv run python ingestion/load_raw.py
    uv run python ingestion/load_raw.py --cutoff-date 2018-07-01
    uv run python ingestion/load_raw.py --raw-dir ci/fixture --expected ci/fixture/expected_row_counts.yml
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from olist_analytics.config import REPO_ROOT, load_settings  # noqa: E402

# raw table name -> source file name (Kaggle: olistbr/brazilian-ecommerce)
SOURCE_FILES: dict[str, str] = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "product_category_name_translation": "product_category_name_translation.csv",
}

# Child tables that are filtered to the surviving orders when --cutoff-date is used.
ORDER_CHILD_TABLES = ("order_items", "order_payments", "order_reviews")

DEFAULT_EXPECTED = REPO_ROOT / "ingestion" / "expected_row_counts.yml"


def file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def physical_data_lines(path: Path) -> int:
    """Number of newline-terminated lines minus the header (what `wc -l` would suggest)."""
    with open(path, "rb") as fh:
        newlines = sum(chunk.count(b"\n") for chunk in iter(lambda: fh.read(1 << 20), b""))
    return max(newlines - 1, 0)


def read_csv_sql(path: Path) -> str:
    # all_varchar keeps raw values untouched; header handles the UTF-8 BOM in the translation file.
    return f"read_csv('{path.as_posix()}', header = true, all_varchar = true)"


def load(raw_dir: Path, db_path: Path, expected_file: Path | None, cutoff_date: str | None,
         hold_back_orders: int = 0) -> list[dict]:
    missing = [f for f in SOURCE_FILES.values() if not (raw_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"{len(missing)} source file(s) not found in {raw_dir}: {missing}. "
            "Set OLIST_RAW_DIR (or raw_data_dir in config.yaml) to the folder with the Olist CSVs."
        )

    expected: dict[str, int] = {}
    if expected_file is not None and expected_file.exists():
        expected = yaml.safe_load(expected_file.read_text(encoding="utf-8")) or {}

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute("create schema if not exists raw")
    loaded_at = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)

    if cutoff_date:
        # Orders first, so child tables can be filtered to the surviving order ids.
        con.execute(
            f"""
            create or replace temp table _orders_in_scope as
            select order_id, customer_id
            from {read_csv_sql(raw_dir / SOURCE_FILES['orders'])}
            where try_cast(order_purchase_timestamp as timestamp) < date '{cutoff_date}'
            """
        )
        if hold_back_orders:
            # Late-arriving records: drop N orders purchased 30-60 days before the cutoff,
            # i.e. well outside the incremental lookback window. Deterministic choice.
            con.execute(
                f"""
                delete from _orders_in_scope
                where order_id in (
                    select order_id
                    from {read_csv_sql(raw_dir / SOURCE_FILES['orders'])}
                    where try_cast(order_purchase_timestamp as timestamp)
                        between date '{cutoff_date}' - interval 60 day and date '{cutoff_date}' - interval 30 day
                    order by md5(order_id)
                    limit {int(hold_back_orders)}
                )
                """
            )

    audit_rows: list[dict] = []
    for table, file_name in SOURCE_FILES.items():
        path = raw_dir / file_name
        started = time.perf_counter()
        where = ""
        if cutoff_date and table == "orders":
            where = "where order_id in (select order_id from _orders_in_scope)"
        elif cutoff_date and table in ORDER_CHILD_TABLES:
            where = "where order_id in (select order_id from _orders_in_scope)"
        elif cutoff_date and table == "customers":
            where = "where customer_id in (select customer_id from _orders_in_scope)"

        con.execute(
            f"""
            create or replace table raw.{table} as
            select
                *,
                '{file_name}' as _source_file,
                timestamp '{loaded_at}' as _loaded_at
            from {read_csv_sql(path)}
            {where}
            """
        )
        parsed_rows = con.execute(f"select count(*) from raw.{table}").fetchone()[0]
        exp = None if cutoff_date else expected.get(table)
        status = "ok" if exp is None or exp == parsed_rows else "row_count_mismatch"
        audit_rows.append(
            {
                "table_name": table,
                "source_file": file_name,
                "file_bytes": path.stat().st_size,
                "file_md5": file_md5(path),
                "physical_data_lines": physical_data_lines(path),
                "parsed_rows": parsed_rows,
                "expected_rows": exp,
                "status": status,
                "is_partial_load": bool(cutoff_date),
                "cutoff_date": cutoff_date,
                "load_seconds": round(time.perf_counter() - started, 2),
                "loaded_at": loaded_at,
            }
        )

    con.execute(
        """
        create or replace table raw.load_audit (
            table_name varchar, source_file varchar, file_bytes bigint, file_md5 varchar,
            physical_data_lines bigint, parsed_rows bigint, expected_rows bigint, status varchar,
            is_partial_load boolean, cutoff_date varchar, load_seconds double, loaded_at timestamp
        )
        """
    )
    con.executemany(
        "insert into raw.load_audit values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [list(r.values()) for r in audit_rows],
    )
    con.close()
    return audit_rows


def main() -> int:
    settings = load_settings()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw-dir", type=Path, default=settings.raw_data_dir)
    parser.add_argument("--duckdb-path", type=Path, default=settings.duckdb_path)
    parser.add_argument("--expected", type=Path, default=DEFAULT_EXPECTED,
                        help="YAML with expected row counts per table (checked on full loads only).")
    parser.add_argument("--cutoff-date", default=None,
                        help="Only load orders purchased before this ISO date (simulates an earlier extract).")
    parser.add_argument("--hold-back-orders", type=int, default=0,
                        help="With --cutoff-date: also leave out N orders from 30-60 days before the cutoff "
                             "(simulates late-arriving records).")
    args = parser.parse_args()

    print(f"Loading raw CSVs from {args.raw_dir}\n  -> {args.duckdb_path} (schema raw)")
    if args.cutoff_date:
        print(f"  partial load: orders purchased before {args.cutoff_date}"
              + (f", holding back {args.hold_back_orders} older orders" if args.hold_back_orders else ""))
    rows = load(args.raw_dir.expanduser(), args.duckdb_path.expanduser(), args.expected, args.cutoff_date,
                args.hold_back_orders)

    print(f"\n{'table':36s} {'rows':>10s} {'expected':>10s} {'file lines':>11s}  status")
    for r in rows:
        exp = "-" if r["expected_rows"] is None else f"{r['expected_rows']:,}"
        print(f"{r['table_name']:36s} {r['parsed_rows']:>10,} {exp:>10s} {r['physical_data_lines']:>11,}  {r['status']}")
    bad = [r["table_name"] for r in rows if r["status"] != "ok"]
    if bad:
        print(f"\nERROR: parsed row counts differ from {args.expected} for: {bad}", file=sys.stderr)
        return 1
    print("\nLoad complete; audit written to raw.load_audit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
