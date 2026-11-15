"""Conservative discovery and ranking of liquid centralized-exchange spot markets.

This module only discovers candidates. It does not generate trade approvals or place orders.
"""
import math
import re

import ccxt


DEFAULT_EXCHANGES = ("binance", "okx", "bybit")
DEFAULT_QUOTE = "USDT"
_STABLE_BASES = {
    "USDT", "USDC", "BUSD", "FDUSD", "TUSD", "DAI", "USDE", "USDS",
    "USDP", "PYUSD", "EURC", "UST", "USTC",
}
_LEVERAGED_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR", "2L", "2S", "3L", "3S")


def _number(value):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _is_leveraged_or_synthetic(base):
    upper = str(base or "").upper()
    return any(upper.endswith(suffix) and len(upper) > len(suffix) for suffix in _LEVERAGED_SUFFIXES)


def _market_is_candidate(market, quote=DEFAULT_QUOTE):
    if not isinstance(market, dict):
        return False
    base = str(market.get("base") or "").upper()
    quote_code = str(market.get("quote") or "").upper()
    return bool(
        market.get("spot") is True
        and market.get("active") is not False
        and quote_code == quote
        and base
        and base not in _STABLE_BASES
        and not _is_leveraged_or_synthetic(base)
        and market.get("contract") is not True
    )


def _score_ticker(symbol, ticker, market, min_quote_volume, max_spread_pct):
    if not isinstance(ticker, dict):
        return None
    last = _number(ticker.get("last"))
    quote_volume = _number(ticker.get("quoteVolume"))
    bid = _number(ticker.get("bid"))
    ask = _number(ticker.get("ask"))
    high = _number(ticker.get("high"))
    low = _number(ticker.get("low"))
    if last is None or last <= 0 or quote_volume is None or quote_volume < min_quote_volume:
        return None
    if bid is None or ask is None or bid <= 0 or ask < bid:
        return None
    spread_pct = ((ask - bid) / ((ask + bid) / 2)) * 100
    if not math.isfinite(spread_pct) or spread_pct > max_spread_pct:
        return None
    if high is None or low is None or low <= 0 or high < low:
        return None
    range_pct = ((high - low) / last) * 100
    if not math.isfinite(range_pct) or range_pct <= 0:
        return None

    # Ranking is deliberately transparent and liquidity-led, not a profit forecast.
    volume_score = min(50.0, 10.0 * math.log10(max(quote_volume, 1.0) / min_quote_volume + 1.0))
    spread_score = max(0.0, 30.0 * (1.0 - spread_pct / max(max_spread_pct, 0.0001)))
    movement_score = min(20.0, range_pct)
    score = round(volume_score + spread_score + movement_score, 2)
    return {
        "symbol": symbol,
        "base": market.get("base"),
        "quote": market.get("quote"),
        "last": last,
        "quote_volume_24h": quote_volume,
        "spread_pct": round(spread_pct, 4),
        "range_24h_pct": round(range_pct, 3),
        "discovery_score": score,
        "source": "centralized_spot",
        "trade_approved": False,
    }


def discover_spot_candidates(
    exchange_id,
    *,
    quote=DEFAULT_QUOTE,
    min_quote_volume=1_000_000,
    max_spread_pct=0.8,
    max_candidates=30,
):
    """Return liquid spot candidates from one CCXT exchange using public market data."""
    if not isinstance(exchange_id, str) or exchange_id not in DEFAULT_EXCHANGES:
        raise ValueError(f"Exchange must be one of: {', '.join(DEFAULT_EXCHANGES)}")
    if not isinstance(quote, str) or not re.fullmatch(r"[A-Z0-9]{2,12}", quote):
        raise ValueError("Quote currency must be a short uppercase market code")
    min_volume = _number(min_quote_volume)
    max_spread = _number(max_spread_pct)
    if min_volume is None or min_volume <= 0:
        raise ValueError("Minimum quote volume must be finite and positive")
    if max_spread is None or not 0 < max_spread <= 10:
        raise ValueError("Maximum spread must be greater than 0 and at most 10 percent")
    if isinstance(max_candidates, bool) or not isinstance(max_candidates, int) or not 1 <= max_candidates <= 100:
        raise ValueError("Maximum candidates must be an integer between 1 and 100")

    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class({"enableRateLimit": True, "timeout": 20000})
    if not exchange.has.get("fetchTickers"):
        raise RuntimeError(f"{exchange_id} does not support bulk ticker retrieval")
    markets = exchange.load_markets()
    symbols = [
        symbol for symbol, market in markets.items()
        if _market_is_candidate(market, quote=quote)
    ]
    if not symbols:
        return []
    # One bulk request per exchange avoids uncontrolled per-symbol API calls.
    tickers = exchange.fetch_tickers(symbols)
    if not isinstance(tickers, dict):
        raise RuntimeError("Exchange returned an invalid ticker collection")

    candidates = []
    for symbol in symbols:
        row = _score_ticker(
            symbol, tickers.get(symbol), markets[symbol], min_volume, max_spread
        )
        if row:
            row["exchange"] = exchange_id
            candidates.append(row)
    candidates.sort(
        key=lambda item: (
            item["discovery_score"],
            item["quote_volume_24h"],
            -item["spread_pct"],
        ),
        reverse=True,
    )
    return candidates[:max_candidates]


def discover_across_exchanges(
    exchange_ids=DEFAULT_EXCHANGES,
    *,
    quote=DEFAULT_QUOTE,
    min_quote_volume=1_000_000,
    max_spread_pct=0.8,
    max_candidates=30,
):
    """Scan supported CEXs independently; preserve per-exchange errors for visibility."""
    if not isinstance(exchange_ids, (list, tuple)) or not exchange_ids:
        raise ValueError("At least one exchange is required")
    if len(set(exchange_ids)) != len(exchange_ids):
        raise ValueError("Exchange list must not contain duplicates")
    results = []
    errors = {}
    for exchange_id in exchange_ids:
        try:
            results.extend(discover_spot_candidates(
                exchange_id,
                quote=quote,
                min_quote_volume=min_quote_volume,
                max_spread_pct=max_spread_pct,
                max_candidates=max_candidates,
            ))
        except Exception as exc:
            errors[exchange_id] = str(exc)[:240]
    results.sort(
        key=lambda item: (
            item["discovery_score"],
            item["quote_volume_24h"],
            -item["spread_pct"],
        ),
        reverse=True,
    )
    return {
        "candidates": results[:max_candidates],
        "scanned_exchanges": list(exchange_ids),
        "errors": errors,
        "scan_only": True,
        "live_orders_sent": False,
        "trade_approved": False,
    }
