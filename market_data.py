import ccxt
import pandas as pd

def fetch_ohlcv(exchange_id="binance", symbol="BTC/USDT", timeframe="1h", limit=300):
    exchange_cls = getattr(ccxt, exchange_id)
    exchange = exchange_cls({"enableRateLimit": True, "timeout": 20000})
    rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    if not rows:
        raise RuntimeError("No market data returned")
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
