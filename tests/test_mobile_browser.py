import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    "داشبورد",
    "تحلیل بازار",
    "آزمایشگاه استراتژی",
    "مرکز سیگنال‌ها",
    "شکار توکن‌های DEX",
    "مرکز یادگیری",
    "سرمایه‌گذاری مشارکتی (آزمایشی)",
    "اتصالات",
    "تنظیمات و راهنما",
]


@pytest.fixture(scope="module")
def running_app():
    process = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
            "--server.headless", "true", "--server.address", "127.0.0.1",
            "--server.port", "8765", "--browser.gatherUsageStats", "false",
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    base_url = "http://127.0.0.1:8765"
    deadline = time.time() + 45
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Streamlit exited before becoming ready")
        try:
            with urllib.request.urlopen(base_url, timeout=2):
                break
        except Exception:
            time.sleep(0.5)
    else:
        process.terminate()
        raise RuntimeError("Streamlit did not become ready within 45 seconds")
    yield base_url
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


@pytest.mark.parametrize("width", [320, 375, 390, 430])
def test_mobile_viewports_render_all_pages_without_horizontal_overflow(running_app, width):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": 844}, device_scale_factor=1)
        page.goto(running_app, wait_until="domcontentloaded", timeout=30000)
        page.get_by_text("NEXUS AI TRADER").first.wait_for(timeout=20000)

        # Streamlit collapses its sidebar on narrow viewports. Open it before
        # interacting with navigation items so the test exercises real mobile UI.
        sidebar_toggle = page.locator('[data-testid="stSidebarCollapsedControl"]')
        if sidebar_toggle.count() and sidebar_toggle.first.is_visible():
            sidebar_toggle.first.click(timeout=8000)
            page.locator('[data-testid="stSidebar"]').wait_for(state="visible", timeout=8000)

        sidebar = page.locator('[data-testid="stSidebar"]')
        for page_name in PAGES:
            # Target the actual accessible radio control, not its inner <p>
            # text node (which can be outside the viewport in Streamlit's
            # narrow-screen sidebar drawer).
            nav_item = sidebar.get_by_role("radio", name=page_name)
            nav_item.wait_for(state="visible", timeout=8000)
            nav_item.click(timeout=8000)
            page.wait_for_timeout(250)
            dimensions = page.evaluate(
                "() => ({viewport: window.innerWidth, document: document.documentElement.scrollWidth, body: document.body.scrollWidth})"
            )
            assert dimensions["document"] <= dimensions["viewport"] + 2, (
                f"Horizontal overflow at {width}px on {page_name}: {dimensions}"
            )
            assert dimensions["body"] <= dimensions["viewport"] + 2, (
                f"Body overflow at {width}px on {page_name}: {dimensions}"
            )
        browser.close()
