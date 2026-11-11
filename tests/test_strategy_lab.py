import numpy as np
import pandas as pd

from nexus.strategy_lab import compare_all, run_backtest, strategy_signals


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
