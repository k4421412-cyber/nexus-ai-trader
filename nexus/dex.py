import requests


def search_pairs(query):
    if not isinstance(query, str) or not query.strip():
        raise ValueError("DEX search query must be a non-empty string")
    query = query.strip()
    if len(query) > 100:
        raise ValueError("DEX search query must not exceed 100 characters")

    url = "https://api.dexscreener.com/latest/dex/search"
    response = requests.get(url, params={"q": query}, timeout=20)
    response.raise_for_status()
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("DEX search returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise RuntimeError("DEX search returned an unexpected response format")

    pairs = data.get("pairs")
    if pairs is None:
        return []
    if not isinstance(pairs, list):
        raise RuntimeError("DEX search returned an invalid pairs list")

    output = []
    for pair in pairs[:30]:
        if not isinstance(pair, dict):
            continue
        base = pair.get("baseToken")
        quote = pair.get("quoteToken")
        liquidity = pair.get("liquidity")
        volume = pair.get("volume")
        base_symbol = base.get("symbol", "") if isinstance(base, dict) else ""
        quote_symbol = quote.get("symbol", "") if isinstance(quote, dict) else ""
        output.append({
            "chain": pair.get("chainId"),
            "pair": f"{base_symbol}/{quote_symbol}",
            "price_usd": pair.get("priceUsd"),
            "liquidity_usd": liquidity.get("usd") if isinstance(liquidity, dict) else None,
            "volume_24h": volume.get("h24") if isinstance(volume, dict) else None,
            "url": pair.get("url"),
        })
    return output
