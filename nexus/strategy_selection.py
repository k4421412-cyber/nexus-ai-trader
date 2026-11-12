"""Regime-specific strategy candidate screening on a historical training window."""
import math

import pandas as pd

from nexus.strategy_lab import (
    classify_market_regime, compare_by_regime, qualifies_strategy,
    run_backtest, strategy_signals,
)


def screen_regime_candidates(
    market, *, train_fraction=0.7, min_trades=100, min_win_rate_pct=80.0,
    fee=0.001, slippage=0.0005, initial_balance=1000.0,
):
    """Screen strategies on past data only; output candidates, never execution approval.

    The trailing holdout is deliberately excluded from selection. A candidate
    still needs separate untouched out-of-sample validation before it can trade.
    """
    if not isinstance(market, pd.DataFrame) or len(market) < 250:
        raise ValueError("At least 250 chronological candles are required")
    try:
        fraction = float(train_fraction)
        min_win_rate_pct = float(min_win_rate_pct)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Screening parameters must be numeric") from exc
    if not math.isfinite(fraction) or not 0.5 <= fraction < 0.9:
        raise ValueError("train_fraction must be finite and between 0.5 and 0.9")
    if isinstance(min_trades, bool) or not isinstance(min_trades, int) or min_trades < 1:
        raise ValueError("min_trades must be a positive integer")
    if not math.isfinite(min_win_rate_pct) or not 0 <= min_win_rate_pct <= 100:
        raise ValueError("min_win_rate_pct must be between 0 and 100")

    train_end = int(len(market) * fraction)
    training = market.iloc[:train_end].copy()
    if len(training) < 200:
        raise ValueError("Training window must contain at least 200 candles for regime warmup")

    rows = compare_by_regime(
        training, fee=fee, slippage=slippage, initial_balance=initial_balance
    )
    selected = {}
    screening = {}
    for regime in ("bullish", "bearish", "sideways"):
        candidates = []
        for row in rows:
            metrics = row.get("by_regime", {}).get(regime)
            if not metrics:
                continue
            passed = qualifies_strategy(
                metrics, min_trades=min_trades, min_win_rate_pct=min_win_rate_pct
            )
            if passed:
                candidates.append((row["strategy"], metrics))
        candidates.sort(
            key=lambda item: (
                float(item[1]["net_return_pct"]),
                float(item[1]["expectancy"]),
                math.inf if item[1]["profit_factor"] == "infinite" else float(item[1]["profit_factor"]),
            ),
            reverse=True,
        )
        screening[regime] = {
            "candidate_count": len(candidates),
            "best_candidate": candidates[0][0] if candidates else None,
            "candidate_metrics": candidates[0][1] if candidates else None,
        }
        if candidates:
            selected[regime] = candidates[0][0]

    return {
        "screening_only": True,
        "execution_approved": False,
        "training_candles": train_end,
        "holdout_candles_reserved": len(market) - train_end,
        "minimum_closed_trades": min_trades,
        "minimum_win_rate_pct": min_win_rate_pct,
        "selected_candidates_by_regime": selected,
        "by_regime": screening,
        "all_strategy_metrics": rows,
        "next_gate": "untouched out-of-sample validation and risk review",
    }

def validate_regime_candidates(
    market, *, train_fraction=0.7, min_trades=100, min_win_rate_pct=80.0,
    fee=0.001, slippage=0.0005, initial_balance=1000.0,
):
    """Validate the best training-screened candidate on the untouched holdout.

    A passing result is scoped to this exact market history, symbol and timeframe;
    it is not a global or future-profit guarantee.
    """
    screening = screen_regime_candidates(
        market, train_fraction=train_fraction, min_trades=min_trades,
        min_win_rate_pct=min_win_rate_pct, fee=fee, slippage=slippage,
        initial_balance=initial_balance,
    )
    train_end = screening["training_candles"]
    offset = train_end - 1
    holdout = market.iloc[offset:].reset_index(drop=True)
    labels = classify_market_regime(market).reset_index(drop=True)
    all_signals = strategy_signals(market)
    validation = {}
    approved = {}

    def trade_metrics(trades):
        count = len(trades)
        pnls = [float(trade["net_pnl"]) for trade in trades]
        wins = [value for value in pnls if value > 0]
        losses = [-value for value in pnls if value < 0]
        gross_profit, gross_loss = sum(wins), sum(losses)
        factor = gross_profit / gross_loss if gross_loss else ("infinite" if gross_profit else None)
        balance = float(initial_balance)
        for trade in trades:
            balance *= 1 + float(trade["return_pct"]) / 100
        return {
            "trades": count,
            "win_rate_pct": len(wins) / count * 100 if count else 0.0,
            "net_return_pct": (balance / float(initial_balance) - 1) * 100 if count else 0.0,
            "expectancy": sum(pnls) / count if count else None,
            "profit_factor": factor,
        }

    for regime, strategy_name in screening["selected_candidates_by_regime"].items():
        entry, exit_ = all_signals[strategy_name]
        result = run_backtest(
            holdout, entry.iloc[offset:].to_numpy(dtype=bool), exit_.iloc[offset:].to_numpy(dtype=bool), fee=fee,
            slippage=slippage, initial_balance=initial_balance,
        )
        grouped = []
        for trade in result["trade_log"]:
            signal_index = offset + max(0, int(trade["entry_index"]) - 1)
            if labels.iloc[signal_index] == regime:
                grouped.append(trade)
        metrics = trade_metrics(grouped)
        passed = qualifies_strategy(
            metrics, min_trades=min_trades, min_win_rate_pct=min_win_rate_pct
        )
        validation[regime] = {
            "strategy": strategy_name,
            "metrics": metrics,
            "passes_holdout": passed,
        }
        if passed:
            approved[regime] = strategy_name

    return {
        **screening,
        "holdout_validation": validation,
        "validated_candidates_by_regime": approved,
        "execution_approved": False,
        "next_gate": "replication across additional symbols/timeframes and risk review",
    }

def validate_across_markets(
    markets, *, train_fraction=0.7, min_trades=100, min_win_rate_pct=80.0,
    fee=0.001, slippage=0.0005, initial_balance=1000.0,
):
    """Require the same regime candidate to pass on every supplied market.

    This is a conservative replication check, not live-trading permission.
    Keys should identify distinct symbol/timeframe/exchange datasets.
    """
    if not isinstance(markets, dict) or len(markets) < 2:
        raise ValueError("At least two separately identified market datasets are required")
    if any(not isinstance(key, str) or not key.strip() for key in markets):
        raise ValueError("Every market dataset needs a non-empty identifier")
    results = {}
    for market_id, frame in markets.items():
        results[market_id] = validate_regime_candidates(
            frame, train_fraction=train_fraction, min_trades=min_trades,
            min_win_rate_pct=min_win_rate_pct, fee=fee, slippage=slippage,
            initial_balance=initial_balance,
        )
    replicated = {}
    for regime in ("bullish", "bearish", "sideways"):
        shared = None
        for result in results.values():
            candidate = result["validated_candidates_by_regime"].get(regime)
            names = {candidate} if candidate else set()
            shared = names if shared is None else shared.intersection(names)
        replicated[regime] = sorted(shared or [])
    return {
        "market_count": len(results),
        "market_results": results,
        "replicated_candidates_by_regime": replicated,
        "execution_approved": False,
        "next_gate": "broader exchange/timeframe replication, operational risk review and explicit live approval",
    }