import pandas as pd
import pytest

from nexus.indicators import add_indicators
from nexus.paper import PaperWallet
from nexus.strategies import backtest


def test_rsi_is_100_in_persistent_uptrend():
    close = [100 + i for i in range(40)]
    frame = pd.DataFrame({"close": close, "high": [v + 1 for v in close], "low": [v - 1 for v in close]})
    result = add_indicators(frame)
    assert result["rsi"].iloc[-1] == 100.0


def test_rsi_is_neutral_in_flat_market():
    frame = pd.DataFrame({"close": [100] * 40, "high": [101] * 40, "low": [99] * 40})
    result = add_indicators(frame)
    assert result["rsi"].iloc[-1] == 50.0


def test_indicators_reject_missing_columns():
    with pytest.raises(ValueError):
        add_indicators(pd.DataFrame({"close": [100]}))


def test_paper_wallet_buy_sell_round_trip():
    wallet = PaperWallet(1000)
    wallet.buy("BTC/USDT", 0.01, 20000)
    assert wallet.cash == pytest.approx(800)
    wallet.sell("BTC/USDT", 0.01, 21000)
    assert wallet.cash == pytest.approx(1010)
    assert "BTC/USDT" not in wallet.positions


@pytest.mark.parametrize("quantity,price", [(-1, 10), (1, 0), (float("nan"), 10), (float("inf"), 10)])
def test_paper_wallet_rejects_invalid_orders(quantity, price):
    wallet = PaperWallet(1000)
    with pytest.raises(ValueError):
        wallet.buy("BTC/USDT", quantity, price)


def test_paper_wallet_rejects_overselling():
    wallet = PaperWallet(1000)
    wallet.buy("BTC/USDT", 0.01, 10000)
    with pytest.raises(ValueError):
        wallet.sell("BTC/USDT", 0.02, 10000)


def test_backtest_fills_on_next_open_not_signal_candle_close():
    frame = pd.DataFrame({
        "open": [100, 120, 130],
        "close": [110, 125, 140],
        "ema20": [1, 2, 3],
        "ema50": [2, 1, 1],
    })
    signals = pd.Series([True, False, False])
    result = backtest(frame, signals, fee=0, slippage=0)
    assert result["open_position"] is True
    assert result["final_balance"] == pytest.approx(1000 * 140 / 120, abs=0.01)


def test_backtest_includes_fees_and_slippage():
    frame = pd.DataFrame({
        "open": [100, 100, 100],
        "close": [100, 100, 100],
        "ema20": [1, 2, 3],
        "ema50": [2, 1, 1],
    })
    result = backtest(frame, pd.Series([True, False, False]), fee=0.01, slippage=0.01)
    assert result["final_balance"] < 1000
    assert result["open_position"] is True


def test_backtest_closes_position_on_next_open_after_exit_condition():
    frame = pd.DataFrame({
        "open": [100, 100, 110, 120],
        "close": [100, 100, 110, 120],
        "ema20": [1, 2, 1, 1],
        "ema50": [2, 1, 2, 2],
    })
    signals = pd.Series([True, False, False, False])
    result = backtest(frame, signals, fee=0, slippage=0)
    assert result["closed_trade_count"] == 1
    assert result["open_position"] is False
    assert result["final_balance"] == pytest.approx(1200)


@pytest.mark.parametrize("fee,slippage", [(-0.1, 0), (1, 0), (0, -0.1), (0, 1)])
def test_backtest_rejects_invalid_costs(fee, slippage):
    frame = pd.DataFrame({
        "open": [100, 100], "close": [100, 100],
        "ema20": [1, 1], "ema50": [2, 2],
    })
    with pytest.raises(ValueError):
        backtest(frame, pd.Series([False, False]), fee=fee, slippage=slippage)


@pytest.mark.parametrize(
    "column,value",
    [
        ("open", float("inf")),
        ("close", float("-inf")),
        ("ema20", float("nan")),
        ("ema50", "not-a-number"),
    ],
)
def test_backtest_rejects_non_finite_or_non_numeric_market_data(column, value):
    frame = pd.DataFrame({
        "open": [100, 100],
        "close": [100, 100],
        "ema20": [1, 1],
        "ema50": [2, 2],
    })
    frame.loc[1, column] = value
    with pytest.raises(ValueError, match="non-finite"):
        backtest(frame, pd.Series([False, False]))


def test_backtest_without_signals_preserves_initial_balance():
    frame = pd.DataFrame({
        "open": [100, 105],
        "close": [102, 106],
        "ema20": [1, 1],
        "ema50": [2, 2],
    })
    result = backtest(frame, pd.Series([False, False]))
    assert result["final_balance"] == pytest.approx(1000)
    assert result["net_return_pct"] == pytest.approx(0)
    assert result["closed_trade_count"] == 0
    assert result["max_drawdown_pct"] == pytest.approx(0)
    assert result["profit_factor"] is None


def test_backtest_rejects_mismatched_signal_length():
    frame = pd.DataFrame({
        "open": [100, 100],
        "close": [100, 100],
        "ema20": [1, 1],
        "ema50": [2, 2],
    })
    with pytest.raises(ValueError, match="Signals length"):
        backtest(frame, pd.Series([True]))


def test_backtest_rejects_non_positive_initial_balance():
    frame = pd.DataFrame({
        "open": [100, 100],
        "close": [100, 100],
        "ema20": [1, 1],
        "ema50": [2, 2],
    })
    with pytest.raises(ValueError, match="Initial balance"):
        backtest(frame, pd.Series([False, False]), initial_balance=0)
