import numpy as np
import pandas as pd

from nexus.indicators import add_indicators
from nexus.strategies import compare_strategies, strategy_signal_sets


def _market_frame(size=180):
    index = np.arange(size, dtype=float)
    close = 100 + 0.04 * index + 5 * np.sin(index / 4)
    return pd.DataFrame({
        "open": close * (1 - 0.001 * np.cos(index)),
        "high": close + 1.5,
        "low": close - 1.5,
        "close": close,
        "volume": np.full(size, 1000.0),
    })


def test_strategy_signal_sets_returns_broad_aligned_boolean_entry_exit_pairs():
    market = add_indicators(_market_frame())
    signal_sets = strategy_signal_sets(market)

    assert len(signal_sets) >= 20
    expected_families = {
        "EMA9/EMA21 crossover", "SMA20/SMA50 crossover",
        "MACD zero-line momentum", "Bollinger breakout",
        "Donchian 20-bar breakout", "RSI momentum",
        "Stochastic reversal", "10-bar ROC momentum",
        "ATR channel breakout", "Keltner channel reversion",
        "ADX directional trend", "Bullish engulfing",
        "Hammer reversal", "Volume-confirmed breakout",
    }
    assert expected_families.issubset(signal_sets)
    for name, pair in signal_sets.items():
        assert isinstance(name, str) and name
        assert isinstance(pair, tuple) and len(pair) == 2
        entries, exits = pair
        assert len(entries) == len(market)
        assert len(exits) == len(market)
        assert entries.dtype == bool
        assert exits.dtype == bool
        assert not entries.isna().any()
        assert not exits.isna().any()


def test_compare_strategies_returns_complete_ranked_reports():
    market = add_indicators(_market_frame())
    reports = compare_strategies(market, fee=0.001, slippage=0.0005)

    assert len(reports) >= 20
    assert all(report["minimum_trades_required"] == 100 for report in reports)
    assert all(report["sample_sufficient"] == (report["closed_trade_count"] >= 100) for report in reports)
    assert all(report["candidate_eligible"] == (
        report["sample_sufficient"]
        and report["passes_win_rate_threshold"]
        and report["positive_expectancy"]
        and (report["profit_factor"] == "infinite" or (
            isinstance(report["profit_factor"], (int, float)) and report["profit_factor"] > 1
        ))
    ) for report in reports)
    ranked = [
        (item["candidate_eligible"], item["sample_sufficient"], item["risk_adjusted_score"])
        for item in reports
    ]
    assert ranked == sorted(ranked, reverse=True)

    required_fields = {
        "strategy",
        "estimated_liquidation_return_pct",
        "closed_trade_count",
        "win_rate_pct",
        "max_drawdown_pct",
        "profit_factor",
        "expectancy_per_closed_trade",
        "sample_sufficient",
        "candidate_eligible",
        "risk_adjusted_score",
    }
    for report in reports:
        assert required_fields.issubset(report)
        assert report["initial_balance"] == 1000.0
        assert report["max_drawdown_pct"] >= 0
        assert report["closed_trade_count"] >= 0


def test_strategy_comparison_is_deterministic():
    market = add_indicators(_market_frame())
    first = compare_strategies(market)
    second = compare_strategies(market)

    assert [
        (item["strategy"], item["estimated_liquidation_return_pct"], item["closed_trade_count"])
        for item in first
    ] == [
        (item["strategy"], item["estimated_liquidation_return_pct"], item["closed_trade_count"])
        for item in second
    ]


def test_strategy_library_rejects_missing_ohlc_columns():
    market = add_indicators(_market_frame()).drop(columns=["high"])
    try:
        strategy_signal_sets(market)
    except ValueError as exc:
        assert "high" in str(exc)
    else:
        raise AssertionError("Missing OHLC data should be rejected")
