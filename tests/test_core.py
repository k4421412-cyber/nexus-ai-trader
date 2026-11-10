import pandas as pd
import pytest

from nexus.indicators import add_indicators
from nexus.paper import PaperWallet
from nexus.strategies import backtest, ema_rsi_signals


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
    frame[column] = frame[column].astype(object)
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


@pytest.mark.parametrize(
    "rows",
    [
        [[1000, 100, 105, 99, 102, 10], [2000, 102, float("inf"), 101, 104, 12]],
        [[2000, 100, 105, 99, 102, 10], [1000, 102, 106, 101, 104, 12]],
        [[1000, 100, 105, 99, 102, 10], [1000, 102, 106, 101, 104, 12]],
        [[1000, 100, 99, 98, 102, 10], [2000, 102, 106, 101, 104, 12]],
        [[1000, 100, 105, 103, 102, 10], [2000, 102, 106, 101, 104, 12]],
    ],
)
def test_market_data_rejects_invalid_ohlcv(monkeypatch, rows):
    from nexus import market_data

    class FakeExchange:
        def __init__(self, config):
            self.config = config

        def fetch_ohlcv(self, symbol, timeframe, limit):
            return rows

    monkeypatch.setattr(market_data.ccxt, "binance", FakeExchange)
    with pytest.raises(RuntimeError):
        market_data.fetch_ohlcv()


def test_market_data_accepts_valid_ohlcv(monkeypatch):
    from nexus import market_data

    rows = [
        [1000, 100, 105, 99, 102, 10],
        [2000, 102, 106, 101, 104, 12],
    ]

    class FakeExchange:
        def __init__(self, config):
            self.config = config

        def fetch_ohlcv(self, symbol, timeframe, limit):
            return rows

    monkeypatch.setattr(market_data.ccxt, "binance", FakeExchange)
    result = market_data.fetch_ohlcv()
    assert len(result) == 2
    assert result["timestamp"].is_monotonic_increasing


@pytest.mark.parametrize("signals", [["False", True], [0, 1], [[True], [False]]])
def test_backtest_rejects_non_boolean_or_multidimensional_signals(signals):
    frame = pd.DataFrame({
        "open": [100, 100], "close": [100, 100],
        "ema20": [1, 1], "ema50": [2, 2],
    })
    with pytest.raises(ValueError, match="Signals"):
        backtest(frame, signals)


def test_backtest_treats_missing_boolean_signal_as_false():
    frame = pd.DataFrame({
        "open": [100, 100], "close": [100, 100],
        "ema20": [1, 1], "ema50": [2, 2],
    })
    result = backtest(frame, [None, False])
    assert result["open_position"] is False
    assert result["final_balance"] == pytest.approx(1000)


def test_backtest_reports_liquidation_value_after_exit_costs():
    frame = pd.DataFrame({
        "open": [100, 100],
        "close": [100, 110],
        "ema20": [1, 1],
        "ema50": [2, 2],
    })
    result = backtest(frame, [True, False], fee=0.01, slippage=0.01)
    assert result["open_position"] is True
    assert result["estimated_liquidation_balance"] < result["marked_to_market_balance"]
    assert result["estimated_liquidation_return_pct"] < result["net_return_pct"]


def test_backtest_reports_trade_expectancy_and_market_exposure():
    frame = pd.DataFrame({
        "open": [100, 100, 110, 120],
        "close": [100, 100, 110, 120],
        "ema20": [1, 2, 1, 1],
        "ema50": [2, 1, 2, 2],
    })
    result = backtest(frame, [True, False, False, False], fee=0, slippage=0)
    assert result["closed_trade_count"] == 1
    assert result["expectancy_per_closed_trade"] == pytest.approx(200)
    assert result["average_win"] == pytest.approx(200)
    assert result["average_loss"] is None
    assert result["gross_profit"] == pytest.approx(200)
    assert result["gross_loss"] == pytest.approx(0)
    assert result["exposure_pct"] == pytest.approx(66.67, abs=0.01)


def test_ema_rsi_signals_detect_valid_bullish_crossover():
    frame = pd.DataFrame({
        "ema20": [9.0, 11.0, 12.0],
        "ema50": [10.0, 10.0, 10.5],
        "rsi": [55.0, 60.0, 65.0],
    })
    result = ema_rsi_signals(frame)
    assert result.tolist() == [False, True, False]


def test_ema_rsi_signals_reject_overbought_crossover():
    frame = pd.DataFrame({
        "ema20": [9.0, 11.0],
        "ema50": [10.0, 10.0],
        "rsi": [60.0, 70.0],
    })
    assert ema_rsi_signals(frame).tolist() == [False, False]


def test_ema_rsi_signals_require_indicator_columns():
    with pytest.raises(ValueError, match="Missing signal columns"):
        ema_rsi_signals(pd.DataFrame({"ema20": [1.0], "ema50": [0.5]}))


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
def test_indicators_reject_non_finite_ohlc(bad):
    frame = pd.DataFrame({"high": [101, bad], "low": [99, 99], "close": [100, 100]})
    with pytest.raises(ValueError, match="non-finite"):
        add_indicators(frame)


def test_indicators_reject_inconsistent_ohlc():
    frame = pd.DataFrame({"high": [99], "low": [101], "close": [100]})
    with pytest.raises(ValueError, match="inconsistent"):
        add_indicators(frame)


def test_paper_wallet_rejects_non_numeric_inputs():
    with pytest.raises(ValueError, match="numeric"):
        PaperWallet("not-cash")
    wallet = PaperWallet(100)
    with pytest.raises(ValueError, match="numeric"):
        wallet.buy("BTC/USDT", "many", 10)


def test_paper_wallet_rejects_cash_overflow_on_sale():
    wallet = PaperWallet(1e308)
    wallet.positions["BTC/USDT"] = 1e308
    with pytest.raises(ValueError, match="Invalid order value"):
        wallet.sell("BTC/USDT", 1e308, 2)
    assert wallet.cash == 1e308
    assert wallet.positions["BTC/USDT"] == 1e308


@pytest.mark.parametrize("bad_rsi", [float("inf"), -1, 101, "bad"])
def test_ema_rsi_signals_reject_invalid_indicator_values(bad_rsi):
    frame = pd.DataFrame({
        "ema20": [9.0, 11.0],
        "ema50": [10.0, 10.0],
        "rsi": [50.0, bad_rsi],
    })
    with pytest.raises(ValueError):
        ema_rsi_signals(frame)


def test_ema_rsi_signals_accept_numeric_string_indicators():
    frame = pd.DataFrame({
        "ema20": ["9", "11"],
        "ema50": ["10", "10"],
        "rsi": ["50", "60"],
    })
    assert ema_rsi_signals(frame).tolist() == [False, True]


def test_ema_rsi_signals_treats_warmup_rsi_as_no_signal():
    frame = pd.DataFrame({
        "ema20": [9.0, 11.0, 12.0],
        "ema50": [10.0, 10.0, 10.5],
        "rsi": [float("nan"), 60.0, 65.0],
    })
    assert ema_rsi_signals(frame).tolist() == [False, True, False]
