from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_app_starts_without_exceptions():
    app_file = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_file), default_timeout=15).run()
    assert not app.exception



def test_all_navigation_pages_render_without_exceptions():
    pages = [
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
    for page in pages:
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / "app.py"),
            default_timeout=15,
        )
        app.run()
        app.radio[0].set_value(page).run()
        assert not app.exception, f"Page failed to render: {page}"
