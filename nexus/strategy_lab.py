import math
import numpy as np
import pandas as pd


def _indicators(df):
    x = df.copy()
    close = pd.to_numeric(x["close"], errors="coerce")
    high = pd.to_numeric(x["high"], errors="coerce")
    low = pd.to_numeric(x["low"], errors="coerce")
    if not np.isfinite(np.column_stack([close, high, low])).all():
        raise ValueError("OHLC data contains missing or non-finite values")
    if (close <= 0).any() or (high <= 0).any() or (low <= 0).any():
        raise ValueError("OHLC prices must be positive")
    x["ema9"] = close.ewm(span=9, adjust=False).mean()
    x["ema12"] = close.ewm(span=12, adjust=False).mean()
    x["ema21"] = close.ewm(span=21, adjust=False).mean()
    x["ema20"] = close.ewm(span=20, adjust=False).mean()
    x["ema26"] = close.ewm(span=26, adjust=False).mean()
    x["ema50"] = close.ewm(span=50, adjust=False).mean()
    x["sma20"] = close.rolling(20).mean()
    x["sma50"] = close.rolling(50).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    x["rsi"] = (100 - 100 / (1 + rs)).mask((loss == 0) & (gain > 0), 100).mask((loss == 0) & (gain == 0), 50)
    fast = close.ewm(span=12, adjust=False).mean()
    slow = close.ewm(span=26, adjust=False).mean()
    x["macd"] = fast - slow
    x["macd_signal"] = x["macd"].ewm(span=9, adjust=False).mean()
    x["bb_mid"] = close.rolling(20).mean()
    std = close.rolling(20).std(ddof=0)
    x["bb_upper"] = x["bb_mid"] + 2 * std
    x["bb_lower"] = x["bb_mid"] - 2 * std
    x["donchian_high"] = high.shift(1).rolling(20).max()
    x["donchian_low"] = low.shift(1).rolling(20).min()
    x["roc"] = close.pct_change(10) * 100
    low14 = low.rolling(14).min()
    high14 = high.rolling(14).max()
    x["stoch_k"] = 100 * (close - low14) / (high14 - low14).replace(0, np.nan)
    x["atr"] = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1).rolling(14).mean()
    return x


def strategy_signals(df):
    x = _indicators(df)
    c = x["close"]
    specs = {}

    specs["EMA 9/21 crossover"] = (
        (x.ema9 > x.ema21) & (x.ema9.shift(1) <= x.ema21.shift(1)),
        (x.ema9 < x.ema21)
    )
    specs["SMA 20/50 crossover"] = (
        (x.sma20 > x.sma50) & (x.sma20.shift(1) <= x.sma50.shift(1)),
        (x.sma20 < x.sma50)
    )
    specs["EMA 20/50 + RSI"] = (
        (x.ema20 > x.ema50) & (x.ema20.shift(1) <= x.ema50.shift(1)) & (x.rsi < 70),
        (x.ema20 < x.ema50)
    )
    specs["MACD crossover"] = (
        (x.macd > x.macd_signal) & (x.macd.shift(1) <= x.macd_signal.shift(1)),
        (x.macd < x.macd_signal)
    )
    specs["Bollinger mean reversion"] = (
        (c < x.bb_lower) & (x.rsi < 35),
        (c >= x.bb_mid) | (x.rsi > 55)
    )
    specs["Donchian breakout"] = (
        c > x.donchian_high,
        c < x.donchian_low
    )
    specs["RSI mean reversion"] = (
        (x.rsi < 30) & (x.rsi.shift(1) >= 30),
        x.rsi > 55
    )
    specs["ROC momentum"] = (
        (x.roc > 1.0) & (x.roc.shift(1) <= 1.0),
        x.roc < 0
    )
    specs["Stochastic reversal"] = (
        (x.stoch_k < 20) & (x.stoch_k.shift(1) >= 20),
        x.stoch_k > 80
    )
    specs["ATR channel breakout"] = (
        c > (x.ema20 + 1.5 * x.atr),
        c < x.ema20
    )
    specs["EMA trend + MACD"] = (
        (x.ema20 > x.ema50) & (x.macd > x.macd_signal) & (x.macd.shift(1) <= x.macd_signal.shift(1)),
        (x.ema20 < x.ema50) | (x.macd < x.macd_signal)
    )
    return {name: (entry.fillna(False).astype(bool), exit_.fillna(False).astype(bool)) for name, (entry, exit_) in specs.items()}


