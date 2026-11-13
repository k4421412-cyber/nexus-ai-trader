import numpy as np
import pandas as pd
import pytest

from nexus.strategy_lab import (
    classify_market_regime, compare_all, compare_by_regime, evaluate_by_condition, qualifies_strategy,
    run_backtest, strategy_signals,
)


def sample_market(n=500):
    t = np.arange(n, dtype=float)
    close = 100 + 0.025 * t + 3 * np.sin(t / 8) + 1.2 * np.sin(t / 2.7)
    open_ = close * (1 + 0.001 * np.sin(t / 3))
    high = np.maximum(open_, close) * 1.004
    low = np.minimum(open_, close) * 0.996
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})


def test_strategy_library_has_twenty_boolean_signal_pairs():
    market = sample_market()
    signals = strategy_signals(market)
    assert len(signals) == 20
    for entry, exit_ in signals.values():
        assert len(entry) == len(market)
        assert len(exit_) == len(market)
        assert entry.dtype == bool
        assert exit_.dtype == bool


def test_all_strategy_signals_are_prefix_causal():
    market = sample_market(600)
    full = strategy_signals(market)
    prefix = strategy_signals(market.iloc[:350].copy())
    assert set(full) == set(prefix)
    for name in full:
        full_entry, full_exit = full[name]
        prefix_entry, prefix_exit = prefix[name]
        assert full_entry.iloc[:350].tolist() == prefix_entry.tolist(), name
        assert full_exit.iloc[:350].tolist() == prefix_exit.tolist(), name


def test_backtest_rejects_non_binary_and_non_finite_signals():
    market = pd.DataFrame({"open": [100.0, 101.0, 102.0], "close": [100.0, 101.0, 102.0]})
    for bad in (["False", False, True], [0, np.nan, 1], [0, 2, 1], np.zeros((3, 1))):
        try:
            run_backtest(market, bad, [False, False, False], fee=0, slippage=0)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid signal values or shape were accepted")


def test_backtest_uses_next_open_and_accounts_for_costs():
    market = pd.DataFrame({
        "open": [100.0, 100.0, 100.0, 110.0],
        "close": [100.0, 100.0, 105.0, 110.0],
    })
    entry = [False, True, False, False]
    exit_ = [False, False, True, False]
    free = run_backtest(market, entry, exit_, fee=0, slippage=0)
    costly = run_backtest(market, entry, exit_, fee=0.001, slippage=0.001)
    assert free["trades"] == 1
    assert costly["trades"] == 1
    assert costly["liquidation_balance"] < free["liquidation_balance"]


def test_backtest_force_closes_open_position_at_final_candle():
    market = pd.DataFrame({
        "open": [100.0, 100.0, 100.0],
        "close": [100.0, 100.0, 110.0],
    })
    result = run_backtest(
        market, [False, True, False], [False, False, False],
        fee=0, slippage=0, initial_balance=1000,
    )
    assert result["trades"] == 1
    assert result["open_position"] is False
    assert result["trade_log"][0]["forced_exit"] is True
    assert result["trade_log"][0]["exit_index"] == 2
    assert result["liquidation_balance"] == 1100
    assert result["equity_curve"][-1] == result["liquidation_balance"]


def test_comparison_returns_every_strategy_and_does_not_fake_qualification():
    results = compare_all(sample_market(), fee=0.001, slippage=0.0005)
    assert len(results) == 20
    assert all("qualifies" in row and "trades" in row for row in results)
    assert all(row["qualifies"] is False for row in results if row["trades"] < 100)


def passing_metrics(**overrides):
    metrics = {
        "trades": 100,
        "win_rate_pct": 80.0,
        "net_return_pct": 5.0,
        "expectancy": 0.5,
        "profit_factor": 1.5,
    }
    metrics.update(overrides)
    return metrics


def test_hard_gate_rejects_win_rate_below_80_percent():
    assert not qualifies_strategy(passing_metrics(win_rate_pct=79.99))


def test_hard_gate_accepts_exactly_80_percent_when_all_other_rules_pass():
    assert qualifies_strategy(passing_metrics(win_rate_pct=80.0))


def test_hard_gate_accepts_win_rate_above_80_percent():
    assert qualifies_strategy(passing_metrics(win_rate_pct=85.0))


def test_hard_gate_rejects_fewer_than_100_closed_trades():
    assert not qualifies_strategy(passing_metrics(trades=99, win_rate_pct=100.0))


