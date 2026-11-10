import math

import numpy as np
import pandas as pd


def ema_rsi_signals(df):
    required = {"ema20", "ema50", "rsi"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing signal columns: {', '.join(sorted(missing))}")
    buy = (
        (df["ema20"] > df["ema50"])
        & (df["ema20"].shift() <= df["ema50"].shift())
        & (df["rsi"] < 70)
    )
    return buy.fillna(False)


def backtest(
    df,
    signals,
    fee=0.001,
    slippage=0.0005,
    initial_balance=1000.0,
):
    """Long-only backtest; signals are evaluated at candle close and filled next candle open."""
    required = {"open", "close", "ema20", "ema50"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing backtest columns: {', '.join(sorted(missing))}")
    if len(df) < 2:
        raise ValueError("At least two candles are required for backtesting")
    if len(signals) != len(df):
        raise ValueError("Signals length must match market data length")

    fee = float(fee)
    slippage = float(slippage)
    initial_balance = float(initial_balance)
    if not math.isfinite(fee) or not 0 <= fee < 1:
        raise ValueError("Fee must be finite and between 0 (inclusive) and 1 (exclusive)")
    if not math.isfinite(slippage) or not 0 <= slippage < 1:
        raise ValueError("Slippage must be finite and between 0 (inclusive) and 1 (exclusive)")
    if not math.isfinite(initial_balance) or initial_balance <= 0:
        raise ValueError("Initial balance must be a finite positive number")

    market = df.reset_index(drop=True)
    signal_values = pd.Series(signals).reset_index(drop=True).fillna(False).astype(bool)
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

    for i in range(1, len(market)):
        # Only use the previous candle's completed signal/indicators.
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

        close_price = float(market.iloc[i]["close"])
        equity_curve.append(cash + units * close_price)

    final_equity = equity_curve[-1]
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

    return {
        "initial_balance": round(initial_balance, 2),
        "final_balance": round(final_equity, 2),
        "net_return_pct": round((final_equity / initial_balance - 1) * 100, 4),
        "closed_trade_count": len(closed_trades),
        "open_position": units > 0,
        "open_position_units": round(units, 10),
        "win_rate_pct": round((len(winners) / len(closed_trades)) * 100, 2) if closed_trades else 0.0,
        "max_drawdown_pct": round(max_drawdown * 100, 4),
        "profit_factor": round(profit_factor, 4) if isinstance(profit_factor, (int, float)) else profit_factor,
        "closed_trades": closed_trades,
        "equity_curve": [round(value, 4) for value in equity_curve],
    }
