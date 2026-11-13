import math
import numpy as np
import pandas as pd


def _validated_signal_array(values, length, name=""):
    """Accept only 1-D boolean or binary numeric signals of the expected length."""
    try:
        array = np.asarray(values)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} signal must be a one-dimensional array with matching candle length") from exc
    if array.ndim != 1 or len(array) != length:
        raise ValueError(f"{name} signal must be one-dimensional with matching candle length")
    if array.dtype.kind == "b":
        return array.astype(bool, copy=False)
    if array.dtype.kind in "iuf":
        if not np.isfinite(array).all() or not np.isin(array, [0, 1]).all():
            raise ValueError(f"{name} signal must contain only booleans or numeric 0/1 values")
        return array.astype(bool)
    raise ValueError(f"{name} signal must contain only booleans or numeric 0/1 values")


def _indicators(df):
    x = df.copy()
    close = pd.to_numeric(x["close"], errors="coerce")
    high = pd.to_numeric(x["high"], errors="coerce")
    low = pd.to_numeric(x["low"], errors="coerce")
    if not np.isfinite(np.column_stack([close, high, low])).all():
        raise ValueError("OHLC data contains missing or non-finite values")
    if (close <= 0).any() or (high <= 0).any() or (low <= 0).any():
        raise ValueError("OHLC prices must be positive")
    if (high < low).any() or (close > high).any() or (close < low).any():
        raise ValueError("OHLC prices are inconsistent")
    if "open" in x.columns:
        open_ = pd.to_numeric(x["open"], errors="coerce")
        if not np.isfinite(open_).all() or (open_ <= 0).any() or (open_ > high).any() or (open_ < low).any():
            raise ValueError("OHLC open prices are invalid")
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
    true_range = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    x["atr"] = true_range.rolling(14).mean()
    atr_wilder = true_range.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    x["plus_di"] = 100 * plus_dm.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / atr_wilder.replace(0, np.nan)
    x["minus_di"] = 100 * minus_dm.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / atr_wilder.replace(0, np.nan)
    dx = 100 * (x["plus_di"] - x["minus_di"]).abs() / (x["plus_di"] + x["minus_di"]).replace(0, np.nan)
    x["adx"] = dx.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    x["keltner_mid"] = x["ema20"]
    x["keltner_upper"] = x["keltner_mid"] + 2 * x["atr"]
    x["keltner_lower"] = x["keltner_mid"] - 2 * x["atr"]

    # Causal Supertrend: each band/state uses only current and prior candles.
    midpoint = (high + low) / 2
    basic_upper = midpoint + 3 * atr_wilder
    basic_lower = midpoint - 3 * atr_wilder
    final_upper = np.full(len(x), np.nan)
    final_lower = np.full(len(x), np.nan)
    direction = np.zeros(len(x), dtype=int)
    first_valid = np.flatnonzero(atr_wilder.notna().to_numpy())
    if len(first_valid):
        start = int(first_valid[0])
        final_upper[start] = basic_upper.iloc[start]
        final_lower[start] = basic_lower.iloc[start]
        direction[start] = 1
        for i in range(start + 1, len(x)):
            previous_upper = final_upper[i - 1]
            previous_lower = final_lower[i - 1]
            final_upper[i] = (
                basic_upper.iloc[i]
                if basic_upper.iloc[i] < previous_upper or close.iloc[i - 1] > previous_upper
                else previous_upper
            )
            final_lower[i] = (
                basic_lower.iloc[i]
                if basic_lower.iloc[i] > previous_lower or close.iloc[i - 1] < previous_lower
                else previous_lower
            )
            if direction[i - 1] < 0 and close.iloc[i] > final_upper[i]:
                direction[i] = 1
            elif direction[i - 1] > 0 and close.iloc[i] < final_lower[i]:
                direction[i] = -1
            else:
                direction[i] = direction[i - 1]
    x["supertrend_direction"] = direction
    x["supertrend"] = np.where(direction > 0, final_lower, final_upper)

    # Ichimoku cloud values are shifted forward on charts; shift them back
    # here to compare only the cloud that was already visible at each candle.
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    span_a_visible = ((tenkan + kijun) / 2).shift(26)
    span_b_visible = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
    x["ichimoku_tenkan"] = tenkan
    x["ichimoku_kijun"] = kijun
    x["ichimoku_cloud_top"] = pd.concat([span_a_visible, span_b_visible], axis=1).max(axis=1)
    x["ichimoku_cloud_bottom"] = pd.concat([span_a_visible, span_b_visible], axis=1).min(axis=1)
    x["ichimoku_chikou_confirm"] = close > high.shift(26)
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
    specs["ADX + Directional Movement"] = (
        (x.plus_di > x.minus_di) & (x.plus_di.shift(1) <= x.minus_di.shift(1)) & (x.adx >= 20),
        (x.minus_di > x.plus_di) | (x.adx < 15)
    )
    specs["Keltner channel breakout"] = (
        (c > x.keltner_upper) & (c.shift(1) <= x.keltner_upper.shift(1)),
        c < x.keltner_mid
    )
    specs["Supertrend"] = (
        (x.supertrend_direction > 0) & (x.supertrend_direction.shift(1) < 0),
        (x.supertrend_direction < 0) & (x.supertrend_direction.shift(1) > 0)
    )
    specs["Ichimoku Cloud"] = (
        (c > x.ichimoku_cloud_top)
        & (x.ichimoku_tenkan > x.ichimoku_kijun)
        & (x.ichimoku_tenkan.shift(1) <= x.ichimoku_kijun.shift(1))
        & x.ichimoku_chikou_confirm,
        (c < x.ichimoku_cloud_bottom) | (x.ichimoku_tenkan < x.ichimoku_kijun)
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
    if n < 3:
        raise ValueError("At least 3 candles and matching signal lengths are required")
    entries = _validated_signal_array(entry, n, "Entry")
    exits = _validated_signal_array(exit_, n, "Exit")
    market = df.reset_index(drop=True)
    op = pd.to_numeric(market.open, errors="coerce").to_numpy(dtype=float)
    cl = pd.to_numeric(market.close, errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(op).all() or not np.isfinite(cl).all() or (op <= 0).any() or (cl <= 0).any():
        raise ValueError("Invalid OHLC prices")
    if {"high", "low"}.issubset(market.columns):
        high = pd.to_numeric(market.high, errors="coerce").to_numpy(dtype=float)
        low = pd.to_numeric(market.low, errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(high).all() or not np.isfinite(low).all():
            raise ValueError("Invalid OHLC high/low prices")
        if (high <= 0).any() or (low <= 0).any():
            raise ValueError("OHLC high/low prices must be positive")
        if (high < np.maximum.reduce([op, cl, low])).any() or (low > np.minimum(op, cl)).any():
            raise ValueError("OHLC prices are inconsistent")
    if "timestamp" in market.columns:
        timestamps = pd.to_numeric(market.timestamp, errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(timestamps).all() or pd.Series(timestamps).duplicated().any() or not pd.Series(timestamps).is_monotonic_increasing:
            raise ValueError("Candle timestamps must be finite, unique and chronological")
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
    # Close any remaining position at the final candle so realized trade
    # metrics, net return, and the reported trade count use the same basis.
    if units > 0:
        fill = cl[-1] * (1 - slippage)
        proceeds = units * fill * (1 - fee)
        pnl = proceeds - cost
        trades.append({
            "entry_index": entry_i,
            "exit_index": n - 1,
            "net_pnl": pnl,
            "return_pct": pnl / cost * 100,
            "forced_exit": True,
        })
        cash += proceeds
        units, cost, entry_i = 0.0, 0.0, None
    liquidation = cash
    equity.append(liquidation)
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


def qualifies_strategy(metrics, min_trades=100, min_win_rate_pct=80.0):
    """Apply the hard eligibility gate to one strategy in one market/condition."""
    try:
        trades = int(metrics.get("trades", 0))
        win_rate = float(metrics.get("win_rate_pct", 0.0))
        net_return = float(metrics.get("net_return_pct", 0.0))
        expectancy = metrics.get("expectancy")
        expectancy = float(expectancy) if expectancy is not None else float("nan")
        pf = metrics.get("profit_factor")
        valid_pf = pf == "infinite" or (
            isinstance(pf, (int, float)) and math.isfinite(float(pf)) and float(pf) > 1
        )
        return (
            trades >= min_trades
            and math.isfinite(win_rate) and win_rate >= min_win_rate_pct
            and math.isfinite(net_return) and net_return > 0
            and math.isfinite(expectancy) and expectancy > 0
            and valid_pf
        )
    except (TypeError, ValueError, OverflowError):
        return False


def evaluate_by_condition(condition_metrics, min_trades=100, min_win_rate_pct=80.0):
    """Evaluate each supplied market condition independently; never pool metrics."""
    return {
        str(condition): qualifies_strategy(
            metrics, min_trades=min_trades, min_win_rate_pct=min_win_rate_pct
        )
        for condition, metrics in condition_metrics.items()
    }



def classify_market_regime(df, adx_threshold=20.0):
    """Classify each candle using trailing-only EMA trend and ADX information."""
    if not isinstance(df, pd.DataFrame) or not {"close", "high", "low"}.issubset(df.columns):
        raise ValueError("Market data must contain close, high and low columns")
    if isinstance(adx_threshold, bool):
        raise ValueError("ADX threshold must be a finite number between 0 and 100")
    try:
        adx_threshold = float(adx_threshold)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("ADX threshold must be a finite number between 0 and 100") from exc
    if not math.isfinite(adx_threshold) or not 0 <= adx_threshold <= 100:
        raise ValueError("ADX threshold must be a finite number between 0 and 100")
    x = df.copy()
    close = pd.to_numeric(x["close"], errors="coerce")
    high = pd.to_numeric(x["high"], errors="coerce")
    low = pd.to_numeric(x["low"], errors="coerce")
    if not np.isfinite(np.column_stack([close, high, low])).all():
        raise ValueError("OHLC data contains missing or non-finite values")
    if (close <= 0).any() or (high <= 0).any() or (low <= 0).any():
        raise ValueError("OHLC prices must be positive")
    if (high < low).any() or (close > high).any() or (close < low).any():
        raise ValueError("OHLC prices are inconsistent")
    if "open" in x.columns:
        open_ = pd.to_numeric(x["open"], errors="coerce")
        if not np.isfinite(open_).all() or (open_ <= 0).any() or (open_ > high).any() or (open_ < low).any():
            raise ValueError("OHLC open prices are invalid")
    ema50 = close.ewm(span=50, adjust=False, min_periods=50).mean()
    ema200 = close.ewm(span=200, adjust=False, min_periods=200).mean()
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    previous_close = close.shift(1)
    true_range = pd.concat([
        high - low,
        (high - previous_close).abs(),
        (low - previous_close).abs(),
    ], axis=1).max(axis=1)
    atr = true_range.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    slope_up = ema50 > ema50.shift(5)
    valid = ema200.notna() & adx.notna() & plus_di.notna() & minus_di.notna()
    bullish = valid & (adx >= adx_threshold) & (ema50 > ema200) & slope_up & (plus_di > minus_di)
    bearish = valid & (adx >= adx_threshold) & (ema50 < ema200) & (~slope_up) & (minus_di > plus_di)
    labels = pd.Series("sideways", index=df.index, dtype="object")
    labels.loc[~valid] = "insufficient_data"
    labels.loc[bullish] = "bullish"
    labels.loc[bearish] = "bearish"
    return labels


def _metrics_for_trade_group(trades, initial_balance):
    count = len(trades)
    pnls = [float(t["net_pnl"]) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [-p for p in pnls if p < 0]
    gross_win, gross_loss = sum(wins), sum(losses)
    profit_factor = gross_win / gross_loss if gross_loss else ("infinite" if gross_win else None)
    equity = float(initial_balance)
    peak = equity
    max_drawdown = 0.0
    for trade in trades:
        equity *= 1 + float(trade["return_pct"]) / 100
        peak = max(peak, equity)
        if peak:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
    return {
        "trades": count,
        "win_rate_pct": len(wins) / count * 100 if count else 0.0,
        "net_return_pct": (equity / initial_balance - 1) * 100 if count else 0.0,
        "max_drawdown_pct": max_drawdown * 100,
        "profit_factor": profit_factor,
        "expectancy": sum(pnls) / count if count else None,
    }


def compare_by_regime(df, fee=0.001, slippage=0.0005, initial_balance=1000.0):
    """Backtest every strategy, then grade its closed trades separately by entry regime."""
    regimes = classify_market_regime(df).reset_index(drop=True)
    output = []
    for name, (entry, exit_) in strategy_signals(df).items():
        try:
            backtest = run_backtest(df, entry, exit_, fee, slippage, initial_balance)
            grouped = {key: [] for key in ("bullish", "bearish", "sideways")}
            for trade in backtest["trade_log"]:
                regime = regimes.iloc[max(0, int(trade["entry_index"]) - 1)]
                if regime in grouped:
                    grouped[regime].append(trade)
            by_regime = {}
            for regime, trades in grouped.items():
                metrics = _metrics_for_trade_group(trades, initial_balance)
                metrics["qualifies"] = qualifies_strategy(metrics)
                metrics["status"] = (
                    "معیار اولیه را گذرانده" if metrics["qualifies"]
                    else "رد/داده ناکافی برای تأیید"
                )
                by_regime[regime] = metrics
            output.append({"strategy": name, "by_regime": by_regime})
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            output.append({"strategy": name, "by_regime": {}, "error": str(exc)})
    return output

def compare_all(df, fee=0.001, slippage=0.0005, initial_balance=1000.0):
    results = []
    for name, (entry, exit_) in strategy_signals(df).items():
        try:
            r = run_backtest(df, entry, exit_, fee, slippage, initial_balance)
            qualifies = qualifies_strategy(r)
            results.append({"strategy": name, **r, "qualifies": qualifies,
                            "status": "معیار اولیه را گذرانده" if qualifies else "نیازمند بررسی / رد معیار اولیه"})
        except (ValueError, KeyError, TypeError) as exc:
            results.append({"strategy": name, "trades": 0, "win_rate_pct": 0.0,
                            "net_return_pct": 0.0, "max_drawdown_pct": 0.0,
                            "profit_factor": None, "expectancy": None,
                            "qualifies": False, "status": f"خطا: {exc}"})
    return sorted(results, key=lambda r: (r["qualifies"], r["net_return_pct"], r["profit_factor"] == "infinite"), reverse=True)
