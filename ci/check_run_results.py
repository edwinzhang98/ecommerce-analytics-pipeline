"""Fail when the last dbt invocation produced any warning, error or failure.

`dbt build` exits 0 on warnings. Used in CI after the dbt_project_evaluator run, whose rule
violations are warnings, so that a best-practice violation blocks the pull request.

Usage:  uv run python ci/check_run_results.py [path/to/run_results.json]
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

DEFAULT = Path(__file__).resolve().parents[1] / "dbt" / "target" / "run_results.json"


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    results = json.loads(path.read_text())["results"]
    counts = Counter(r["status"] for r in results)
    bad = [r for r in results if r["status"] in ("warn", "error", "fail", "runtime error")]
    print(f"{len(results)} results: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    for r in bad:
        print(f"  {r['status'].upper():6s} {r['unique_id']}: {r.get('message')}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
