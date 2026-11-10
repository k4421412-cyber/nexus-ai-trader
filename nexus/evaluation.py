"""Chronological out-of-sample and walk-forward evaluation helpers."""
from collections import Counter

import numpy as np

from nexus.strategies import backtest, _validated_signals


def walk_forward_evaluate(
    df,
    strategy_candidates,
    *,
    train_size=500,
    test_size=100,
    step_size=None,
    fee=0.001,
    slippage=0.0005,
    initial_balance=1000.0,
):
    """Select a candidate only on each past training window, then test it forward.

    Candidate signals must be causal (each signal may use only information available
    at that candle). Each OOS fold starts with a fresh virtual balance; returns are
    reported per fold and are not compounded into a fictitious portfolio.
    """
    if not hasattr(df, "iloc") or len(df) < 3:
        raise ValueError("At least three chronological candles are required")
    for name, value in (("train_size", train_size), ("test_size", test_size)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 2:
            raise ValueError(f"{name} must be an integer of at least 2")
    if step_size is None:
        step_size = test_size
    if isinstance(step_size, bool) or not isinstance(step_size, int) or step_size < 1:
        raise ValueError("step_size must be a positive integer")
    if not isinstance(strategy_candidates, dict) or not strategy_candidates:
        raise ValueError("strategy_candidates must be a non-empty mapping")

    normalized = {}
    for name, signals in strategy_candidates.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Every strategy candidate needs a non-empty name")
        normalized[name] = _validated_signals(signals, len(df))

    folds = []
    test_start = train_size
    while test_start < len(df):
        test_end = min(test_start + test_size, len(df))
        train_start = max(0, test_start - train_size)
        training_df = df.iloc[train_start:test_start].reset_index(drop=True)
        training_scores = {}
        for name, signals in normalized.items():
            training_signals = signals.iloc[train_start:test_start].reset_index(drop=True)
            result = backtest(
                training_df, training_signals, fee=fee, slippage=slippage,
                initial_balance=initial_balance,
            )
            # A simple risk-aware selection score; not a promise of future performance.
            training_scores[name] = {
                "score": result["net_return_pct"] - result["max_drawdown_pct"],
                "net_return_pct": result["net_return_pct"],
                "max_drawdown_pct": result["max_drawdown_pct"],
            }
        selected = max(training_scores, key=lambda name: training_scores[name]["score"])

        # Include the final training candle only as the prior-candle signal/warm-up
        # needed to execute the first OOS decision at the first OOS candle's open.
        oos_start = max(0, test_start - 1)
        oos_df = df.iloc[oos_start:test_end].reset_index(drop=True)
        oos_signals = normalized[selected].iloc[oos_start:test_end].reset_index(drop=True)
        oos_result = backtest(
            oos_df, oos_signals, fee=fee, slippage=slippage,
            initial_balance=initial_balance,
        )
        folds.append({
            "train_start": train_start,
            "train_end_exclusive": test_start,
            "test_start": test_start,
            "test_end_exclusive": test_end,
            "training_scores": training_scores,
            "selected_strategy": selected,
            "test_result": oos_result,
        })
        test_start += step_size

    if not folds:
        raise ValueError("Not enough candles to create an out-of-sample test fold")

    returns = [fold["test_result"]["net_return_pct"] for fold in folds]
    drawdowns = [fold["test_result"]["max_drawdown_pct"] for fold in folds]
    counts = Counter(fold["selected_strategy"] for fold in folds)
    return {
        "fold_count": len(folds),
        "selected_strategy_counts": dict(counts),
        "average_oos_net_return_pct": float(np.mean(returns)),
        "worst_oos_drawdown_pct": float(max(drawdowns)),
        "oos_closed_trade_count": sum(fold["test_result"]["closed_trade_count"] for fold in folds),
        "folds": folds,
        "selection_score": "training net return percentage minus training max drawdown percentage",
        "simulation_only": True,
    }
