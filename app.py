import os
import streamlit as st
import pandas as pd
from nexus.market_data import fetch_ohlcv
from nexus.indicators import add_indicators
from nexus.strategies import ema_rsi_signals, backtest
from nexus.strategy_lab import compare_all
from nexus.dex import search_pairs
from nexus.paper import PaperWallet
from nexus.knowledge import save_note, load_notes
from nexus.social_investment import SimulatedInvestmentPool

st.set_page_config(page_title="NEXUS AI TRADER", page_icon="📈", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], button, input, textarea {font-family:Vazirmatn,sans-serif;}
[data-testid="stAppViewContainer"] {background:radial-gradient(ellipse at 8% 0%,rgba(0,195,255,.18),transparent 34%),radial-gradient(ellipse at 92% 18%,rgba(139,92,246,.13),transparent 32%),linear-gradient(145deg,#030817 0%,#07142d 55%,#080d22 100%);color:#edf6ff;}
[data-testid="stHeader"] {background:rgba(3,8,23,.78);}
[data-testid="stSidebar"] {background:linear-gradient(180deg,#07152d,#0c1732);border-left:1px solid rgba(34,211,238,.3);}
.block-container {direction:rtl;text-align:right;max-width:1500px;padding:1.3rem 1.4rem 2rem;}
h1,h2,h3 {letter-spacing:-.35px;}
[data-testid="stMetric"] {background:linear-gradient(145deg,rgba(8,35,67,.95),rgba(10,19,47,.96));border:1px solid rgba(0,195,255,.48);border-radius:17px;padding:16px 18px;box-shadow:0 0 18px rgba(0,174,255,.09);min-height:108px;}
[data-testid="stMetricLabel"] {color:#a9c9e8;}
[data-testid="stMetricValue"] {color:#f5fbff;font-weight:800;}
.stButton button,[data-testid="stDownloadButton"] button {border-radius:12px;border:1px solid rgba(34,211,238,.65);background:linear-gradient(110deg,#075985,#4338ca);color:white;font-weight:700;min-height:44px;}
.stButton button:hover {border-color:#22d3ee;color:white;box-shadow:0 0 16px rgba(34,211,238,.25);}
[data-testid="stDataFrame"],[data-testid="stTable"] {max-width:100%;overflow-x:auto;}
[data-testid="stAlert"] {border-radius:14px;}
[data-testid="stRadio"] > label {display:none;}
[data-testid="stRadio"] > div {gap:7px;flex-wrap:wrap;}
[data-testid="stRadio"] label {background:rgba(9,29,61,.9);border:1px solid rgba(34,211,238,.28);border-radius:12px;padding:8px 13px;margin:0;color:#e8f5ff;}
[data-testid="stRadio"] label:has(input:checked) {background:linear-gradient(110deg,rgba(3,155,220,.42),rgba(79,70,229,.45));border-color:#22d3ee;box-shadow:0 0 12px rgba(34,211,238,.2);}
.nexus-hero {padding:18px 20px;border:1px solid rgba(34,211,238,.5);border-radius:20px;background:linear-gradient(110deg,rgba(5,29,62,.96),rgba(21,20,62,.92));box-shadow:0 0 24px rgba(0,174,255,.12);margin:4px 0 18px;}
.nexus-kicker {color:#36d9f5;font-size:.82rem;font-weight:700;letter-spacing:1.1px;}
.nexus-sub {color:#aac4e4;font-size:.94rem;margin-top:5px;}
.nexus-panel {border:1px solid rgba(34,211,238,.35);border-radius:17px;padding:15px 17px;background:rgba(7,22,48,.82);margin:8px 0 14px;}
.nexus-muted {color:#a9c4e2;font-size:.9rem;}
@media (max-width:768px) {
 [data-testid="stSidebar"] {display:none;}
 [data-testid="stRadio"] {position:relative;z-index:1;background:rgba(3,10,27,.94);border:1px solid rgba(34,211,238,.42);border-radius:15px;padding:7px;margin:10px 0 18px;box-shadow:0 5px 18px rgba(0,0,0,.22);}
 [data-testid="stRadio"] > div {display:flex;flex-wrap:nowrap;overflow-x:auto;justify-content:flex-start;gap:6px;scrollbar-width:thin;padding-bottom:3px;}
 [data-testid="stRadio"] > div::-webkit-scrollbar {height:4px;}
 [data-testid="stRadio"] label {flex:0 0 auto;padding:9px 12px;font-size:.8rem;white-space:nowrap;}
 .block-container {padding:1rem .7rem 2rem;}
 h1 {font-size:1.55rem!important;} h2 {font-size:1.25rem!important;}
 [data-testid="stHorizontalBlock"] {flex-wrap:wrap;gap:.55rem;}
 [data-testid="stHorizontalBlock"] > [data-testid="column"] {flex:1 1 calc(50% - .55rem)!important;min-width:calc(50% - .55rem)!important;}
 [data-testid="stMetric"] {padding:12px;min-height:92px;}
 [data-testid="stMetricValue"] {font-size:1.25rem;}
 .nexus-hero {padding:15px;border-radius:16px;}
}
@media (max-width:420px) {
 [data-testid="stHorizontalBlock"] > [data-testid="column"] {flex:1 1 100%!important;min-width:100%!important;}
}
</style>
""", unsafe_allow_html=True)
st.markdown("""
<div class="nexus-hero" style="margin-top:0">
  <div class="nexus-kicker">NEXUS AI TRADER</div>
  <h1 style="margin:4px 0;color:#f4fbff;">معاملات هوشمند، با کنترل کامل</h1>
  <div class="nexus-sub">نسخه آزمایشی 0.3 · تحلیل بازار و معاملات مجازی</div>
</div>
""", unsafe_allow_html=True)
pages = ["داشبورد", "تحلیل بازار", "آزمایشگاه استراتژی", "مرکز سیگنال‌ها",
         "شکار توکن‌های DEX", "مرکز یادگیری", "سرمایه‌گذاری مشارکتی (آزمایشی)", "اتصالات", "تنظیمات و راهنما"]
page = st.radio("بخش‌ها", pages, horizontal=True, label_visibility="collapsed", key="main_navigation")

if "wallet" not in st.session_state:
    st.session_state.wallet = PaperWallet()
if "notes" not in st.session_state:
    st.session_state.notes = load_notes()
def create_investment_pool(manager_share=None):
    ledger_key = os.environ.get("NEXUS_LEDGER_KEY")
    if ledger_key:
        ledger_path = os.environ.get("NEXUS_LEDGER_PATH", "data/investment-ledger.enc")
        return SimulatedInvestmentPool(
            manager_profit_share_bps=manager_share,
            ledger_path=ledger_path,
            encryption_key=ledger_key,
        )
    return SimulatedInvestmentPool(manager_profit_share_bps=manager_share)


if "investment_pool" not in st.session_state:
    st.session_state.investment_pool = create_investment_pool()

if page == "داشبورد":
    st.markdown("""
    <div class="nexus-panel" style="display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;">
      <div><div class="nexus-kicker">CONTROL CENTER</div><h2 style="margin:3px 0;color:#f4fbff;">داشبورد اصلی</h2><div class="nexus-muted">نمای کلی وضعیت حساب آزمایشی و ابزارهای معاملاتی</div></div>
      <div style="border:1px solid #10b981;color:#6ee7b7;border-radius:30px;padding:7px 13px;font-weight:700;">● حالت آزمایشی</div>
    </div>
    """, unsafe_allow_html=True)
    wallet = st.session_state.wallet
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("موجودی نقد مجازی", f"{wallet.cash:,.2f} USDT")
    m2.metric("موقعیت‌های باز", str(len(wallet.positions)))
    m3.metric("حالت اجرا", "Paper Trading")
    m4.metric("نسخه برنامه", "0.3 آزمایشی")
    st.markdown("### وضعیت سامانه")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="nexus-panel"><b style="color:#22d3ee;">● محیط آزمایشی فعال</b><p class="nexus-muted">سفارش‌ها در این نسخه با موجودی مجازی ثبت می‌شوند؛ هیچ سفارش واقعی به صرافی ارسال نمی‌شود.</p></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="nexus-panel"><b style="color:#fbbf24;">● اتصال صرافی‌ها</b><p class="nexus-muted">اتصال حساب و ارسال سفارش واقعی هنوز پیاده‌سازی نشده است. داده بازار فقط از API عمومی دریافت می‌شود.</p></div>', unsafe_allow_html=True)
    st.markdown("### دارایی‌های مجازی")
    if wallet.positions:
        positions_df = pd.DataFrame([{"نماد": symbol, "مقدار": quantity} for symbol, quantity in wallet.positions.items()])
        st.dataframe(positions_df, use_container_width=True, hide_index=True)
    else:
        st.info("هنوز موقعیت مجازی بازی وجود ندارد. برای شروع، از بخش تحلیل بازار داده دریافت کنید و استراتژی‌ها را در آزمایشگاه بررسی کنید.")
    st.markdown("### ابزارهای اصلی")
    for title, description in [
        ("📊 تحلیل بازار", "قیمت، اندیکاتورها و داده کندل‌ها"),
        ("🧪 آزمایشگاه استراتژی", "بک‌تست با احتساب کارمزد و لغزش"),
        ("⚡ مرکز سیگنال‌ها", "بررسی سیگنال‌های آموزشی"),
    ]:
        st.markdown('<div class="nexus-panel"><b>' + title + '</b><div class="nexus-muted">' + description + '</div></div>', unsafe_allow_html=True)

elif page == "تحلیل بازار":
    st.subheader("تحلیل بازار")
    exchange = st.selectbox("صرافی", ["binance", "okx", "bybit"])
    symbol = st.text_input("نماد", "BTC/USDT")
    timeframe = st.selectbox("تایم‌فریم", ["15m", "1h", "4h", "1d"], index=1)
    limit = st.slider("تعداد کندل", 100, 1000, 300, 50)
    if st.button("دریافت و تحلیل", type="primary"):
        try:
            df = add_indicators(fetch_ohlcv(exchange, symbol, timeframe, limit))
            st.dataframe(df.tail(30), width="stretch")
            last = df.iloc[-1]
            st.metric("آخرین قیمت بسته‌شدن", f"{last['close']:.6g}")
            st.metric("RSI", f"{last['rsi']:.2f}")
            st.write(f"EMA20: {last['ema20']:.6g} | EMA50: {last['ema50']:.6g}")
        except Exception as e:
            st.error(f"دریافت داده ناموفق بود: {e}")

elif page == "آزمایشگاه استراتژی":
    st.subheader("آزمایشگاه خودکار استراتژی‌ها")
    st.caption("۱۱ روش معاملاتی روی داده تاریخی یکسان مقایسه می‌شوند؛ همه سفارش‌ها شبیه‌سازی هستند.")
    exchange = st.selectbox("صرافی داده بازار", ["okx", "binance", "bybit"], key="auto_bt_ex")
    symbol = st.text_input("نماد معاملاتی", "BTC/USDT", key="auto_bt_symbol")
    timeframe = st.selectbox("تایم‌فریم", ["15m", "1h", "4h", "1d"], index=1, key="auto_bt_tf")
    candle_limit = st.slider("تعداد کندل تاریخی", 300, 1500, 1000, 100, key="auto_bt_limit")
    col1, col2 = st.columns(2)
    fee = col1.number_input("کارمزد هر سمت (%)", 0.0, 1.0, 0.1, 0.01, key="auto_bt_fee") / 100
    slippage = col2.number_input("لغزش هر سمت (%)", 0.0, 1.0, 0.05, 0.01, key="auto_bt_slip") / 100
    initial_balance = st.number_input("سرمایه اولیه مجازی (USDT)", 100.0, 100000.0, 1000.0, 100.0, key="auto_bt_balance")
    if st.button("🚀 آزمایش همه استراتژی‌ها", type="primary", use_container_width=True):
        try:
            with st.spinner("دریافت داده و اجرای بک‌تست ۱۱ استراتژی..."):
                market = add_indicators(fetch_ohlcv(exchange, symbol, timeframe, candle_limit))
                results = compare_all(market, fee, slippage, initial_balance)
            st.session_state["strategy_lab_results"] = results
            st.session_state["strategy_lab_meta"] = {"exchange": exchange, "symbol": symbol, "timeframe": timeframe, "candles": len(market)}
            st.success(f"آزمایش {len(results)} استراتژی روی {len(market)} کندل انجام شد.")
        except Exception as exc:
            st.error(f"اجرای آزمایش ناموفق بود: {exc}")
    results = st.session_state.get("strategy_lab_results")
    if results:
        meta = st.session_state.get("strategy_lab_meta", {})
        qualified = [r for r in results if r.get("qualifies")]
        st.markdown("### خلاصه مقایسه")
        a, b, d = st.columns(3)
        a.metric("روش‌های آزمایش‌شده", len(results))
        b.metric("عبور از معیار اولیه", len(qualified))
        d.metric("حداقل معاملات لازم", "۱۰۰ معامله بسته")
        st.caption(f"بازار: {meta.get('exchange')} · {meta.get('symbol')} · {meta.get('timeframe')} · {meta.get('candles')} کندل")
        if qualified:
            st.success("حداقل یک استراتژی معیارهای اولیه را گذرانده؛ این نتیجه تأیید نهایی یا تضمین سود نیست.")
        else:
            st.warning("هیچ استراتژی همه معیارهای اولیه را نگذرانده است؛ هیچ روشی تأییدشده اعلام نمی‌شود.")
        rows = []
        for r in results:
            pf = r.get("profit_factor")
            pf_text = "بی‌نهایت" if pf == "infinite" else (f"{pf:.2f}" if isinstance(pf, (int, float)) else "—")
            rows.append({"استراتژی": r["strategy"], "معاملات بسته": r.get("trades", 0),
                         "نرخ برد (%)": round(r.get("win_rate_pct", 0), 2),
                         "بازده خالص (%)": round(r.get("net_return_pct", 0), 2),
                         "افت سرمایه (%)": round(r.get("max_drawdown_pct", 0), 2),
                         "Profit Factor": pf_text, "وضعیت": "قبول اولیه" if r.get("qualifies") else "تأییدنشده"})
        st.markdown("### جدول رتبه‌بندی")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        names = [r["strategy"] for r in results]
        selected_name = st.selectbox("جزئیات کدام استراتژی؟", names, key="strategy_lab_detail")
        selected = next(r for r in results if r["strategy"] == selected_name)
        st.markdown(f"#### {selected_name}")
        x1, x2, x3 = st.columns(3)
        x1.metric("بازده خالص", f'{selected.get("net_return_pct", 0):.2f}%')
        x2.metric("نرخ برد", f'{selected.get("win_rate_pct", 0):.2f}%')
        x3.metric("بیشترین افت سرمایه", f'{selected.get("max_drawdown_pct", 0):.2f}%')
        curve = pd.DataFrame({"شماره کندل": range(len(selected.get("equity_curve", []))), "ارزش حساب (USDT)": selected.get("equity_curve", [])}).set_index("شماره کندل")
        if not curve.empty:
            st.line_chart(curve, use_container_width=True)
        if selected.get("trade_log"):
            trades = pd.DataFrame(selected["trade_log"])
            trades.index = range(1, len(trades) + 1)
            trades.index.name = "معامله"
            st.dataframe(trades.tail(100), use_container_width=True)
        st.caption("معیار قبول اولیه: حداقل ۱۰۰ معامله بسته، نرخ برد حداقل ۸۰٪، بازده خالص و امید ریاضی مثبت، Profit Factor بالاتر از ۱. آزمون خارج از نمونه و walk-forward هنوز لازم است؛ ۱۰۰ معامله با ۱۰۰ آزمایش مستقل یکسان نیست.")
    else:
        st.info("برای شروع، نماد و تایم‌فریم را انتخاب کن و روی «آزمایش همه استراتژی‌ها» بزن.")

elif page == "مرکز سیگنال‌ها":
    st.subheader("مرکز سیگنال‌ها")
    st.info(
        "این بخش برای بررسی و ارزیابی دقت سیگنال‌های ربات NEXUS AI TRADER طراحی شده است. "
        "همچنین برای افرادی که از پلتفرم‌های مختلف بونوس دریافت کرده‌اند، کاربرد دارد."
    )
    st.warning("سیگنال‌های این نسخه آموزشی‌اند و توصیه مالی نیستند.")
    exchange = st.selectbox("صرافی", ["binance", "okx", "bybit"], key="sig_ex")
    symbol = st.text_input("نماد", "BTC/USDT", key="sig_symbol")
    if st.button("بررسی سیگنال"):
        try:
            df = add_indicators(fetch_ohlcv(exchange, symbol, "1h", 200))
            # The newest exchange candle may still be forming; use the last completed candle.
            closed_candle = df.iloc[-2]
            sig = ema_rsi_signals(df).iloc[-2]
            if sig:
                st.success("سیگنال فعلی: BUY")
            else:
                st.info("سیگنال فعلی: NO TRADE")
            st.write("زمان آخرین کندل بسته‌شده:", str(closed_candle["timestamp"]))
            st.write("استراتژی: EMA20/EMA50 + RSI")
            st.caption(
                "نسخه فعلی فقط سیگنال ورود خرید (Long) تولید می‌کند؛ "
                "NO TRADE به معنی نبود شرط ورود است، نه سیگنال فروش. "
                "برای جلوگیری از سیگنال ناپایدار، کندل در حال تشکیل استفاده نمی‌شود."
            )
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

elif page == "سرمایه‌گذاری مشارکتی (آزمایشی)":
    st.subheader("سرمایه‌گذاری مشارکتی و تقسیم سود — محیط شبیه‌سازی")
    st.warning(
        "این بخش فقط با اعداد مجازی کار می‌کند؛ هیچ واریز، برداشت، اتصال کیف پول یا معامله واقعی انجام نمی‌شود. "
        "زیان نیز مانند سود، متناسب با سهم سرمایه مجازی هر فرد تقسیم می‌شود."
    )
    pool = st.session_state.investment_pool
    if pool.persistent:
        st.success("دفترکل روی دیسک ذخیره و با Fernet رمزنگاری می‌شود.")
    else:
        st.warning("دفترکل فعلاً فقط در حافظه نشست است. برای ذخیره دائمی، NEXUS_LEDGER_KEY و NEXUS_LEDGER_PATH را در محیط سرور تنظیم کنید.")

    if not pool.investors and not pool.started:
        manager_options = sorted(set([0, 500, 1000, 1500, 2000, pool.manager_profit_share_bps]))
        manager_share = st.selectbox(
            "سهم مدیر از سود جدیدِ تحقق‌یافته",
            manager_options,
            index=manager_options.index(pool.manager_profit_share_bps),
            format_func=lambda value: f"{value / 100:.1f}%",
            key="pool_manager_share",
        )
        if st.button("ثبت تنظیم سهم مدیر"):
            try:
                pool.set_manager_profit_share(manager_share)
                st.success("تنظیمات استخر مجازی ثبت شد.")
            except ValueError as e:
                st.error(str(e))

    st.markdown("#### افزودن سرمایه‌گذار مجازی")
    st.caption("هر فرد فقط یک بار و پیش از اولین معامله شبیه‌سازی‌شده به این استخر اضافه می‌شود.")
    c1, c2 = st.columns(2)
    investor_id = c1.text_input("شناسه دلخواه سرمایه‌گذار", key="pool_investor_id")
    contribution = c2.number_input(
        "مبلغ سرمایه مجازی (USDT)", min_value=0.01, value=100.0, step=10.0,
        key="pool_contribution"
    )
    if st.button("افزودن سرمایه مجازی"):
        try:
            pool.add_investor(investor_id, contribution)
            st.success("سرمایه مجازی با موفقیت ثبت شد.")
        except (ValueError, KeyError) as e:
            st.error(str(e))

    if pool.investors:
        st.markdown("#### برداشت مجازی سرمایه‌گذار")
        withdrawal_investor = st.selectbox(
            "انتخاب سرمایه‌گذار برای برداشت مجازی",
            list(pool.investors.keys()),
            key="pool_withdrawal_investor",
        )
        withdrawal_amount = st.number_input(
            "مبلغ برداشت مجازی (USDT)", min_value=0.01, value=10.0, step=1.0,
            key="pool_withdrawal_amount",
        )
        if st.button("ثبت برداشت مجازی"):
            try:
                pool.withdraw_virtual(withdrawal_investor, withdrawal_amount)
                st.success("برداشت مجازی در دفترکل ثبت شد؛ هیچ پول واقعی جابه‌جا نشد.")
            except (ValueError, KeyError) as e:
                st.error(str(e))

    st.markdown("#### ثبت نتیجه معامله فرضی")
    st.caption("سود را مثبت و زیان را منفی وارد کنید؛ کارمزد معامله جداگانه از نتیجه کسر می‌شود.")
    c3, c4 = st.columns(2)
    realized_pnl = c3.number_input(
        "سود/زیان تحقق‌یافته فرضی (USDT)", value=0.0, step=1.0,
        key="pool_realized_pnl"
    )
    trading_fees = c4.number_input(
        "هزینه و کارمزد فرضی (USDT)", min_value=0.0, value=0.0, step=0.1,
        key="pool_trading_fees"
    )
    if st.button("ثبت نتیجه در دفترکل مجازی"):
        try:
            if realized_pnl == 0 and trading_fees == 0:
                st.error("نتیجه یا هزینه معامله باید غیرصفر باشد.")
            else:
                pool.record_trade(realized_pnl, trading_fees)
                st.success("نتیجه فرضی ثبت و بین سرمایه‌گذاران توزیع شد.")
        except (ValueError, KeyError) as e:
            st.error(str(e))

    report = pool.summary()
    st.markdown("#### خلاصه استخر")
    m1, m2, m3 = st.columns(3)
    m1.metric("تعداد سرمایه‌گذاران", report["investor_count"])
    m2.metric("کل سرمایه مجازی", f'{float(report["total_virtual_contributions"]):,.2f} USDT')
    m3.metric("سود/زیان خالص استخر", f'{float(report["pool_cumulative_net_pnl"]):,.2f} USDT')
    st.metric("موجودی مجازی فعلی پس از برداشت‌ها", f'{float(report["current_virtual_balance"]):,.2f} USDT')

    if report["investors"]:
        st.markdown("#### گزارش سهم هر سرمایه‌گذار")
        investor_rows = []
        for investor in report["investors"]:
            investor_rows.append({
                "سرمایه‌گذار": investor["investor_id"],
                "سهم از استخر (%)": float(investor["share_pct"]),
                "سرمایه اولیه مجازی": float(investor["contributed"]),
                "سود/زیان خالص": float(investor["net_pnl"]),
                "ارزش مجازی فعلی": float(investor["virtual_value"]),
            })
        st.dataframe(pd.DataFrame(investor_rows), use_container_width=True)

    st.markdown("#### دفترکل رویدادها")
    if pool.ledger:
        st.dataframe(pd.DataFrame(pool.ledger), use_container_width=True)
    st.caption(
        "محاسبات با Decimal انجام می‌شوند. سهم مدیر فقط از سود خالص جدید بالاتر از سقف قبلی "
        "(High-Water Mark) محاسبه می‌شود؛ بازیابی زیان قبلی دوباره مشمول سهم مدیر نیست. "
        "برای سادگی MVP، افزودن سرمایه جدید پس از اولین معامله و برداشت هنوز پشتیبانی نمی‌شود. "
        + ("دفترکل با رمزنگاری احرازاصالت‌شده Fernet ذخیره شده و زنجیره هش رویدادها نیز بررسی می‌شود."
           if pool.persistent else
           "ذخیره دائمی فعال نیست؛ با پایان نشست ممکن است اطلاعات از بین برود.")
    )

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
