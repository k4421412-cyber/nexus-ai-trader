import pandas as pd
import pytest

from nexus.indicators import add_indicators
from nexus.paper import PaperWallet


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
