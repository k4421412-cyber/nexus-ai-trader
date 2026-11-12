"""Goal-based automatic paper trading. This module never places live orders."""
import math

import pandas as pd

from nexus.strategies import ema_rsi_signals


def _finite_number(value, name, *, minimum=None, maximum=None, strict_min=False):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and (number <= minimum if strict_min else number < minimum):
        operator = "greater than" if strict_min else "at least"
        raise ValueError(f"{name} must be {operator} {minimum}")
    if maximum is not None and number > maximum:
        raise ValueError(f"{name} must be at most {maximum}")
    return number


def simulate_to_goal(
    market,
    *,
    initial_balance=1.0,
    target_balance=5.0,
    max_loss_pct=20.0,
    max_position_pct=25.0,
    fee_pct=0.1,
    slippage_pct=0.05,
):
    """Replay closed candles using EMA/RSI entries and EMA trend exits.

    Signals from candle i-1 execute at candle i open. The simulation is
    long-only, applies fees/slippage on both sides, and stops at the target,
    loss limit, or end of supplied history. No live exchange API is used.
    """
    initial = _finite_number(initial_balance, "Initial balance", minimum=0, strict_min=True)
    target = _finite_number(target_balance, "Target balance", minimum=0, strict_min=True)
    if target <= initial:
        raise ValueError("Target balance must be greater than initial balance")
    loss_pct = _finite_number(max_loss_pct, "Maximum loss percentage", minimum=0, maximum=50, strict_min=True)
    position_pct = _finite_number(max_position_pct, "Maximum position percentage", minimum=0, maximum=100, strict_min=True)
    fee = _finite_number(fee_pct, "Fee percentage", minimum=0, maximum=5) / 100
    slippage = _finite_number(slippage_pct, "Slippage percentage", minimum=0, maximum=5) / 100
    if fee >= 1 or slippage >= 1:
        raise ValueError("Fee and slippage must be below 100%")

    required = {"open", "close", "ema20", "ema50", "rsi"}
    if not isinstance(market, pd.DataFrame) or len(market) < 3:
        raise ValueError("At least three closed market candles are required")
    missing = required.difference(market.columns)
    if missing:
        raise ValueError(f"Missing market columns: {', '.join(sorted(missing))}")
    data = market.reset_index(drop=True).copy()
    for col in ("open", "close", "ema20", "ema50", "rsi"):
        data[col] = pd.to_numeric(data[col], errors="coerce")
    if not data[["open", "close", "ema20", "ema50"]].apply(lambda c: c.map(math.isfinite)).all().all():
        raise ValueError("Market prices and EMA indicators must be finite")
    if (data[["open", "close"]] <= 0).any().any():
        raise ValueError("Market prices must be positive")

    signals = ema_rsi_signals(data).tolist()
    cash = initial
    units = 0.0
    entry_cost = 0.0
    trades = []
    curve = [initial]
    status = "history_exhausted"
    stop_balance = initial * (1 - loss_pct / 100)
    last_price = float(data.iloc[0]["close"])
    stop_index = len(data) - 1

    def close_position(price, index, reason):
        nonlocal cash, units, entry_cost
        if units <= 0:
            return
        fill = price * (1 - slippage)
        proceeds = units * fill * (1 - fee)
        pnl = proceeds - entry_cost
        cash += proceeds
        trades.append({
            "entry_cost": round(entry_cost, 10),
            "exit_proceeds": round(proceeds, 10),
            "net_pnl": round(pnl, 10),
            "return_pct": round((pnl / entry_cost) * 100, 4) if entry_cost else 0.0,
            "exit_index": index,
            "exit_reason": reason,
        })
        units = 0.0
        entry_cost = 0.0

    for i in range(1, len(data)):
        previous = data.iloc[i - 1]
        candle = data.iloc[i]
        execution_open = float(candle["open"])
        last_price = float(candle["close"])
        should_exit = units > 0 and float(previous["ema20"]) < float(previous["ema50"])
        should_enter = units == 0 and bool(signals[i - 1]) and cash > 0

        if should_exit:
            close_position(execution_open, i, "strategy_exit")
        elif should_enter:
            equity_at_open = cash + units * execution_open
            allocation = min(cash, equity_at_open * position_pct / 100)
            fill = execution_open * (1 + slippage)
            total_cost_per_unit = fill * (1 + fee)
            if allocation > 0 and total_cost_per_unit > 0:
                units = allocation / total_cost_per_unit
                entry_cost = units * total_cost_per_unit
                cash -= entry_cost

        marked_equity = cash + units * last_price
        curve.append(marked_equity)
        if marked_equity >= target:
            close_position(last_price, i, "target_liquidation")
            curve[-1] = cash
            status = "target_reached" if cash >= target else "target_touched_before_exit_costs"
            stop_index = i
            break
        if marked_equity <= stop_balance:
            close_position(last_price, i, "risk_limit_liquidation")
            curve[-1] = cash
            status = "risk_limit_reached"
            stop_index = i
            break

    if units > 0:
        close_position(last_price, stop_index, "end_of_history_liquidation")
        curve[-1] = cash

    final_balance = cash
    return {
        "simulation_only": True,
        "live_orders_sent": False,
        "status": status,
        "initial_balance": round(initial, 10),
        "target_balance": round(target, 10),
        "stop_balance": round(stop_balance, 10),
        "final_balance": round(final_balance, 10),
        "net_pnl": round(final_balance - initial, 10),
        "net_return_pct": round((final_balance / initial - 1) * 100, 4),
        "trades": len(trades),
        "win_rate_pct": round(sum(t["net_pnl"] > 0 for t in trades) / len(trades) * 100, 2) if trades else 0.0,
        "trade_log": trades,
        "equity_curve": [round(value, 10) for value in curve],
        "candles_processed": len(curve),
        "stop_index": stop_index,
    }
