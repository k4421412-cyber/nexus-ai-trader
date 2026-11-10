import ccxt
import numpy as np
import pandas as pd


def fetch_ohlcv(exchange_id="binance", symbol="BTC/USDT", timeframe="1h", limit=300):
    if not isinstance(exchange_id, str) or exchange_id not in ccxt.exchanges:
        raise ValueError(f"Unsupported exchange: {exchange_id}")
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("Trading symbol must be a non-empty string")
    if not isinstance(timeframe, str) or not timeframe.strip():
        raise ValueError("Timeframe must be a non-empty string")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 50 <= limit <= 1000:
        raise ValueError("Candle limit must be an integer between 50 and 1000")

    exchange_cls = getattr(ccxt, exchange_id)
    exchange = exchange_cls({"enableRateLimit": True, "timeout": 20000})
    rows = exchange.fetch_ohlcv(symbol.strip(), timeframe=timeframe, limit=limit)
    if not rows:
        raise RuntimeError("No market data returned")

    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    columns = ["timestamp", "open", "high", "low", "close", "volume"]
    for column in columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    values = df[columns].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise RuntimeError("Exchange returned missing, non-numeric, or non-finite OHLCV data")
    if (df[["open", "high", "low", "close"]] <= 0).any().any() or (df["volume"] < 0).any():
        raise RuntimeError("Exchange returned invalid OHLCV values")
    if not df["timestamp"].is_monotonic_increasing or df["timestamp"].duplicated().any():
        raise RuntimeError("Exchange returned unordered or duplicate candle timestamps")
    if (df["high"] < df[["open", "close", "low"]].max(axis=1)).any():
        raise RuntimeError("Exchange returned inconsistent candle highs")
    if (df["low"] > df[["open", "close", "high"]].min(axis=1)).any():
        raise RuntimeError("Exchange returned inconsistent candle lows")
    return df
