import numpy as np
import pandas as pd
import pytest

from nexus.strategy_selection import screen_regime_candidates


def sample_market(n=600):
    t = np.arange(n, dtype=float)
    close = 100 + 0.025 * t + 3 * np.sin(t / 8) + 1.2 * np.sin(t / 2.7)
    open_ = close * (1 + 0.001 * np.sin(t / 3))
    high = np.maximum(open_, close) * 1.004
    low = np.minimum(open_, close) * 0.996
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})


def test_screening_reserves_holdout_and_never_approves_execution():
    result = screen_regime_candidates(sample_market(), train_fraction=0.7)
    assert result["screening_only"] is True
    assert result["execution_approved"] is False
    assert result["training_candles"] == 420
    assert result["holdout_candles_reserved"] == 180
    assert result["next_gate"] == "untouched out-of-sample validation and risk review"
    for regime, strategy_name in result["selected_candidates_by_regime"].items():
        metrics = result["by_regime"][regime]["candidate_metrics"]
        assert strategy_name is not None
        assert metrics["trades"] >= 100
        assert metrics["win_rate_pct"] >= 80
        assert metrics["net_return_pct"] > 0
        assert metrics["expectancy"] > 0
        assert metrics["profit_factor"] == "infinite" or metrics["profit_factor"] > 1


def test_screening_rejects_short_history_and_bad_parameters():
    with pytest.raises(ValueError, match="250"):
        screen_regime_candidates(sample_market(249))
    with pytest.raises(ValueError, match="train_fraction"):
        screen_regime_candidates(sample_market(), train_fraction=1.0)
    with pytest.raises(ValueError, match="min_trades"):
        screen_regime_candidates(sample_market(), min_trades=0)