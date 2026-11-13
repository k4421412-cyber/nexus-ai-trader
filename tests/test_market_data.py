import pytest

from nexus import market_data


class FakeExchange:
    def __init__(self, options):
        self.options = options

    def parse_timeframe(self, timeframe):
        if timeframe != "1m":
            raise ValueError("unsupported timeframe")
        return 60

    def milliseconds(self):
        return 200_000

    def fetch_ohlcv(self, symbol, timeframe, limit):
        return [
            [0, 100, 102, 99, 101, 10],
            [60_000, 101, 103, 100, 102, 11],
            [120_000, 102, 104, 101, 103, 12],
            [180_000, 103, 105, 102, 104, 13],
        ]


def install_fake_exchange(monkeypatch):
    monkeypatch.setattr(market_data.ccxt, "binance", FakeExchange)


def test_fetch_ohlcv_excludes_currently_forming_candle(monkeypatch):
    install_fake_exchange(monkeypatch)

    result = market_data.fetch_ohlcv("binance", "BTC/USDT", "1m", 50)

    assert result["timestamp"].tolist() == [0, 60_000, 120_000]
    assert len(result) == 3


def test_fetch_ohlcv_rejects_unsupported_timeframe(monkeypatch):
    install_fake_exchange(monkeypatch)

    with pytest.raises(ValueError, match="Unsupported timeframe"):
        market_data.fetch_ohlcv("binance", "BTC/USDT", "5m", 50)


def test_fetch_ohlcv_rejects_future_candle_timestamp(monkeypatch):
    install_fake_exchange(monkeypatch)

    class FutureExchange(FakeExchange):
        def fetch_ohlcv(self, symbol, timeframe, limit):
            rows = super().fetch_ohlcv(symbol, timeframe, limit)
            rows[-1][0] = 300_000
            return rows

    monkeypatch.setattr(market_data.ccxt, "binance", FutureExchange)

    with pytest.raises(RuntimeError, match="future"):
        market_data.fetch_ohlcv("binance", "BTC/USDT", "1m", 50)


def test_fetch_ohlcv_rejects_when_no_closed_candles_exist(monkeypatch):
    class FormingOnlyExchange(FakeExchange):
        def fetch_ohlcv(self, symbol, timeframe, limit):
            return [[180_000, 103, 105, 102, 104, 13]]

    monkeypatch.setattr(market_data.ccxt, "binance", FormingOnlyExchange)

    with pytest.raises(RuntimeError, match="fully closed"):
        market_data.fetch_ohlcv("binance", "BTC/USDT", "1m", 50)
