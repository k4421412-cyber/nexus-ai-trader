import numpy as np
import pandas as pd
import pytest

from nexus.evaluation import walk_forward_evaluate


def _market(size):
    close = np.linspace(100, 140, size)
    return pd.DataFrame({
        "open": close,
        "close": close,
        "ema20": close * 1.001,
        "ema50": close,
    })


def test_walk_forward_uses_past_training_window_and_disjoint_oos_folds():
    size = 50
    market = _market(size)
    candidate_a = np.zeros(size, dtype=bool)
    candidate_b = np.zeros(size, dtype=bool)
    candidate_a[5::4] = True
    candidate_b[7::5] = True
    result = walk_forward_evaluate(
        market, {"A": candidate_a, "B": candidate_b},
        train_size=20, test_size=10, fee=0, slippage=0,
    )
    assert result["fold_count"] == 3
    folds = result["folds"]
    assert folds[0]["test_start"] == 20
    assert folds[0]["test_end_exclusive"] == folds[1]["test_start"]
    assert folds[1]["test_end_exclusive"] == folds[2]["test_start"]
    assert all(f["train_end_exclusive"] == f["test_start"] for f in folds)
    assert result["simulation_only"] is True


def test_walk_forward_does_not_use_future_test_prices_for_candidate_selection():
    market = _market(40)
    a = np.zeros(40, dtype=bool)
    b = np.zeros(40, dtype=bool)
    a[3::3] = True
    b[4::4] = True
    first = walk_forward_evaluate(market, {"A": a, "B": b}, train_size=20, test_size=10, fee=0, slippage=0)
    changed_future = market.copy()
    changed_future.loc[20:, ["open", "close"]] *= 4
    second = walk_forward_evaluate(changed_future, {"A": a, "B": b}, train_size=20, test_size=10, fee=0, slippage=0)
    assert first["folds"][0]["selected_strategy"] == second["folds"][0]["selected_strategy"]
    assert first["folds"][0]["training_scores"] == second["folds"][0]["training_scores"]


@pytest.mark.parametrize("kwargs", [
    {"train_size": 1, "test_size": 5},
    {"train_size": 10, "test_size": 0},
    {"train_size": 10, "test_size": 5, "step_size": 0},
])
def test_walk_forward_rejects_invalid_window_sizes(kwargs):
    with pytest.raises(ValueError):
        walk_forward_evaluate(_market(30), {"A": np.zeros(30, dtype=bool)}, **kwargs)


def test_walk_forward_requires_causal_signal_sequence_shape():
    with pytest.raises(ValueError, match="length"):
        walk_forward_evaluate(_market(30), {"A": [True, False]}, train_size=10, test_size=5)
