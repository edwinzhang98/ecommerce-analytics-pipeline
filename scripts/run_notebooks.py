"""Execute every notebook top to bottom (fresh kernel), save it with its outputs, and export it to
reports/<name>.html so it can be read without Jupyter.  Equivalent to:
    jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb
    jupyter nbconvert --to html --output-dir reports notebooks/*.ipynb
Usage:  uv run python scripts/run_notebooks.py        (make notebooks)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import nbformat
from nbconvert import HTMLExporter
from nbconvert.preprocessors import ExecutePreprocessor

REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = sorted((REPO_ROOT / "notebooks").glob("[0-9]*.ipynb"))
REPORTS = REPO_ROOT / "reports"


def main() -> int:
    REPORTS.mkdir(exist_ok=True)
    exporter = HTMLExporter(template_name="lab")
    for path in NOTEBOOKS:
        started = time.perf_counter()
        nb = nbformat.read(path, as_version=4)
        ExecutePreprocessor(timeout=600, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(path.parent)}})
        nbformat.write(nb, path)
        body, _ = exporter.from_notebook_node(nb)
        (REPORTS / f"{path.stem}.html").write_text(body, encoding="utf-8")
        print(f"  {path.name}: executed and exported in {time.perf_counter() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
