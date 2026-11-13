"""Chronological out-of-sample and walk-forward evaluation helpers."""
from collections import Counter

import numpy as np

from nexus.strategy_lab import run_backtest, _validated_signal_array, qualifies_strategy


def _candidate_pair(candidate, length):
    """Normalize a candidate to (entry, exit) boolean signals."""
    if isinstance(candidate, (tuple, list)) and len(candidate) == 2:
        entry, exit_ = candidate
    else:
        # Backward-compatible entry-only candidates are held until the fold ends.
        entry, exit_ = candidate, np.zeros(length, dtype=bool)
    entry = _validated_signal_array(entry, length, "Entry")
    exit_ = _validated_signal_array(exit_, length, "Exit")
    return entry, exit_


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
    min_trades=100,
    min_win_rate_pct=80.0,
):
    """Select only a strategy that passes the hard gate on past candles, then test it forward.

    Signals must be causal and precomputed without future data. Every fold starts
    with a fresh paper balance; fold returns are not compounded.
    """
    if not hasattr(df, "iloc") or len(df) < 3:
        raise ValueError("At least three chronological candles are required")
    for name, value in (("train_size", train_size), ("test_size", test_size)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 3:
            raise ValueError(f"{name} must be an integer of at least 3")
    if step_size is None:
        step_size = test_size
    if isinstance(step_size, bool) or not isinstance(step_size, int) or step_size < test_size:
        raise ValueError("step_size must be an integer greater than or equal to test_size")
    if not isinstance(strategy_candidates, dict) or not strategy_candidates:
        raise ValueError("strategy_candidates must be a non-empty mapping")
    if isinstance(min_trades, bool) or not isinstance(min_trades, int) or min_trades < 1:
        raise ValueError("min_trades must be a positive integer")
    try:
        min_win_rate_pct = float(min_win_rate_pct)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("min_win_rate_pct must be numeric") from exc
    if not np.isfinite(min_win_rate_pct) or not 0 <= min_win_rate_pct <= 100:
        raise ValueError("min_win_rate_pct must be between 0 and 100")

    normalized = {}
    for name, candidate in strategy_candidates.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Every strategy candidate needs a non-empty name")
        normalized[name] = _candidate_pair(candidate, len(df))

    folds = []
    test_start = train_size
    while test_start < len(df):
        test_end = min(test_start + test_size, len(df))
        train_start = max(0, test_start - train_size)
        training_df = df.iloc[train_start:test_start].reset_index(drop=True)
        training_scores = {}
        for name, (entries, exits) in normalized.items():
            result = run_backtest(
                training_df,
                entries[train_start:test_start],
                exits[train_start:test_start],
                fee=fee,
                slippage=slippage,
                initial_balance=initial_balance,
            )
            training_scores[name] = {
                "score": result["net_return_pct"] - result["max_drawdown_pct"],
                "net_return_pct": result["net_return_pct"],
                "max_drawdown_pct": result["max_drawdown_pct"],
                "closed_trade_count": result["trades"],
                "win_rate_pct": result["win_rate_pct"],
                "expectancy": result["expectancy"],
                "profit_factor": result["profit_factor"],
                "passes_hard_gate": qualifies_strategy(
                    result, min_trades=min_trades, min_win_rate_pct=min_win_rate_pct
                ),
            }
        eligible = [name for name, metrics in training_scores.items() if metrics["passes_hard_gate"]]
        selected = max(eligible, key=lambda name: training_scores[name]["score"]) if eligible else None

        # Include the prior candle so its completed signal can execute at test_start open.
        oos_start = max(0, test_start - 1)
        oos_df = df.iloc[oos_start:test_end].reset_index(drop=True)
        if selected is None:
            # No method met the training gate: remain flat in the untouched test window.
            no_signal = np.zeros(len(oos_df), dtype=bool)
            oos_result = run_backtest(
                oos_df, no_signal, no_signal, fee=fee,
                slippage=slippage, initial_balance=initial_balance,
            )
        else:
            entries, exits = normalized[selected]
            oos_result = run_backtest(
                oos_df,
                entries[oos_start:test_end],
                exits[oos_start:test_end],
                fee=fee,
                slippage=slippage,
                initial_balance=initial_balance,
            )
        folds.append({
            "train_start": train_start,
            "train_end_exclusive": test_start,
            "test_start": test_start,
            "test_end_exclusive": test_end,
            "training_scores": training_scores,
            "eligible_candidates": eligible,
            "selected_strategy": selected,
            "selection_status": "selected_after_hard_gate" if selected else "no_training_candidate_passed_hard_gate",
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
        "oos_closed_trade_count": sum(fold["test_result"]["trades"] for fold in folds),
        "folds": folds,
        "selection_score": "training net return percentage minus training max drawdown percentage, after the hard eligibility gate",
        "minimum_closed_trades": min_trades,
        "minimum_win_rate_pct": min_win_rate_pct,
        "simulation_only": True,
    }