def test_hard_gate_rejects_non_profitable_results_even_with_80_percent_win_rate():
    assert not qualifies_strategy(passing_metrics(net_return_pct=0.0))
    assert not qualifies_strategy(passing_metrics(expectancy=-0.01))
    assert not qualifies_strategy(passing_metrics(profit_factor=1.0))


def test_conditions_are_evaluated_separately_without_averaging():
    outcomes = evaluate_by_condition({
        "bull": passing_metrics(win_rate_pct=84.0),
        "bear": passing_metrics(win_rate_pct=79.0),
        "sideways": passing_metrics(win_rate_pct=80.0),
    })
    assert outcomes == {"bull": True, "bear": False, "sideways": True}


def test_infinite_profit_factor_is_allowed_only_with_other_gates_passed():
    assert qualifies_strategy(passing_metrics(profit_factor="infinite"))
    assert not qualifies_strategy(passing_metrics(profit_factor="infinite", trades=99))



def test_regime_classifier_uses_only_current_and_past_candles():
    market = sample_market(600)
    full_labels = classify_market_regime(market)
    prefix_labels = classify_market_regime(market.iloc[:350])
    assert full_labels.iloc[:350].tolist() == prefix_labels.tolist()
    assert set(full_labels.unique()).issubset({
        "bullish", "bearish", "sideways", "insufficient_data"
    })


def test_regime_classifier_marks_warmup_as_insufficient_data():
    labels = classify_market_regime(sample_market(250))
    assert (labels.iloc[:199] == "insufficient_data").all()
    assert labels.iloc[199:].isin(["bullish", "bearish", "sideways"]).all()


def test_all_twenty_strategies_are_evaluated_separately_by_regime():
    results = compare_by_regime(sample_market(600), fee=0.001, slippage=0.0005)
    assert len(results) == 20
    expected = {"bullish", "bearish", "sideways"}
    for row in results:
        assert set(row["by_regime"]) == expected
        for metrics in row["by_regime"].values():
            assert "qualifies" in metrics
            if metrics["trades"] < 100:
                assert metrics["qualifies"] is False



def test_forced_exit_deducts_final_fee_and_slippage_from_realized_metrics():
    market = pd.DataFrame({
        "open": [100.0, 100.0, 100.0],
        "close": [100.0, 100.0, 110.0],
    })
    result = run_backtest(
        market, [False, True, False], [False, False, False],
        fee=0.01, slippage=0.01, initial_balance=1000,
    )
    expected_units = 1000 / (100 * 1.01 * 1.01)
    expected_balance = expected_units * 110 * 0.99 * 0.99
    assert result["trades"] == 1
    assert result["trade_log"][0]["forced_exit"] is True
    assert np.isclose(result["liquidation_balance"], expected_balance)
    assert np.isclose(
        result["net_return_pct"],
        (expected_balance / 1000 - 1) * 100,
    )
    assert result["equity_curve"][-1] == result["liquidation_balance"]



def test_backtest_rejects_inconsistent_ohlc_and_non_chronological_timestamps():
    market = pd.DataFrame({
        "timestamp": [1000, 2000, 3000],
        "open": [100.0, 101.0, 102.0],
        "high": [101.0, 102.0, 103.0],
        "low": [99.0, 100.0, 101.0],
        "close": [100.0, 101.0, 102.0],
    })
    bad_ohlc = market.copy()
    bad_ohlc.loc[1, "high"] = 99.0
    with pytest.raises(ValueError, match="inconsistent"):
        run_backtest(bad_ohlc, [False] * 3, [False] * 3)
    bad_time = market.copy()
    bad_time.loc[2, "timestamp"] = 1500
    with pytest.raises(ValueError, match="chronological"):
        run_backtest(bad_time, [False] * 3, [False] * 3)


def test_regime_classifier_rejects_invalid_threshold_and_inconsistent_ohlc():
    market = sample_market(250)
    with pytest.raises(ValueError, match="ADX threshold"):
        classify_market_regime(market, adx_threshold=float("nan"))
    with pytest.raises(ValueError, match="ADX threshold"):
        classify_market_regime(market, adx_threshold=101)
    invalid = market.copy()
    invalid.loc[10, "open"] = invalid.loc[10, "high"] * 2
    with pytest.raises(ValueError, match="open prices"):
        classify_market_regime(invalid)
