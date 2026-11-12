import numpy as np
import pandas as pd
import pytest

from nexus.evaluation import walk_forward_evaluate


def market_data(n=12):
    close = np.linspace(100.0, 112.0, n)
    return pd.DataFrame({
        "open": close,
        "close": close,
        "ema20": close + 2.0,
        "ema50": close,
    })


def test_walk_forward_uses_chronological_non_overlapping_test_folds():
    market = market_data()
    candidates = {
        "always_in": np.ones(len(market), dtype=bool),
        "never_in": np.zeros(len(market), dtype=bool),
    }
    result = walk_forward_evaluate(
        market, candidates, train_size=6, test_size=3, fee=0, slippage=0
    )
    assert result["simulation_only"] is True
    assert result["fold_count"] == 2
    assert [
        (fold["train_start"], fold["train_end_exclusive"],
         fold["test_start"], fold["test_end_exclusive"])
        for fold in result["folds"]
    ] == [(0, 6, 6, 9), (3, 9, 9, 12)]
    assert all(fold["test_start"] >= fold["train_end_exclusive"] for fold in result["folds"])


def test_walk_forward_first_fold_is_not_influenced_by_future_test_data():
    market = market_data()
    candidates = {
        "always_in": np.ones(len(market), dtype=bool),
        "never_in": np.zeros(len(market), dtype=bool),
    }
    baseline = walk_forward_evaluate(
        market, candidates, train_size=6, test_size=3, fee=0, slippage=0
    )
    changed_future = market.copy()
    changed_future.loc[9:, ["open", "close", "ema20", "ema50"]] *= 4
    changed = walk_forward_evaluate(
        changed_future, candidates, train_size=6, test_size=3, fee=0, slippage=0
    )
    assert baseline["folds"][0]["training_scores"] == changed["folds"][0]["training_scores"]
    assert baseline["folds"][0]["selected_strategy"] == changed["folds"][0]["selected_strategy"]
    assert baseline["folds"][0]["test_result"] == changed["folds"][0]["test_result"]


@pytest.mark.parametrize("kwargs", [
    {"train_size": 1, "test_size": 3},
    {"train_size": 6, "test_size": 0},
    {"train_size": 6, "test_size": 3, "step_size": 0},
    {"train_size": 6, "test_size": 3, "step_size": 2},
])
def test_walk_forward_rejects_invalid_window_sizes(kwargs):
    with pytest.raises(ValueError):
        walk_forward_evaluate(
            market_data(),
            {"candidate": np.zeros(12, dtype=bool)},
            **kwargs,
        )


def test_walk_forward_rejects_empty_candidates_and_short_history():
    with pytest.raises(ValueError):
        walk_forward_evaluate(market_data(), {}, train_size=6, test_size=3)
    with pytest.raises(ValueError):
        walk_forward_evaluate(
            market_data(5),
            {"candidate": np.zeros(5, dtype=bool)},
            train_size=6,
            test_size=3,
        )


def test_walk_forward_uses_entry_and_exit_signals_for_strategy_candidates():
    market = pd.DataFrame({
        "open": [100.0, 100.0, 100.0, 100.0, 110.0, 110.0, 110.0, 110.0],
        "close": [100.0, 100.0, 100.0, 100.0, 110.0, 110.0, 110.0, 110.0],
        "ema20": [100.0] * 8,
        "ema50": [100.0] * 8,
    })
    entry = np.array([False, True, False, False, False, False, False, False])
    exit_ = np.array([False, False, False, True, False, False, False, False])
    result = walk_forward_evaluate(
        market,
        {"paired_strategy": (entry, exit_)},
        train_size=4,
        test_size=4,
        fee=0,
        slippage=0,
    )
    assert result["fold_count"] == 1
    assert result["folds"][0]["selected_strategy"] == "paired_strategy"
    assert result["folds"][0]["test_result"]["trades"] == 1
    assert result["folds"][0]["test_result"]["trade_log"][0]["forced_exit"] is False


def test_walk_forward_rejects_mismatched_paired_signal_lengths():
    market = market_data()
    with pytest.raises(ValueError, match="matching"):
        walk_forward_evaluate(
            market,
            {"bad_pair": (np.zeros(12, dtype=bool), np.zeros(11, dtype=bool))},
            train_size=6,
            test_size=3,
        )
