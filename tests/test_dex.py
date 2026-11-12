import pytest

from nexus import dex


class FakeResponse:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        return None

    def json(self):
        if self.error:
            raise self.error
        return self.payload


@pytest.mark.parametrize("query", ["", "   ", None, 123, "x" * 101])
def test_search_pairs_rejects_invalid_queries(query):
    with pytest.raises(ValueError):
        dex.search_pairs(query)


def test_search_pairs_normalizes_valid_pair_payload(monkeypatch):
    monkeypatch.setattr(
        dex.requests,
        "get",
        lambda *args, **kwargs: FakeResponse({
            "pairs": [{
                "chainId": "ethereum",
                "baseToken": {"symbol": "ABC"},
                "quoteToken": {"symbol": "USDT"},
                "priceUsd": "1.25",
                "liquidity": {"usd": 1000},
                "volume": {"h24": 500},
                "url": "https://example.test/pair",
            }]
        }),
    )
    assert dex.search_pairs(" ABC ") == [{
        "chain": "ethereum",
        "pair": "ABC/USDT",
        "price_usd": "1.25",
        "liquidity_usd": 1000,
        "volume_24h": 500,
        "url": "https://example.test/pair",
    }]


@pytest.mark.parametrize("payload", [None, [], "bad", {"pairs": "not-a-list"}])
def test_search_pairs_rejects_unexpected_response_shapes(monkeypatch, payload):
    monkeypatch.setattr(dex.requests, "get", lambda *args, **kwargs: FakeResponse(payload))
    with pytest.raises(RuntimeError, match="unexpected|invalid"):
        dex.search_pairs("ABC")


def test_search_pairs_skips_malformed_pairs_and_handles_missing_nested_fields(monkeypatch):
    monkeypatch.setattr(
        dex.requests,
        "get",
        lambda *args, **kwargs: FakeResponse({"pairs": [None, "bad", {"chainId": "solana"}]}),
    )
    assert dex.search_pairs("ABC") == [{
        "chain": "solana",
        "pair": "/",
        "price_usd": None,
        "liquidity_usd": None,
        "volume_24h": None,
        "url": None,
    }]


def test_search_pairs_rejects_invalid_json(monkeypatch):
    monkeypatch.setattr(
        dex.requests, "get",
        lambda *args, **kwargs: FakeResponse(error=ValueError("invalid json")),
    )
    with pytest.raises(RuntimeError, match="invalid JSON"):
        dex.search_pairs("ABC")
