from pathlib import Path

from streamlit.testing.v1 import AppTest


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


def test_streamlit_app_starts_without_exceptions():
    app_file = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_file), default_timeout=15).run()
    assert not app.exception


def test_all_navigation_pages_render_without_exceptions():
    app_file = Path(__file__).resolve().parents[1] / "app.py"

    for page in PAGES:
        app = AppTest.from_file(str(app_file), default_timeout=15)
        # Set the keyed radio state before the first run. This avoids relying
        # on positional access (app.radio[0]), which can raise IndexError
        # when Streamlit's test element collection is empty or changes order.
        app.session_state["main_navigation"] = page
        app.run()
        assert not app.exception, f"Page failed to render: {page}"
        assert app.session_state["main_navigation"] == page
