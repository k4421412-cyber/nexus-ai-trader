import os
import json
from datetime import datetime, timezone
import streamlit as st
import pandas as pd
from nexus.market_data import fetch_ohlcv
from nexus.indicators import add_indicators
from nexus.strategies import ema_rsi_signals, backtest, compare_strategies
from nexus.dex import search_pairs
from nexus.paper import PaperWallet
from nexus.knowledge import save_note, load_notes
from nexus.social_investment import SimulatedInvestmentPool

st.set_page_config(page_title="NEXUS AI TRADER", page_icon="📈", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;800&display=swap');
html, body, [class*="css"] {font-family: Vazirmatn, sans-serif;}
[data-testid="stAppViewContainer"] {background:radial-gradient(ellipse at 12% 0%,rgba(34,211,238,.16),transparent 38%),linear-gradient(135deg,#0b1220 0%,#111b31 55%,#17233d 100%);}
[data-testid="stSidebar"] {background:linear-gradient(180deg,#101a2d,#17243d);border-left:1px solid rgba(34,211,238,.25);}
[data-testid="stMetric"] {background:rgba(22,36,59,.82);border:1px solid rgba(34,211,238,.22);padding:14px;border-radius:14px;}
.stButton button {border-radius:10px;border:1px solid rgba(34,211,238,.45);background:linear-gradient(110deg,#0e7490,#4f46e5);color:white;font-weight:700;}
.block-container {direction: rtl; text-align: right; max-width: 100%; padding-left: 1rem; padding-right: 1rem;}
[data-testid="stSidebar"] {direction: rtl;}
[data-testid="stDataFrame"], [data-testid="stTable"] {max-width: 100%; overflow-x: auto;}
.stButton button, [data-testid="stDownloadButton"] button {min-height: 44px;}
@media (max-width: 640px) {
  .block-container {padding-left: 0.65rem; padding-right: 0.65rem;}
  [data-testid="stMetric"] {overflow-wrap: anywhere;}
  h1 {font-size: 1.65rem;}
}
</style>
""", unsafe_allow_html=True)
st.title("🚀 NEXUS AI TRADER")
st.caption("نسخه آزمایشی 0.2 | تحلیل بازار، آزمایش استراتژی و معاملات مجازی")
pages = ["داشبورد", "تحلیل بازار", "آزمایشگاه استراتژی", "مرکز سیگنال‌ها",
         "شکار توکن‌های DEX", "مرکز یادگیری", "سرمایه‌گذاری مشارکتی (آزمایشی)", "اتصالات", "تنظیمات و راهنما"]
page = st.sidebar.radio("بخش‌ها", pages)

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
            st.dataframe(df.tail(30), width="stretch")
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

    st.markdown("### مقایسه خودکار استراتژی‌ها")
    st.caption("پنج روش ثابت با داده، کارمزد و لغزش یکسان آزمایش می‌شوند؛ پارامترها روی داده آینده تنظیم نمی‌شوند.")
    if st.button("🚀 اجرای مقایسه خودکار ۵ استراتژی", type="primary"):
        try:
            auto_df = add_indicators(fetch_ohlcv(exchange, symbol, timeframe, 1000))
            reports = compare_strategies(auto_df, fee=fee, slippage=slippage)
            st.session_state["auto_strategy_reports"] = reports
            st.session_state["auto_strategy_meta"] = {
                "exchange": exchange.upper(), "requested_symbol": symbol.upper(),
                "resolved_symbol": auto_df.attrs.get("resolved_symbol", symbol.strip()),
                "timeframe": timeframe, "candles": len(auto_df),
                "fee_per_side_pct": fee * 100, "slippage_per_side_pct": slippage * 100,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            st.session_state["auto_strategy_report_payload"] = {
                "project": "NEXUS AI TRADER", "report_type": "automatic_strategy_comparison",
                "metadata": st.session_state["auto_strategy_meta"], "results": reports,
                "notice": "Historical simulation only; not financial advice or a guarantee of future returns."
            }
        except Exception as e:
            st.error(f"مقایسه خودکار انجام نشد: {e}")

    if st.session_state.get("auto_strategy_reports"):
        meta = st.session_state.get("auto_strategy_meta", {})
        st.caption(
            f"بازار: {meta.get('exchange')} | نماد درخواستی: {meta.get('requested_symbol')} | "
            f"نماد استاندارد: {meta.get('resolved_symbol')} | تایم‌فریم: {meta.get('timeframe')} | "
            f"کندل: {meta.get('candles')} | زمان UTC: {meta.get('generated_at_utc')}"
        )
        rows = [{
            "استراتژی": x["strategy"],
            "بازده پس از هزینه خروج (%)": x["estimated_liquidation_return_pct"],
            "معاملات بسته‌شده": x["closed_trade_count"],
            "نرخ برد (%)": x["win_rate_pct"],
            "Profit Factor": x["profit_factor"],
            "افت سرمایه (%)": x["max_drawdown_pct"],
            "امید ریاضی (USDT)": x["expectancy_per_closed_trade"],
        } for x in st.session_state["auto_strategy_reports"]]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        eligible = [x for x in st.session_state["auto_strategy_reports"] if x["closed_trade_count"] >= 10]
        if eligible:
            best = eligible[0]
            st.success("بهترین نتیجه موقت با حداقل ۱۰ معامله: " + best["strategy"])
        else:
            st.warning("هیچ استراتژی حداقل ۱۰ معامله بسته‌شده ندارد؛ نتیجه فعلاً برای انتخاب نهایی کافی نیست.")
        st.caption("این رتبه‌بندی غربال اولیه است؛ آزمون خارج از نمونه و walk-forward هنوز لازم است.")
        report_json = json.dumps(st.session_state["auto_strategy_report_payload"], ensure_ascii=False, indent=2, default=str)
        st.download_button(
            "📥 دریافت گزارش کامل برای بررسی",
            data=report_json.encode("utf-8"),
            file_name="nexus_strategy_report.json",
            mime="application/json",
            use_container_width=True,
        )
        if st.button("📋 آماده‌سازی خلاصه برای ارسال در گفتگو"):
            summary_lines = [
                "NEXUS AI TRADER — گزارش مقایسه استراتژی‌ها",
                f"بازار: {meta.get('exchange')} | نماد: {meta.get('resolved_symbol')} | تایم‌فریم: {meta.get('timeframe')}",
                f"کندل‌ها: {meta.get('candles')} | زمان UTC: {meta.get('generated_at_utc')}",
            ]
            for item in st.session_state["auto_strategy_reports"]:
                summary_lines.append(
                    f"{item['strategy']}: بازده خروج {item['estimated_liquidation_return_pct']}%، "
                    f"معاملات {item['closed_trade_count']}، برد {item['win_rate_pct']}%، "
                    f"افت سرمایه {item['max_drawdown_pct']}%، PF {item['profit_factor']}"
                )
            st.code("\\n".join(summary_lines), language="text")
            st.info("این خلاصه را کپی کن و در همین گفتگو بفرست تا نتایج را بررسی کنم.")


    if st.button("اجرای بک‌تست"):
        try:
            df = add_indicators(fetch_ohlcv(exchange, symbol, timeframe, 300))
            signals = ema_rsi_signals(df)
            result = backtest(df, signals, fee, slippage)
            resolved_symbol = df.attrs.get("resolved_symbol", symbol.strip())
            st.markdown("### نتیجه بک‌تست")
            st.caption(
                f"بازار: {exchange.upper()} | نماد درخواستی: {symbol.upper()} | "
                f"نماد استاندارد: {resolved_symbol.upper()} | "
                f"تایم‌فریم: {timeframe} | تعداد کندل دریافت‌شده: {len(df)}"
            )

            m1, m2, m3 = st.columns(3)
            m1.metric("ارزش نهایی", f"{result['final_balance']:,.2f} USDT")
            m2.metric("بازده خالص", f"{result['net_return_pct']:.2f}%")
            m3.metric("تعداد معاملات بسته‌شده", result["closed_trade_count"])

            d1, d2, d3, d4 = st.columns(4)
            d1.metric("سیگنال‌های ورود قابل اجرا", result["entry_signal_count"])
            d2.metric("شرط‌های خروج مشاهده‌شده", result["exit_condition_count"])
            d3.metric("ورودهای اجراشده", result["executed_entry_count"])
            d4.metric("خروج‌های اجراشده", result["executed_exit_count"])
            if result["closed_trade_count"] == 0:
                if result["open_position"]:
                    st.warning("سیگنال ورود اجرا شده، اما موقعیت تا پایان بازه بسته نشده است؛ نتیجه نهایی هنوز قطعی نیست.")
                elif result["entry_signal_count"] == 0:
                    st.warning("در این بازه هیچ سیگنال ورود قابل اجرایی تولید نشده است. این وضعیت به معنی سود یا زیان صفرِ یک استراتژیِ اثبات‌شده نیست.")
                else:
                    st.warning("سیگنال ورود وجود داشته، اما معامله بسته‌شده‌ای ثبت نشده است؛ جزئیات اجرای سفارش را بررسی کنید.")

            m4, m5, m6 = st.columns(3)
            m4.metric("نرخ برد", f"{result['win_rate_pct']:.2f}%")
            m5.metric("بیشترین افت سرمایه", f"{result['max_drawdown_pct']:.2f}%")
            pf = result["profit_factor"]
            m6.metric("Profit Factor", str(pf) if pf is not None else "—")

            m7, m8, m9 = st.columns(3)
            m7.metric("ارزش برآوردی پس از خروج", f"{result['estimated_liquidation_balance']:,.2f} USDT")
            m8.metric("بازده پس از هزینه خروج", f"{result['estimated_liquidation_return_pct']:.2f}%")
            expectancy = result["expectancy_per_closed_trade"]
            m9.metric("امید ریاضی هر معامله", f"{expectancy:,.2f} USDT" if expectancy is not None else "—")

            st.markdown("#### نمودار ارزش سرمایه")
            equity = pd.DataFrame({
                "شماره کندل": range(len(result["equity_curve"])),
                "ارزش سرمایه (USDT)": result["equity_curve"],
            }).set_index("شماره کندل")
            st.line_chart(equity, use_container_width=True)

            if result["open_position"]:
                st.info(
                    f"در پایان بازه یک موقعیت باز وجود دارد؛ "
                    f"تعداد واحد: {result['open_position_units']} | "
                    f"ارزش برآوردی پس از کارمزد و لغزش خروج: "
                    f"{result['estimated_liquidation_balance']:,.2f} USDT"
                )
            else:
                st.caption("در پایان بازه موقعیت بازی وجود ندارد.")

            st.markdown("#### جزئیات معاملات بسته‌شده")
            if result["closed_trades"]:
                trades = pd.DataFrame(result["closed_trades"])
                trades.index = range(1, len(trades) + 1)
                trades.index.name = "معامله"
                st.dataframe(trades, use_container_width=True)
            else:
                st.info("در بازه انتخاب‌شده هیچ معامله‌ای بسته نشده است.")

            st.caption(
                "کارمزد و لغزش ورود و خروج معاملات بسته‌شده لحاظ شده‌اند؛ "
                "برای موقعیت باز نیز ارزش برآوردی پس از هزینه خروج جداگانه محاسبه شده است. "
                "این گزارش بک‌تست تاریخی است و سود آینده را تضمین نمی‌کند؛ "
                "آزمون خارج از نمونه و walk-forward هنوز کامل نشده است."
            )
        except Exception as e:
            st.error(str(e))

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
