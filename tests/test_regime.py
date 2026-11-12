import pandas as pd
import pytest
from nexus.regime import detect_market_regime


def test_insufficient_history_is_unknown():
    df = pd.DataFrame({"close": [100] * 5, "high": [101] * 5, "low": [99] * 5})
    assert detect_market_regime(df)["regime"] == "unknown"


def test_detects_bullish_trend():
    close = [100 + i for i in range(60)]
    df = pd.DataFrame({"close": close, "high": [x + 1 for x in close], "low": [x - 1 for x in close]})
    assert detect_market_regime(df)["regime"] == "bullish"


def test_rejects_invalid_prices():
    df = pd.DataFrame({"close": [100] * 30, "high": [101] * 30, "low": [99] * 30})
    df.loc[10, "close"] = float("nan")
    with pytest.raises(ValueError, match="non-finite"):
        detect_market_regime(df)


def test_requires_valid_lookback():
    df = pd.DataFrame({"close": [100] * 30, "high": [101] * 30, "low": [99] * 30})
    with pytest.raises(ValueError):
        detect_market_regime(df, lookback=5)
