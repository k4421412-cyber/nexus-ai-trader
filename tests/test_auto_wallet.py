import numpy as np
import pandas as pd
import pytest

from nexus.auto_wallet import simulate_to_goal


def sample_market(n=8):
    close = np.array([100, 100, 100, 100, 110, 120, 130, 140], dtype=float)[:n]
    return pd.DataFrame({
        "open": close,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "ema20": np.array([99, 99, 99, 99, 101, 105, 110, 120], dtype=float)[:n],
        "ema50": np.array([100, 100, 100, 100, 100, 100, 100, 100], dtype=float)[:n],
        "rsi": np.array([50] * n, dtype=float),
    })


def test_simulation_is_explicitly_paper_only_and_respects_target():
    market = sample_market()
    # Inject a valid crossover signal at candle 3.
    market.loc[2, "ema20"] = 99
    market.loc[2, "ema50"] = 100
    market.loc[3, "ema20"] = 101
    market.loc[3, "ema50"] = 100
    result = simulate_to_goal(
        market, initial_balance=1, target_balance=1.01,
        max_loss_pct=20, max_position_pct=100, fee_pct=0, slippage_pct=0,
    )
    assert result["simulation_only"] is True
    assert result["live_orders_sent"] is False
    assert result["final_balance"] >= 1
    assert result["status"] in {"target_reached", "target_touched_before_exit_costs", "history_exhausted"}


def test_rejects_target_not_above_initial_balance():
    with pytest.raises(ValueError, match="greater than"):
        simulate_to_goal(sample_market(), initial_balance=1, target_balance=1)


@pytest.mark.parametrize("kwargs", [
    {"initial_balance": 0},
    {"target_balance": 0},
    {"max_loss_pct": 0},
    {"max_loss_pct": 51},
    {"max_position_pct": 0},
    {"max_position_pct": 101},
    {"fee_pct": -0.1},
    {"slippage_pct": float("nan")},
])
def test_rejects_invalid_risk_and_balance_settings(kwargs):
    with pytest.raises(ValueError):
        simulate_to_goal(sample_market(), **kwargs)


def test_rejects_missing_or_non_finite_market_data():
    with pytest.raises(ValueError, match="Missing market columns"):
        simulate_to_goal(pd.DataFrame({"open": [1, 2, 3]}))
    bad = sample_market()
    bad.loc[2, "close"] = np.nan
    with pytest.raises(ValueError, match="finite"):
        simulate_to_goal(bad)


def test_rejects_unknown_or_research_only_strategy():
    with pytest.raises(ValueError, match="Unknown or non-executable"):
        simulate_to_goal(sample_market(), strategy_name="Supertrend")


def test_all_eleven_implemented_strategies_can_run_in_paper_mode():
    from nexus.strategy_lab import strategy_signals

    market = sample_market()
    for strategy_name in strategy_signals(market):
        result = simulate_to_goal(
            market, strategy_name=strategy_name, initial_balance=100,
            target_balance=1000, max_position_pct=100, fee_pct=0, slippage_pct=0,
        )
        assert result["simulation_only"] is True
        assert result["live_orders_sent"] is False
        assert result["strategy"] == strategy_name


def test_trade_fees_and_slippage_reduce_result():
    market = sample_market()
    free = simulate_to_goal(market, initial_balance=100, target_balance=1000,
                            max_position_pct=100, fee_pct=0, slippage_pct=0,
                            strategy_name="EMA 9/21 crossover")
    costly = simulate_to_goal(market, initial_balance=100, target_balance=1000,
                              max_position_pct=100, fee_pct=1, slippage_pct=1,
                              strategy_name="EMA 9/21 crossover")
    assert costly["final_balance"] < free["final_balance"]
