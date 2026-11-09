import streamlit as st
import pandas as pd
from nexus.market_data import fetch_ohlcv
from nexus.indicators import add_indicators
from nexus.strategies import ema_rsi_signals, backtest
from nexus.dex import search_pairs
from nexus.paper import PaperWallet
from nexus.knowledge import save_note, load_notes

st.set_page_config(page_title="NEXUS AI TRADER", page_icon="📈", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;800&display=swap');
html, body, [class*="css"] {font-family: Vazirmatn, sans-serif;}
.block-container {direction: rtl; text-align: right;}
[data-testid="stSidebar"] {direction: rtl;}
</style>
""", unsafe_allow_html=True)
st.title("🚀 NEXUS AI TRADER")
st.caption("نسخه آزمایشی 0.2 | تحلیل بازار، آزمایش استراتژی و معاملات مجازی")
pages = ["داشبورد", "تحلیل بازار", "آزمایشگاه استراتژی", "مرکز سیگنال‌ها",
         "شکار توکن‌های DEX", "مرکز یادگیری", "اتصالات", "تنظیمات و راهنما"]
page = st.sidebar.radio("بخش‌ها", pages)

if "wallet" not in st.session_state:
    st.session_state.wallet = PaperWallet()
if "notes" not in st.session_state:
    st.session_state.notes = load_notes()

if page == "داشبورد":
    st.subheader("داشبورد")
    a, b, c = st.columns(3)
    a.metric("نسخه", "0.2")
    b.metric("حالت", "Paper Trading")
    c.metric("سرمایه مجازی", f"{st.session_state.wallet.cash:,.2f} USDT")
    st.info("این نسخه MVP است؛ پیش از استفاده مالی، نتایج را مستقل بررسی کنید.")
    st.write("از منوی کناری برای دریافت داده بازار، بک‌تست و بررسی جفت‌ارزهای DEX استفاده کنید.")

elif page == "تحلیل بازار":
    st.subheader("تحلیل بازار")
    exchange = st.selectbox("صرافی", ["binance", "okx", "bybit"])
    symbol = st.text_input("نماد", "BTC/USDT")
    timeframe = st.selectbox("تایم‌فریم", ["15m", "1h", "4h", "1d"], index=1)
    limit = st.slider("تعداد کندل", 100, 1000, 300, 50)
    if st.button("دریافت و تحلیل", type="primary"):
        try:
            df = add_indicators(fetch_ohlcv(exchange, symbol, timeframe, limit))
            st.dataframe(df.tail(30), use_container_width=True)
            last = df.iloc[-1]
            st.metric("آخرین قیمت بسته‌شدن", f"{last['close']:.6g}")
            st.metric("RSI", f"{last['rsi']:.2f}")
            st.write(f"EMA20: {last['ema20']:.6g} | EMA50: {last['ema50']:.6g}")
        except Exception as e:
            st.error(f"دریافت داده ناموفق بود: {e}")

elif page == "آزمایشگاه استراتژی":
    st.subheader("آزمایشگاه استراتژی")
    exchange = st.selectbox("صرافی", ["binance", "okx", "bybit"], key="bt_ex")
    symbol = st.text_input("نماد", "BTC/USDT", key="bt_symbol")
    timeframe = st.selectbox("تایم‌فریم", ["15m", "1h", "4h", "1d"], index=1, key="bt_tf")
    fee = st.number_input("کارمزد هر سمت (%)", 0.0, 1.0, 0.1, 0.01) / 100
    slippage = st.number_input("لغزش هر سمت (%)", 0.0, 1.0, 0.05, 0.01) / 100
    if st.button("اجرای بک‌تست"):
        try:
            df = add_indicators(fetch_ohlcv(exchange, symbol, timeframe, 500))
            signals = ema_rsi_signals(df)
            result = backtest(df, signals, fee, slippage)
            st.json(result)
            st.caption("این بک‌تست نمونه و ساده است؛ آزمون خارج از نمونه و walk-forward کامل نیست.")
        except Exception as e:
            st.error(str(e))

elif page == "مرکز سیگنال‌ها":
    st.subheader("مرکز سیگنال‌ها")
    st.warning("سیگنال‌های این نسخه آموزشی‌اند و توصیه مالی نیستند.")
    exchange = st.selectbox("صرافی", ["binance", "okx", "bybit"], key="sig_ex")
    symbol = st.text_input("نماد", "BTC/USDT", key="sig_symbol")
    if st.button("بررسی سیگنال"):
        try:
            df = add_indicators(fetch_ohlcv(exchange, symbol, "1h", 200))
            sig = ema_rsi_signals(df).iloc[-1]
            st.write("وضعیت:", "BUY" if sig else "NO TRADE")
            st.write("زمان کندل:", str(df.iloc[-1]["timestamp"]))
            st.write("استراتژی: EMA20/EMA50 + RSI")
        except Exception as e:
            st.error(str(e))

elif page == "شکار توکن‌های DEX":
    st.subheader("جست‌وجوی جفت‌ارزهای DEX")
    q = st.text_input("نام توکن یا نماد", "TON")
    if st.button("جست‌وجو"):
        try:
            rows = search_pairs(q)
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True)
            else:
                st.info("نتیجه‌ای پیدا نشد.")
        except Exception as e:
            st.error(str(e))
    st.caption("این ابزار فقط اطلاعات عمومی بازار را نمایش می‌دهد و قرارداد را audit یا honeypot را تشخیص نمی‌دهد.")

elif page == "مرکز یادگیری":
    st.subheader("دفترچه یادگیری")
    title = st.text_input("عنوان یادداشت")
    body = st.text_area("خلاصه آموزش یا استراتژی")
    if st.button("ذخیره یادداشت"):
        if title.strip() and body.strip():
            save_note(title, body)
            st.success("یادداشت ذخیره شد.")
        else:
            st.warning("عنوان و متن را وارد کنید.")
    for note in load_notes():
        with st.expander(note["title"]):
            st.write(note["body"])

elif page == "اتصالات":
    st.subheader("اتصالات")
    st.info("اتصال حساب صرافی، WalletConnect و اجرای سفارش واقعی هنوز پیاده‌سازی نشده‌اند.")
    st.write("هرگز عبارت بازیابی (seed phrase) یا کلید خصوصی را در این برنامه وارد نکنید.")
    st.write("در نسخه‌های بعدی، API فقط با مجوزهای محدود و بدون برداشت قابل بررسی است.")

elif page == "تنظیمات و راهنما":
    st.subheader("تنظیمات و راهنما")
    st.markdown("""
- این نسخه صرفاً MVP آزمایشی است.
- داده‌ها از API عمومی صرافی‌ها دریافت می‌شوند و به اینترنت نیاز دارند.
- سیگنال EMA/RSI یک نمونه آموزشی است، نه هوش مصنوعی پیشرفته.
- بک‌تست فعلی ساده است و تضمین سودآوری یا نرخ برد مشخص نمی‌دهد.
- اسکن DEX بررسی امنیت قرارداد نیست.
- یادگیری خودکار از YouTube و Telegram هنوز فعال نیست.
- معاملات واقعی و اتصال کیف پول/حساب صرافی هنوز ساخته نشده‌اند.
- ابتدا فقط با پول مجازی آزمایش کنید.
""")
