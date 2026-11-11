import numpy as np
import pandas as pd

from nexus.strategy_lab import (\n    compare_all, evaluate_by_condition, qualifies_strategy,\n    run_backtest, strategy_signals,\n)


def sample_market(n=500):
    t = np.arange(n, dtype=float)
    close = 100 + 0.025 * t + 3 * np.sin(t / 8) + 1.2 * np.sin(t / 2.7)
    open_ = close * (1 + 0.001 * np.sin(t / 3))
    high = np.maximum(open_, close) * 1.004
    low = np.minimum(open_, close) * 0.996
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})


def test_strategy_library_has_eleven_boolean_signal_pairs():
    market = sample_market()
    signals = strategy_signals(market)
    assert len(signals) == 11
    for entry, exit_ in signals.values():
        assert len(entry) == len(market)
        assert len(exit_) == len(market)
        assert entry.dtype == bool
        assert exit_.dtype == bool


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


def test_comparison_returns_every_strategy_and_does_not_fake_qualification():
    results = compare_all(sample_market(), fee=0.001, slippage=0.0005)
    assert len(results) == 11
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