def run_backtest(df, entry, exit_, fee=0.001, slippage=0.0005, initial_balance=1000.0):
    if not {"open", "close"}.issubset(df.columns):
        raise ValueError("OHLC data must include open and close")
    fee, slippage, initial_balance = float(fee), float(slippage), float(initial_balance)
    if not math.isfinite(fee) or not 0 <= fee < 1:
        raise ValueError("Fee must be between 0 and 1")
    if not math.isfinite(slippage) or not 0 <= slippage < 1:
        raise ValueError("Slippage must be between 0 and 1")
    if not math.isfinite(initial_balance) or initial_balance <= 0:
        raise ValueError("Initial balance must be positive")
    n = len(df)
    entries, exits = np.asarray(entry, dtype=bool), np.asarray(exit_, dtype=bool)
    if n < 3 or len(entries) != n or len(exits) != n:
        raise ValueError("At least 3 candles and matching signal lengths are required")
    market = df.reset_index(drop=True)
    op = pd.to_numeric(market.open, errors="coerce").to_numpy(dtype=float)
    cl = pd.to_numeric(market.close, errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(op).all() or not np.isfinite(cl).all() or (op <= 0).any() or (cl <= 0).any():
        raise ValueError("Invalid OHLC prices")
    cash, units, cost = initial_balance, 0.0, 0.0
    trades, equity = [], [initial_balance]
    entry_i = None
    for i in range(1, n):
        # Signals from the prior completed candle execute at this candle's open.
        if units > 0 and exits[i-1]:
            fill = op[i] * (1 - slippage)
            proceeds = units * fill * (1 - fee)
            pnl = proceeds - cost
            trades.append({"entry_index": entry_i, "exit_index": i, "net_pnl": pnl, "return_pct": pnl / cost * 100})
            cash += proceeds
            units, cost, entry_i = 0.0, 0.0, None
        elif units == 0 and entries[i-1]:
            fill = op[i] * (1 + slippage)
            units = cash / (fill * (1 + fee))
            cost = units * fill * (1 + fee)
            cash, entry_i = 0.0, i
        equity.append(cash + units * cl[i])
    last = cl[-1] * (1 - slippage)
    liquidation = cash + units * last * (1 - fee)
    peak, drawdown = initial_balance, 0.0
    for value in equity:
        peak = max(peak, value)
        drawdown = max(drawdown, (peak-value)/peak if peak else 0)
    wins = [t["net_pnl"] for t in trades if t["net_pnl"] > 0]
    losses = [-t["net_pnl"] for t in trades if t["net_pnl"] < 0]
    gross_win, gross_loss = sum(wins), sum(losses)
    count = len(trades)
    pf = gross_win/gross_loss if gross_loss else ("infinite" if gross_win else None)
    return {
        "trades": count,
        "win_rate_pct": len(wins)/count*100 if count else 0.0,
        "net_return_pct": (liquidation/initial_balance-1)*100,
        "max_drawdown_pct": drawdown*100,
        "profit_factor": pf,
        "expectancy": sum(t["net_pnl"] for t in trades)/count if count else None,
        "liquidation_balance": liquidation,
        "open_position": units > 0,
        "trade_log": trades,
        "equity_curve": equity,
    }


def compare_all(df, fee=0.001, slippage=0.0005, initial_balance=1000.0):
    results = []
    for name, (entry, exit_) in strategy_signals(df).items():
        try:
            r = run_backtest(df, entry, exit_, fee, slippage, initial_balance)
            pf = r["profit_factor"]
            qualifies = (
                r["trades"] >= 100
                and r["win_rate_pct"] >= 80
                and r["net_return_pct"] > 0
                and r["expectancy"] is not None and r["expectancy"] > 0
                and (pf == "infinite" or (isinstance(pf, (int, float)) and pf > 1))
            )
            results.append({"strategy": name, **r, "qualifies": qualifies,
                            "status": "معیار اولیه را گذرانده" if qualifies else "نیازمند بررسی / رد معیار اولیه"})
        except (ValueError, KeyError, TypeError) as exc:
            results.append({"strategy": name, "trades": 0, "win_rate_pct": 0.0,
                            "net_return_pct": 0.0, "max_drawdown_pct": 0.0,
                            "profit_factor": None, "expectancy": None,
                            "qualifies": False, "status": f"خطا: {exc}"})
    return sorted(results, key=lambda r: (r["qualifies"], r["net_return_pct"], r["profit_factor"] == "infinite"), reverse=True)
