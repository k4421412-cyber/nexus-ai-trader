import ccxt
from ccxt.base.errors import AuthenticationError, ExchangeNotAvailable, ExchangeError, NetworkError, RateLimitExceeded, RequestTimeout, BadSymbol
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
    requested_symbol = symbol.strip()
    resolved_symbol = requested_symbol

    # Accept exchange-native IDs such as OKX's SOL-USDT, while keeping
    # CCXT's unified symbol (for example SOL/USDT) for fetch_ohlcv.
    if "-" in requested_symbol and "/" not in requested_symbol:
        markets = exchange.load_markets()
        matches = [
            market for market in markets.values()
            if str(market.get("id", "")).upper() == requested_symbol.upper()
            and market.get("active", True)
        ]
        if matches:
            matches.sort(key=lambda market: (not market.get("spot", False), market.get("swap", False)))
            resolved_symbol = matches[0]["symbol"]
        else:
            raise ValueError(
                f"Market ID '{requested_symbol}' was not found on {exchange_id.upper()}. "
                "Use a listed market such as BTC/USDT or check the exchange's market list."
            )

    try:
        if getattr(exchange, "has", {}).get("fetchOHLCV") is False:
            raise RuntimeError(f"{exchange_id.upper()} does not support OHLCV candles through this API.")
        if getattr(exchange, "timeframes", None) and timeframe not in exchange.timeframes:
            supported = ", ".join(list(exchange.timeframes.keys())[:20])
            raise ValueError(
                f"Timeframe '{timeframe}' is not supported by {exchange_id.upper()}. "
                f"Examples: {supported}"
            )
        rows = exchange.fetch_ohlcv(resolved_symbol, timeframe=timeframe, limit=limit)
    except BadSymbol as exc:
        raise ValueError(
            f"Symbol '{requested_symbol}' is not recognized by {exchange_id.upper()}. "
            "Check the exchange's spot market list and use its CCXT symbol format."
        ) from exc
    except RateLimitExceeded as exc:
        raise RuntimeError(f"{exchange_id.upper()} rate limit reached. Wait briefly and retry.") from exc
    except RequestTimeout as exc:
        raise RuntimeError(f"{exchange_id.upper()} request timed out. Check the connection and retry.") from exc
    except NetworkError as exc:
        raise RuntimeError(f"Network error while contacting {exchange_id.upper()}. The server may be unreachable.") from exc
    except ExchangeNotAvailable as exc:
        raise RuntimeError(
            f"{exchange_id.upper()} is temporarily unavailable from this network or region. "
            "This app cannot bypass exchange access restrictions; try an officially accessible exchange."
        ) from exc
    except AuthenticationError as exc:
        raise RuntimeError(f"{exchange_id.upper()} requires authentication for this request or rejected access.") from exc
    except ExchangeError as exc:
        raise RuntimeError(f"{exchange_id.upper()} rejected the market-data request: {str(exc)[:240]}") from exc
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
    df.attrs["requested_symbol"] = requested_symbol
    df.attrs["resolved_symbol"] = resolved_symbol
    return df
