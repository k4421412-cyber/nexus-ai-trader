import numpy as np
import pandas as pd
import pytest

from nexus.strategy_selection import screen_regime_candidates, validate_regime_candidates


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

def test_holdout_changes_cannot_change_training_selection():
    market = sample_market()
    baseline = screen_regime_candidates(market)
    changed = market.copy()
    changed.loc[420:, ["open", "high", "low", "close"]] *= 3
    altered = screen_regime_candidates(changed)
    assert baseline["selected_candidates_by_regime"] == altered["selected_candidates_by_regime"]
    assert baseline["by_regime"] == altered["by_regime"]

def test_holdout_validation_is_separate_and_never_grants_global_execution_permission():
    from nexus.strategy_selection import validate_regime_candidates

    result = validate_regime_candidates(sample_market())
    assert result["screening_only"] is True
    assert result["execution_approved"] is False
    assert result["holdout_validation"].keys() <= result["selected_candidates_by_regime"].keys()
    assert result["validated_candidates_by_regime"].keys() <= result["holdout_validation"].keys()
    for regime, details in result["holdout_validation"].items():
        assert details["metrics"]["trades"] >= 0
        assert details["passes_holdout"] is False or details["strategy"] == result["selected_candidates_by_regime"][regime]
    assert result["next_gate"] == "replication across additional symbols/timeframes and risk review"

def test_cross_market_replication_requires_same_strategy_in_each_dataset(monkeypatch):
    from nexus import strategy_selection

    results = {
        "market-a": {"validated_candidates_by_regime": {"bullish": "EMA 9/21", "bearish": "MACD"}},
        "market-b": {"validated_candidates_by_regime": {"bullish": "EMA 9/21", "bearish": "RSI"}},
    }
    market_a = sample_market()
    market_a.attrs["test_key"] = "market-a"
    market_b = sample_market()
    market_b.attrs["test_key"] = "market-b"
    monkeypatch.setattr(
        strategy_selection, "validate_regime_candidates",
        lambda frame, **kwargs: results[frame.attrs["test_key"]]
    )
    result = strategy_selection.validate_across_markets({"market-a": market_a, "market-b": market_b})
    assert result["market_count"] == 2
    assert result["replicated_candidates_by_regime"]["bullish"] == ["EMA 9/21"]
    assert result["replicated_candidates_by_regime"]["bearish"] == []
    assert result["execution_approved"] is False


def test_cross_market_replication_requires_at_least_two_datasets():
    from nexus.strategy_selection import validate_across_markets

    with pytest.raises(ValueError, match="two"):
        validate_across_markets({"BTC/USDT": sample_market()})


@pytest.mark.parametrize("kwargs", [
    {"fee": -0.01},
    {"fee": float("nan")},
    {"slippage": 1.0},
    {"initial_balance": 0},
    {"initial_balance": float("inf")},
])
def test_screening_rejects_invalid_cost_and_balance_inputs(kwargs):
    with pytest.raises(ValueError):
        screen_regime_candidates(sample_market(), **kwargs)


def test_cross_market_validation_caps_dataset_count_and_requires_frames():
    from nexus.strategy_selection import validate_across_markets

    with pytest.raises(ValueError, match="12"):
        validate_across_markets({f"market-{i}": sample_market() for i in range(13)})
    with pytest.raises(ValueError, match="DataFrame"):
        validate_across_markets({"market-a": sample_market(), "market-b": "not-a-dataframe"})


def test_screening_rejects_non_chronological_market_timestamps():
    market = sample_market()
    market["timestamp"] = np.arange(len(market), dtype=np.int64)
    market.loc[len(market) - 1, "timestamp"] = 1
    with pytest.raises(ValueError, match="chronological"):
        screen_regime_candidates(market)
