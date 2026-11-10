import pandas as pd


def add_indicators(df):
    required = {"high", "low", "close"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    if df.empty:
        raise ValueError("Cannot calculate indicators for empty market data")

    x = df.copy()
    close = pd.to_numeric(x["close"], errors="coerce")
    high = pd.to_numeric(x["high"], errors="coerce")
    low = pd.to_numeric(x["low"], errors="coerce")
    if close.isna().any() or high.isna().any() or low.isna().any():
        raise ValueError("OHLC data contains missing or non-numeric values")
    if (close <= 0).any() or (high <= 0).any() or (low <= 0).any():
        raise ValueError("OHLC prices must be positive")

    x["ema20"] = close.ewm(span=20, adjust=False).mean()
    x["ema50"] = close.ewm(span=50, adjust=False).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.mask((loss == 0) & (gain > 0), 100.0)
    rsi = rsi.mask((loss == 0) & (gain == 0), 50.0)
    x["rsi"] = rsi

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    x["atr"] = tr.rolling(14, min_periods=14).mean()
    return x
