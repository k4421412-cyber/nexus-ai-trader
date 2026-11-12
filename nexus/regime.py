"""Causal, rule-based market regime labels for research and paper selection."""
import math
import pandas as pd

REGIME_NAMES = ("bullish", "bearish", "sideways", "high_volatility", "low_volatility")


def detect_market_regime(market, *, lookback=50):
    """Classify the latest completed candle using trailing OHLCV data.

    This transparent heuristic is not predictive. Invalid observations raise
    ValueError; insufficient valid history returns unknown.
    """
    required = {"close", "high", "low"}
    if not isinstance(market, pd.DataFrame) or not required.issubset(market.columns):
        raise ValueError("Market data must contain close, high and low columns")
    if isinstance(lookback, bool) or not isinstance(lookback, int) or lookback < 20:
        raise ValueError("lookback must be an integer >= 20")

    data = market.tail(lookback + 1).copy()
    close = pd.to_numeric(data["close"], errors="coerce")
    high = pd.to_numeric(data["high"], errors="coerce")
    low = pd.to_numeric(data["low"], errors="coerce")
    for series in (close, high, low):
        if not all(math.isfinite(float(value)) for value in series):
            raise ValueError("Market data contains non-finite prices")
        if (series <= 0).any():
            raise ValueError("Market prices must be positive")
    if (high < low).any() or (close > high).any() or (close < low).any():
        raise ValueError("OHLC prices are inconsistent")

    if len(data) < lookback:
        return {"regime": "unknown", "confidence": 0.0, "trend_strength_pct": None, "volatility_pct": None, "lookback": len(data)}

    returns = close.pct_change().dropna()
    volatility = float(returns.std(ddof=0) * math.sqrt(len(returns)) * 100)
    trend = float((close.iloc[-1] / close.iloc[0] - 1) * 100)
    # Strong direction takes precedence over low realized volatility.
    if volatility >= 8:
        regime = "high_volatility"
    elif trend >= 3:
        regime = "bullish"
    elif trend <= -3:
        regime = "bearish"
    elif volatility <= 0.8:
        regime = "low_volatility"
    else:
        regime = "sideways"

    if regime in ("bullish", "bearish"):
        confidence = min(0.95, max(0.1, abs(trend) / 10))
    elif regime == "high_volatility":
        confidence = min(0.95, max(0.1, volatility / 16))
    else:
        confidence = min(0.95, max(0.1, abs(volatility - 0.8) / 8))
    return {"regime": regime, "confidence": round(confidence, 3), "trend_strength_pct": round(trend, 4), "volatility_pct": round(volatility, 4), "lookback": len(data)}
