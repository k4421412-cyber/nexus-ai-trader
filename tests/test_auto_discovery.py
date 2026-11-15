import pytest

from nexus import auto_discovery


class FakeExchange:
    has = {"fetchTickers": True}

    def __init__(self, options):
        self.options = options

    def load_markets(self):
        return {
            "BTC/USDT": {"symbol": "BTC/USDT", "base": "BTC", "quote": "USDT", "spot": True, "active": True},
            "ETH/USDT": {"symbol": "ETH/USDT", "base": "ETH", "quote": "USDT", "spot": True, "active": True},
            "USDC/USDT": {"symbol": "USDC/USDT", "base": "USDC", "quote": "USDT", "spot": True, "active": True},
            "BTC/USDC": {"symbol": "BTC/USDC", "base": "BTC", "quote": "USDC", "spot": True, "active": True},
            "BTC/USDT:USDT": {"symbol": "BTC/USDT:USDT", "base": "BTC", "quote": "USDT", "spot": False, "active": True, "contract": True},
            "BTCUP/USDT": {"symbol": "BTCUP/USDT", "base": "BTCUP", "quote": "USDT", "spot": True, "active": True},
            "DEAD/USDT": {"symbol": "DEAD/USDT", "base": "DEAD", "quote": "USDT", "spot": True, "active": False},
        }

    def fetch_tickers(self, symbols):
        assert symbols == ["BTC/USDT", "ETH/USDT"]
        return {
            "BTC/USDT": {"last": 100, "quoteVolume": 10_000_000, "bid": 99.9, "ask": 100.1, "high": 105, "low": 95},
            "ETH/USDT": {"last": 10, "quoteVolume": 500_000, "bid": 9.9, "ask": 10.1, "high": 11, "low": 9},
        }


def install_fake(monkeypatch):
    monkeypatch.setattr(auto_discovery.ccxt, "binance", FakeExchange)


def test_discovery_filters_non_spot_stable_leveraged_inactive_and_low_volume(monkeypatch):
    install_fake(monkeypatch)
    result = auto_discovery.discover_spot_candidates("binance")
    assert [row["symbol"] for row in result] == ["BTC/USDT"]
    assert result[0]["trade_approved"] is False
    assert result[0]["source"] == "centralized_spot"


def test_discovery_rejects_unsupported_exchange():
    with pytest.raises(ValueError, match="Exchange must be one of"):
        auto_discovery.discover_spot_candidates("unknown")


def test_discovery_rejects_bad_volume_and_spread():
    with pytest.raises(ValueError, match="volume"):
        auto_discovery.discover_spot_candidates("binance", min_quote_volume=0)
    with pytest.raises(ValueError, match="spread"):
        auto_discovery.discover_spot_candidates("binance", max_spread_pct=0)


def test_discovery_skips_missing_and_invalid_tickers(monkeypatch):
    class InvalidTickerExchange(FakeExchange):
        def fetch_tickers(self, symbols):
            return {"BTC/USDT": {"last": float("nan"), "quoteVolume": 9_000_000}}

    monkeypatch.setattr(auto_discovery.ccxt, "binance", InvalidTickerExchange)
    assert auto_discovery.discover_spot_candidates("binance") == []


def test_multi_exchange_scan_reports_errors_and_never_approves_trade(monkeypatch):
    install_fake(monkeypatch)
    result = auto_discovery.discover_across_exchanges(["binance", "okx"])
    assert result["scan_only"] is True
    assert result["live_orders_sent"] is False
    assert result["trade_approved"] is False
    assert result["errors"]["okx"]
    assert result["candidates"][0]["symbol"] == "BTC/USDT"
