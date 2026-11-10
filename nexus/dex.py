import requests

def search_pairs(query):
    url = "https://api.dexscreener.com/latest/dex/search"
    r = requests.get(url, params={"q": query}, timeout=20)
    r.raise_for_status()
    data = r.json().get("pairs") or []
    out = []
    for p in data[:30]:
        out.append({
            "chain": p.get("chainId"),
            "pair": (p.get("baseToken") or {}).get("symbol", "") + "/" + (p.get("quoteToken") or {}).get("symbol", ""),
            "price_usd": p.get("priceUsd"),
            "liquidity_usd": (p.get("liquidity") or {}).get("usd"),
            "volume_24h": (p.get("volume") or {}).get("h24"),
            "url": p.get("url")
        })
    return out
