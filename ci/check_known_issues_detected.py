"""CI guard: every known-issue test must DETECT its planted issue on the synthetic fixture.

On real data the known-issue tests pass at a documented baseline (warn if the count grows,
error if it explodes). On the small CI fixture those thresholds are never reached, so a passing
test alone would not prove the test can see anything. The fixture plants at least one instance
of every issue (ci/make_fixture.py), and this script asserts that each test tagged `known_issue`
  1. passed (planted counts stay under the production thresholds), and
  2. stored at least one failing row in its store_failures table (it detected the issue).

Usage (after `dbt build` on the fixture):
    uv run python ci/check_known_issues_detected.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET = REPO_ROOT / "dbt" / "target"


def main() -> int:
    manifest = json.loads((TARGET / "manifest.json").read_text())
    run_results = json.loads((TARGET / "run_results.json").read_text())
    status = {r["unique_id"]: r["status"] for r in run_results["results"]}
    db_path = os.environ.get("DUCKDB_PATH", str(REPO_ROOT / "data" / "warehouse" / "ci.duckdb"))
    con = duckdb.connect(db_path, read_only=True)

    rows, problems = [], []
    for uid, node in manifest["nodes"].items():
        if node["resource_type"] != "test" or "known_issue" not in node.get("tags", []):
            continue
        relation = f'test_failures."{node["alias"]}"'
        try:
            detected = con.execute(f"select count(*) from {relation}").fetchone()[0]
        except duckdb.Error:
            detected = None
        st = status.get(uid, "not run")
        rows.append((node["name"], st, detected))
        if st != "pass":
            problems.append(f"{node['name']}: status {st}")
        if not detected:
            problems.append(f"{node['name']}: detected nothing (planted issue missing or test cannot see it)")

    width = max(len(r[0]) for r in rows)
    print(f"{'known-issue test':{width}s}  status  rows detected")
    for name, st, detected in sorted(rows):
        print(f"{name:{width}s}  {st:6s}  {detected}")
    if problems:
        print("\nFAILED:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    print(f"\nAll {len(rows)} known-issue tests passed and detected their planted issue.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
