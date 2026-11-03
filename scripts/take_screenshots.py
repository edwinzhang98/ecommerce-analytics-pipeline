"""Regenerate the README screenshots: every app page, plus the dbt docs lineage graph.

Doubles as a smoke test: it fails if any page shows a Streamlit exception.

    uv sync --group screenshots && uv run playwright install chromium   # once
    make screenshots                                                    # starts the app itself
    uv run --group screenshots python scripts/take_screenshots.py --url http://localhost:8501  # app already running
"""
from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "docs" / "images"
PAGES = [
    ("", "app_1_overview"),  # the default page lives at the root URL
    ("raw-data-issues", "app_2_raw_data_issues"),
    ("model-lineage", "app_3_model_lineage"),
    ("test-results", "app_4_test_results"),
    ("business-questions", "app_5_business_questions"),
    ("dashboard", "app_6_dashboard"),
    ("analyst-guide", "app_7_analyst_guide"),
]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_page(page, timeout_s: float = 60) -> None:
    """Wait until Streamlit has finished running the script and the charts have drawn."""
    page.wait_for_selector('[data-testid="stAppViewContainer"]', timeout=timeout_s * 1000)
    deadline, stable, last = time.time() + timeout_s, 0, -1
    while time.time() < deadline:
        running = page.locator('[data-testid="stStatusWidget"]').count()
        charts = page.locator(".js-plotly-plot .main-svg").count()
        stable = stable + 1 if (charts == last and not running) else 0
        last = charts
        if stable >= 4:
            return
        page.wait_for_timeout(500)


def full_height(page) -> int:
    return page.evaluate(
        """() => {
            const main = document.querySelector('[data-testid="stMain"]') || document.scrollingElement;
            return Math.max(main.scrollHeight, document.body.scrollHeight);
        }"""
    )


def shoot_app(url: str, width: int = 1440) -> list[str]:
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": 1000}, device_scale_factor=1)
        for path, name in PAGES:
            page.goto(f"{url}/{path}")
            wait_for_page(page)
            exceptions = page.locator('[data-testid="stException"]')
            if exceptions.count():
                errors.append(f"{path}: {exceptions.first.inner_text()[:500]}")
            height = min(full_height(page) + 40, 9000)
            page.set_viewport_size({"width": width, "height": height})
            page.wait_for_timeout(1500)
            page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
            page.set_viewport_size({"width": width, "height": 1000})
            print(f"  {name}.png ({height}px)")
        browser.close()
    return errors


def shoot_lineage() -> None:
    docs = REPO_ROOT / "dbt" / "target" / "static_index.html"
    if not docs.exists():
        print("  skipped dbt lineage: run `make docs` first")
        return
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1700, "height": 1000}, device_scale_factor=2)
        # models, sources and seeds that feed the two exposures (tests and metrics left out for readability)
        select = "%2Bexposure:streamlit_analytics_app%20%2Bexposure:business_question_analyses"
        page.goto(f"{docs.as_uri()}#!/overview?g_v=1&g_i={select}")
        page.wait_for_timeout(7000)
        page.screenshot(path=str(OUT / "dbt_lineage.png"))
        browser.close()
    print("  dbt_lineage.png")


REPORT_FIGURES = {
    "fig-three": "chart_three_analysts", "fig-paths": "chart_query_paths", "fig-q1a": "chart_q1_late_vs_on_time",
    "fig-q1c": "chart_q1_states", "fig-q2a": "chart_q2_definitions", "fig-q3a": "chart_q3_pareto",
    "fig-q3b": "chart_q3_handover",
}


def shoot_report_figures() -> None:
    """Cut the README's key charts out of reports/report.html, so they are identical to the report and app."""
    report = REPO_ROOT / "reports" / "report.html"
    if not report.exists():
        print("  skipped report charts: run `make report` first")
        return
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1100, "height": 1200}, device_scale_factor=2)
        page.goto(report.as_uri())
        page.wait_for_timeout(3000)
        # full-width figures for the README: collapse the report's two-column grids, let plotly re-layout
        page.add_style_tag(content=".grid2 { grid-template-columns: 1fr !important; }")
        page.evaluate("window.dispatchEvent(new Event('resize'))")
        page.wait_for_timeout(1500)
        for element_id, name in REPORT_FIGURES.items():
            element = page.locator(f"#{element_id}")
            element.scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            element.screenshot(path=str(OUT / f"{name}.png"))
            print(f"  {name}.png")
        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", help="Use an app that is already running instead of starting one.")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    server = None
    url = args.url
    if not url:
        port = free_port()
        server = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "dashboard/app.py", "--server.port", str(port),
             "--server.headless", "true"], cwd=REPO_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        url = f"http://localhost:{port}"
        time.sleep(4)
    try:
        print("dbt docs lineage:")
        shoot_lineage()
        print("report charts:")
        shoot_report_figures()
        print("app pages:")
        errors = shoot_app(url)
    finally:
        if server:
            server.terminate()
    if errors:
        print("\nPages with errors:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    print("All pages rendered without errors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
