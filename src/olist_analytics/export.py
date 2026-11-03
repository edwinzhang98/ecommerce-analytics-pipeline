"""Build the cache that the Streamlit app and the HTML report read (`make cache`).

The app never queries the warehouse: it reads parquet / JSON files written here, so it starts
fast and works while dbt holds the DuckDB file. Everything is derived from the warehouse and
the dbt artifacts of the last build, so the app always shows the current state.

    uv run python -m olist_analytics.export artifacts   # after dbt build / docs: copy dbt artifacts
    uv run python -m olist_analytics.export cache       # write the cache
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import Counter
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from olist_analytics.config import REPO_ROOT, Settings, load_settings
from olist_analytics.sqlfile import run_sql_file

MART_TABLES = [
    "fct_orders", "fct_order_items", "dim_customers", "dim_products",
    "dim_sellers", "dim_date", "customer_360", "seller_scorecard",
]
DQ_SQL_DIR = REPO_ROOT / "sql" / "data_quality"
METRICS_SQL_DIR = REPO_ROOT / "sql" / "metrics"
ISSUE_REGISTER = DQ_SQL_DIR / "issue_register.yml"
ARTIFACT_FILES = ["manifest.json", "run_results.json", "catalog.json", "sources.json", "static_index.html"]


# --------------------------------------------------------------------------- dbt artifacts
def save_artifacts(settings: Settings) -> list[str]:
    """Copy the dbt artifacts of the last command into the cache (run_results.json is
    overwritten by every dbt command, so `make build` saves the build's copy right away)."""
    target = settings.dbt_dir / "target"
    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in ARTIFACT_FILES:
        src = target / name
        if not src.exists():
            continue
        if name == "run_results.json":
            # keep the results of `dbt build`, not of docs generate / source freshness
            args = json.loads(src.read_text()).get("args", {})
            if args.get("which") not in ("build", "test"):
                continue
        shutil.copy2(src, settings.artifacts_dir / name)
        copied.append(name)
    return copied


# --------------------------------------------------------------------------- helpers
def _write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def _layer(fqn: list[str], resource_type: str) -> str:
    if resource_type == "source":
        return "raw (source)"
    if resource_type == "seed":
        return "seed"
    if resource_type == "snapshot":
        return "snapshot"
    if resource_type == "exposure":
        return "exposure"
    if resource_type == "semantic_model":
        return "semantic layer"
    parts = fqn[1:-1]
    if parts[:1] == ["staging"]:
        return "staging"
    if parts[:1] == ["intermediate"]:
        return "intermediate"
    if parts[:2] == ["marts", "core"]:
        return "marts (core)"
    if parts[:2] == ["marts", "business"]:
        return "marts (business)"
    return "/".join(parts) or "other"


def _test_category(node: dict) -> str:
    tags = node.get("tags", [])
    name = (node.get("test_metadata") or {}).get("name") or ""
    if "known_issue" in tags:
        return "known-issue baseline"
    if "reconciliation" in tags or name in ("sum_matches",):
        return "reconciliation"
    if name in ("row_count_matches", "unique_combination_of_columns", "is_continuous_date_spine"):
        return "grain / fan-out"
    if name == "row_count_matches_load_audit":
        return "load integrity"
    if name == "relationships":
        return "referential integrity"
    if name in ("unique",):
        return "uniqueness"
    if name in ("not_null",):
        return "completeness"
    if name in ("accepted_values", "accepted_range", "non_negative", "not_before", "expression_is_true"):
        return "validity"
    return "business rule"


# --------------------------------------------------------------------------- cache parts
def export_marts(con: duckdb.DuckDBPyConnection, out: Path) -> dict[str, int]:
    (out / "marts").mkdir(parents=True, exist_ok=True)
    counts = {}
    for table in MART_TABLES:
        con.execute(f"copy marts.{table} to '{(out / 'marts' / f'{table}.parquet').as_posix()}' (format parquet)")
        counts[table] = con.execute(f"select count(*) from marts.{table}").fetchone()[0]
    return counts


def export_sql_results(con: duckdb.DuckDBPyConnection, out: Path) -> list[str]:
    written = []
    files = sorted(DQ_SQL_DIR.glob("*.sql")) + [
        METRICS_SQL_DIR / "01_three_analysts_on_raw.sql", METRICS_SQL_DIR / "03_customer_key_trap_on_raw.sql"]
    for path in files:
        for name, df in run_sql_file(con, path).items():
            if df is None:
                continue
            target = out / "sql" / f"{path.stem}__{name}.parquet"
            _write(df, target)
            written.append(target.name)
    return written


def export_issue_register(con: duckdb.DuckDBPyConnection, out: Path) -> pd.DataFrame:
    issues = yaml.safe_load(ISSUE_REGISTER.read_text(encoding="utf-8"))["issues"]
    rows = []
    for issue in issues:
        count = con.execute(issue["count_sql"]).fetchone()[0]
        rows.append({
            "id": issue["id"], "class": issue["class"], "table": issue["table"], "title": issue["title"],
            "affected": int(count), "unit": issue["unit"], "detail": " ".join(issue["detail"].split()),
            "handling": " ".join(str(issue["handling"]).split()),
            "downstream": " ".join(str(issue["downstream"]).split()),
            "dbt_tests": ", ".join(issue.get("dbt_tests") or []),
        })
    df = pd.DataFrame(rows)
    _write(df, out / "dq_issues.parquet")
    return df


def _test_target(node: dict, manifest: dict) -> dict | None:
    """The model / source / seed / snapshot a test is attached to; None for cross-model singular tests."""
    uid = node.get("attached_node")
    if not uid:
        kw_model = str(((node.get("test_metadata") or {}).get("kwargs") or {}).get("model", ""))
        src = re.search(r"source\('(\w+)',\s*'(\w+)'\)", kw_model)
        ref = re.search(r"ref\('(\w+)'\)", kw_model)
        if src:
            uid = f"source.olist_analytics.{src.group(1)}.{src.group(2)}"
        elif ref:
            uid = next((u for u, n in manifest["nodes"].items() if n.get("name") == ref.group(1)
                        and n["resource_type"] in ("model", "seed", "snapshot")), None)
        else:
            deps = node["depends_on"]["nodes"]
            uid = deps[0] if len(deps) == 1 else None
    return manifest["nodes"].get(uid) or manifest["sources"].get(uid) if uid else None


def export_test_results(con: duckdb.DuckDBPyConnection, artifacts: Path, out: Path) -> pd.DataFrame:
    manifest = json.loads((artifacts / "manifest.json").read_text())
    run_results = json.loads((artifacts / "run_results.json").read_text())
    results = {r["unique_id"]: r for r in run_results["results"]}
    nodes = {**manifest["nodes"], **manifest.get("unit_tests", {})}
    rows = []
    for uid, node in nodes.items():
        if node["resource_type"] not in ("test", "unit_test"):
            continue
        result = results.get(uid, {})
        if node["resource_type"] == "unit_test":
            target = manifest["nodes"].get(f"model.olist_analytics.{node.get('model')}")
            kind, category, test_name = "unit", "unit test", node["name"]
        else:
            meta = node.get("test_metadata") or {}
            kind = "generic" if meta else "singular"
            category, test_name = _test_category(node), meta.get("name", "singular")
            target = _test_target(node, manifest)
        attached = target["name"] if target else None
        layer = _layer(target.get("fqn", []), target["resource_type"]) if target else "cross-model"
        config = node.get("config", {})
        failing_rows = None
        if config.get("store_failures"):
            try:
                failing_rows = con.execute(f'select count(*) from test_failures."{node["alias"]}"').fetchone()[0]
            except duckdb.Error:
                failing_rows = None
        rows.append({
            "test": node["name"], "kind": kind, "test_type": test_name, "category": category,
            "model": attached, "column": node.get("column_name"), "layer": layer,
            "severity": config.get("severity"), "warn_if": config.get("warn_if"), "error_if": config.get("error_if"),
            "dq_issue": (config.get("meta") or {}).get("dq_issue"), "tags": ", ".join(node.get("tags", [])),
            "status": result.get("status", "not run"), "seconds": round(result.get("execution_time", 0.0), 3),
            "failing_rows": failing_rows,
        })
    df = pd.DataFrame(rows).sort_values(["category", "model", "test"]).reset_index(drop=True)
    _write(df, out / "tests.parquet")
    return df


def export_lineage(artifacts: Path, out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    manifest = json.loads((artifacts / "manifest.json").read_text())
    tests_per_node: Counter = Counter()
    for node in manifest["nodes"].values():
        if node["resource_type"] == "test":
            target = node.get("attached_node") or next(iter(node["depends_on"]["nodes"]), None)
            if target:
                tests_per_node[target] += 1
    for unit in manifest.get("unit_tests", {}).values():
        tests_per_node[f"model.olist_analytics.{unit.get('model')}"] += 1

    nodes, edges = [], []
    pools = [manifest["nodes"], manifest["sources"], manifest.get("exposures", {})]
    for pool in pools:
        for uid, node in pool.items():
            rtype = node["resource_type"]
            if rtype not in ("model", "seed", "snapshot", "source", "exposure"):
                continue
            if node.get("package_name") != "olist_analytics":
                continue
            if rtype == "source" and node["name"] == "load_audit":
                pass
            name = f"{node['source_name']}.{node['name']}" if rtype == "source" else node["name"]
            config = node.get("config", {})
            nodes.append({
                "unique_id": uid, "name": name, "resource_type": rtype,
                "layer": _layer(node.get("fqn", []), rtype),
                "materialized": config.get("materialized") if rtype in ("model", "snapshot") else rtype,
                "description": " ".join((node.get("description") or "").split())[:600],
                "columns": len(node.get("columns", {})),
                "documented_columns": sum(1 for c in node.get("columns", {}).values() if c.get("description")),
                "tests": tests_per_node.get(uid, 0),
                "contract": bool((config.get("contract") or {}).get("enforced")),
                "access": node.get("access") or config.get("access"),
                "path": node.get("original_file_path"),
            })
            for parent in node.get("depends_on", {}).get("nodes", []):
                if parent.split(".")[1] == "olist_analytics":
                    edges.append({"parent": parent, "child": uid})
    nodes_df, edges_df = pd.DataFrame(nodes), pd.DataFrame(edges).drop_duplicates()
    _write(nodes_df, out / "lineage_nodes.parquet")
    _write(edges_df, out / "lineage_edges.parquet")
    return nodes_df, edges_df


def export_load_audit(con: duckdb.DuckDBPyConnection, out: Path) -> None:
    _write(con.execute("select * from raw.load_audit").df(), out / "load_audit.parquet")


def project_stats(marts: dict, tests: pd.DataFrame, lineage: pd.DataFrame, issues: pd.DataFrame,
                  artifacts: Path) -> dict:
    manifest = json.loads((artifacts / "manifest.json").read_text())
    run_results = json.loads((artifacts / "run_results.json").read_text())
    models = lineage[lineage.resource_type == "model"]
    statuses = Counter(r["status"] for r in run_results["results"])
    return {
        "dbt_version": manifest["metadata"]["dbt_version"],
        "generated_at": manifest["metadata"]["generated_at"],
        "build_elapsed_seconds": round(run_results.get("elapsed_time", 0.0), 1),
        "build_status_counts": dict(statuses),
        "models_by_layer": models.groupby("layer").size().to_dict(),
        "models": int(len(models)),
        "sources": int((lineage.resource_type == "source").sum()),
        "seeds": int((lineage.resource_type == "seed").sum()),
        "snapshots": int((lineage.resource_type == "snapshot").sum()),
        "exposures": int((lineage.resource_type == "exposure").sum()),
        "semantic_models": len(manifest.get("semantic_models", {})),
        "metrics": len(manifest.get("metrics", {})),
        "data_tests": int((tests.kind != "unit").sum()),
        "unit_tests": int((tests.kind == "unit").sum()),
        "custom_generic_test_types": sorted(
            set(tests.loc[tests.kind == "generic", "test_type"]) & {
                "non_negative", "not_before", "row_count_matches", "sum_matches",
                "row_count_matches_load_audit", "is_continuous_date_spine"}),
        "singular_tests": int((tests.kind == "singular").sum()),
        "known_issue_tests": int((tests.category == "known-issue baseline").sum()),
        "tests_by_category": tests.groupby("category").size().to_dict(),
        "tests_passed": int((tests.status == "pass").sum()),
        "mart_columns": int(models.loc[models.layer.str.startswith("marts"), "columns"].sum()),
        "mart_columns_documented": int(models.loc[models.layer.str.startswith("marts"), "documented_columns"].sum()),
        "contracted_models": int(models.contract.sum()),
        "dq_issues": int(len(issues)),
        "dq_issue_classes": int(issues["class"].nunique()),
        "mart_rows": marts,
    }


def build_cache(settings: Settings) -> dict:
    out = settings.cache_dir
    out.mkdir(parents=True, exist_ok=True)
    artifacts = settings.artifacts_dir
    if not (artifacts / "manifest.json").exists() or not (artifacts / "run_results.json").exists():
        raise FileNotFoundError(
            f"dbt artifacts missing in {artifacts}. Run `make build docs` (or `make all`) first.")
    con = duckdb.connect(str(settings.duckdb_path), read_only=True)
    marts = export_marts(con, out)
    sql_files = export_sql_results(con, out)
    issues = export_issue_register(con, out)
    tests = export_test_results(con, artifacts, out)
    nodes, _ = export_lineage(artifacts, out)
    export_load_audit(con, out)
    con.close()
    stats = project_stats(marts, tests, nodes, issues, artifacts)
    (out / "project_stats.json").write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")
    return {"marts": marts, "sql_results": len(sql_files), "issues": len(issues), "tests": len(tests), "stats": stats}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["artifacts", "cache"])
    args = parser.parse_args()
    settings = load_settings()
    if args.command == "artifacts":
        copied = save_artifacts(settings)
        print(f"Saved dbt artifacts to {settings.artifacts_dir}: {', '.join(copied) or 'none'}")
        return 0
    summary = build_cache(settings)
    stats = summary["stats"]
    print(f"Cache written to {settings.cache_dir}")
    print(f"  marts: {', '.join(f'{k}={v:,}' for k, v in summary['marts'].items())}")
    print(f"  {summary['sql_results']} SQL result sets, {summary['issues']} DQ issues, {summary['tests']} tests")
    print(f"  models={stats['models']} tests={stats['data_tests']}+{stats['unit_tests']} unit, "
          f"passed={stats['tests_passed']}, mart columns documented "
          f"{stats['mart_columns_documented']}/{stats['mart_columns']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
