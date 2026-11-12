"""Causal, rule-based market regime labels for research and paper selection."""
import math
import pandas as pd

REGIME_NAMES = ("bullish", "bearish", "sideways", "high_volatility", "low_volatility")


def detect_market_regime(market, *, lookback=50):
    """Classify the latest completed candle using only trailing OHLCV data.

    This is a transparent heuristic, not a predictive model. Insufficient or
    invalid history returns unknown rather than guessing.
    """
    if not isinstance(market, pd.DataFrame) or not {"close", "high", "low"}.issubset(market.columns):
        raise ValueError("Market data must contain close, high and low columns")
    if isinstance(lookback, bool) or not isinstance(lookback, int) or lookback < 20:
        raise ValueError("lookback must be an integer >= 20")
    data = market.tail(lookback + 1).copy()
    if len(data) < lookback:
        return {"regime": "unknown", "confidence": 0.0, "trend_strength_pct": None, "volatility_pct": None}
    close = pd.to_numeric(data["close"], errors="coerce")
    high = pd.to_numeric(data["high"], errors="coerce")
    low = pd.to_numeric(data["low"], errors="coerce")
    if not all(math.isfinite(float(x)) for series in (close, high, low) for x in series):
        raise ValueError("Market data contains non-finite prices")
    if (close <= 0).any() or (high <= 0).any() or (low <= 0).any():
        raise ValueError("Market prices must be positive")
    returns = close.pct_change().dropna()
    volatility = float(returns.std(ddof=0) * math.sqrt(len(returns)) * 100)
    trend = float((close.iloc[-1] / close.iloc[0] - 1) * 100)
    # Volatility thresholds are screening heuristics, not calibrated forecasts.
    if volatility >= 8:
        regime = "high_volatility"
    elif volatility <= 0.8:
        regime = "low_volatility"
    elif trend >= 3:
        regime = "bullish"
    elif trend <= -3:
        regime = "bearish"
    else:
        regime = "sideways"
    confidence = min(0.95, max(0.1, abs(trend) / 10 if regime in ("bullish", "bearish") else abs(volatility - 0.8) / 8))
    return {"regime": regime, "confidence": round(confidence, 3),
            "trend_strength_pct": round(trend, 4), "volatility_pct": round(volatility, 4),
            "lookback": len(data)}
