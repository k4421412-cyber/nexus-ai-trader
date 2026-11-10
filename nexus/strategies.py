import math

import numpy as np
import pandas as pd

import numpy as np
import pandas as pd


def ema_rsi_signals(df):
    required = {"ema20", "ema50", "rsi"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing signal columns: {', '.join(sorted(missing))}")
    market = df.copy()
    for column in required:
        converted = pd.to_numeric(market[column], errors="coerce")
        if (market[column].notna() & converted.isna()).any():
            raise ValueError("Signal indicators must be numeric")
        market[column] = converted
    ema_values = market[["ema20", "ema50"]].to_numpy(dtype=float)
    rsi_values = market["rsi"].to_numpy(dtype=float)
    if not np.isfinite(ema_values).all() or np.isinf(rsi_values).any():
        raise ValueError("EMA values must be finite and RSI values must be finite or missing")
    if (market[["ema20", "ema50"]] <= 0).any().any():
        raise ValueError("EMA values must be positive")
    valid_rsi = market["rsi"].dropna()
    if ((valid_rsi < 0) | (valid_rsi > 100)).any():
        raise ValueError("RSI values must be between 0 and 100")
    buy = (
        (market["ema20"] > market["ema50"])
        & (market["ema20"].shift() <= market["ema50"].shift())
        & (market["rsi"] < 70)
    )
    return buy.fillna(False)


def _validated_signals(signals, expected_length):
    values = np.asarray(signals, dtype=object)
    if values.ndim != 1:
        raise ValueError("Signals must be a one-dimensional boolean sequence")
    if len(values) != expected_length:
        raise ValueError("Signals length must match market data length")

    normalized = []
    for value in values:
        if value is None or value is pd.NA:
            normalized.append(False)
        elif isinstance(value, (bool, np.bool_)):
            normalized.append(bool(value))
        else:
            try:
                missing = pd.isna(value)
            except (TypeError, ValueError):
                missing = False
            if isinstance(missing, (bool, np.bool_)) and missing:
                normalized.append(False)
            else:
                raise ValueError("Signals must contain only boolean values or missing values")
    return pd.Series(normalized, dtype=bool)


def backtest(
    df,
    signals,
    fee=0.001,
    slippage=0.0005,
    initial_balance=1000.0,
):
    """Long-only backtest; close-based signals fill at the next candle open."""
    required = {"open", "close", "ema20", "ema50"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing backtest columns: {', '.join(sorted(missing))}")
    if len(df) < 2:
        raise ValueError("At least two candles are required for backtesting")

    signal_values = _validated_signals(signals, len(df))

    try:
        fee = float(fee)
        slippage = float(slippage)
        initial_balance = float(initial_balance)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Fee, slippage, and initial balance must be numeric") from exc

    if not math.isfinite(fee) or not 0 <= fee < 1:
        raise ValueError("Fee must be finite and between 0 (inclusive) and 1 (exclusive)")
    if not math.isfinite(slippage) or not 0 <= slippage < 1:
        raise ValueError("Slippage must be finite and between 0 (inclusive) and 1 (exclusive)")
    if not math.isfinite(initial_balance) or initial_balance <= 0:
        raise ValueError("Initial balance must be a finite positive number")

    market = df.reset_index(drop=True).copy()
    for column in ["open", "close", "ema20", "ema50"]:
        market[column] = pd.to_numeric(market[column], errors="coerce")
    numeric_values = market[["open", "close", "ema20", "ema50"]].to_numpy(dtype=float)
    if not np.isfinite(numeric_values).all():
        raise ValueError("Backtest data contains missing, non-numeric, or non-finite prices/indicators")
    if (market[["open", "close"]] <= 0).any().any():
        raise ValueError("Backtest prices must be positive")

    cash = initial_balance
    units = 0.0
    entry_cost = 0.0
    closed_trades = []
    equity_curve = [initial_balance]
    exposed_bars = 0

    for i in range(1, len(market)):
        execution_open = float(market.iloc[i]["open"])
        should_exit = float(market.iloc[i - 1]["ema20"]) < float(market.iloc[i - 1]["ema50"])
        should_enter = bool(signal_values.iloc[i - 1])

        if units > 0 and should_exit:
            fill_price = execution_open * (1 - slippage)
            proceeds = units * fill_price * (1 - fee)
            pnl = proceeds - entry_cost
            closed_trades.append({
                "entry_cost": round(entry_cost, 8),
                "exit_proceeds": round(proceeds, 8),
                "net_pnl": round(pnl, 8),
                "return_pct": round((pnl / entry_cost) * 100, 4),
            })
            cash += proceeds
            units = 0.0
            entry_cost = 0.0
        elif units == 0 and should_enter and cash > 0:
            fill_price = execution_open * (1 + slippage)
            total_cost_per_unit = fill_price * (1 + fee)
            units = cash / total_cost_per_unit
            entry_cost = units * total_cost_per_unit
            cash = 0.0

        if units > 0:
            exposed_bars += 1
        close_price = float(market.iloc[i]["close"])
        equity_curve.append(cash + units * close_price)

    marked_to_market_balance = equity_curve[-1]
    last_close = float(market.iloc[-1]["close"])
    estimated_exit_price = last_close * (1 - slippage)
    estimated_liquidation_balance = cash + units * estimated_exit_price * (1 - fee)

    peak = equity_curve[0]
    max_drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - value) / peak)

    winners = [t["net_pnl"] for t in closed_trades if t["net_pnl"] > 0]
    losers = [-t["net_pnl"] for t in closed_trades if t["net_pnl"] < 0]
    gross_profit = sum(winners)
    gross_loss = sum(losers)
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (None if gross_profit == 0 else "infinite")
    trade_count = len(closed_trades)

    return {
        "initial_balance": round(initial_balance, 2),
        "final_balance": round(marked_to_market_balance, 2),
        "marked_to_market_balance": round(marked_to_market_balance, 8),
        "estimated_liquidation_balance": round(estimated_liquidation_balance, 8),
        "estimated_liquidation_return_pct": round((estimated_liquidation_balance / initial_balance - 1) * 100, 4),
        "net_return_pct": round((marked_to_market_balance / initial_balance - 1) * 100, 4),
        "closed_trade_count": trade_count,
        "open_position": units > 0,
        "open_position_units": round(units, 10),
        "win_rate_pct": round((len(winners) / trade_count) * 100, 2) if trade_count else 0.0,
        "average_win": round(sum(winners) / len(winners), 8) if winners else None,
        "average_loss": round(-sum(losers) / len(losers), 8) if losers else None,
        "expectancy_per_closed_trade": round(sum(t["net_pnl"] for t in closed_trades) / trade_count, 8) if trade_count else None,
        "gross_profit": round(gross_profit, 8),
        "gross_loss": round(gross_loss, 8),
        "exposure_pct": round(exposed_bars / (len(market) - 1) * 100, 2),
        "max_drawdown_pct": round(max_drawdown * 100, 4),
        "profit_factor": round(profit_factor, 4) if isinstance(profit_factor, (int, float)) else profit_factor,
        "closed_trades": closed_trades,
        "equity_curve": [round(value, 4) for value in equity_curve],
    }
