import json
import time

import numpy as np
import pandas as pd
import pytest
from cryptography.fernet import Fernet

from nexus.social_investment import SimulatedInvestmentPool
from nexus.strategies import backtest


def test_encrypted_ledger_persists_and_restores_state(tmp_path):
    key = Fernet.generate_key()
    path = tmp_path / "secure" / "ledger.enc"
    pool = SimulatedInvestmentPool(ledger_path=path, encryption_key=key)
    pool.add_investor("confidential-investor", "250")
    pool.record_trade("17.50", "1.25")

    ciphertext = path.read_bytes()
    assert b"confidential-investor" not in ciphertext
    assert b"250" not in ciphertext
    restored = SimulatedInvestmentPool(ledger_path=path, encryption_key=key)
    assert restored.persistent is True
    assert restored.investor_report("confidential-investor") == pool.investor_report("confidential-investor")
    assert restored.ledger == pool.ledger


def test_encrypted_ledger_rejects_wrong_key(tmp_path):
    path = tmp_path / "ledger.enc"
    SimulatedInvestmentPool(ledger_path=path, encryption_key=Fernet.generate_key())
    with pytest.raises(ValueError, match="decrypt or validate"):
        SimulatedInvestmentPool(ledger_path=path, encryption_key=Fernet.generate_key())


def test_encrypted_ledger_rejects_ciphertext_tampering(tmp_path):
    key = Fernet.generate_key()
    path = tmp_path / "ledger.enc"
    SimulatedInvestmentPool(ledger_path=path, encryption_key=key)
    raw = bytearray(path.read_bytes())
    raw[-8] ^= 1
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="decrypt or validate"):
        SimulatedInvestmentPool(ledger_path=path, encryption_key=key)


def test_encrypted_ledger_rejects_validly_encrypted_broken_hash_chain(tmp_path):
    key = Fernet.generate_key()
    path = tmp_path / "ledger.enc"
    SimulatedInvestmentPool(ledger_path=path, encryption_key=key)
    cipher = Fernet(key)
    payload = json.loads(cipher.decrypt(path.read_bytes()))
    payload["ledger"][0]["event"] = "tampered_event"
    path.write_bytes(cipher.encrypt(json.dumps(payload).encode()))
    with pytest.raises(ValueError, match="integrity validation"):
        SimulatedInvestmentPool(ledger_path=path, encryption_key=key)


def test_ledger_write_failure_rolls_back_in_memory_state(tmp_path, monkeypatch):
    pool = SimulatedInvestmentPool(
        ledger_path=tmp_path / "ledger.enc", encryption_key=Fernet.generate_key()
    )
    monkeypatch.setattr(pool, "_persist", lambda: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        pool.add_investor("alice", "100")
    assert pool.investors == {}
    assert str(pool.total_contributed) == "0"
    assert len(pool.ledger) == 1


def test_trade_write_failure_rolls_back_all_financial_state(tmp_path, monkeypatch):
    pool = SimulatedInvestmentPool(
        ledger_path=tmp_path / "ledger.enc", encryption_key=Fernet.generate_key()
    )
    pool.add_investor("alice", "100")
    before = pool.summary()
    monkeypatch.setattr(pool, "_persist", lambda: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        pool.record_trade("15", "1")
    assert pool.summary() == before


def test_ledger_requires_key_and_path_as_a_pair(tmp_path):
    with pytest.raises(ValueError, match="supplied together"):
        SimulatedInvestmentPool(ledger_path=tmp_path / "ledger.enc")


def test_manager_share_configuration_is_locked_after_allocation():
    pool = SimulatedInvestmentPool()
    pool.set_manager_profit_share(1250)
    assert pool.manager_profit_share_bps == 1250
    pool.add_investor("alice", "100")
    with pytest.raises(ValueError, match="before allocations"):
        pool.set_manager_profit_share(0)


def test_backtest_100_deterministic_financial_scenarios():
    rng = np.random.default_rng(20261110)
    for _ in range(100):
        n = 120
        returns = rng.normal(0.0002, 0.012, n)
        close = 100 * np.cumprod(1 + returns)
        open_prices = close * (1 + rng.normal(0, 0.002, n))
        ema20 = pd.Series(close).ewm(span=20, adjust=False).mean().to_numpy()
        ema50 = pd.Series(close).ewm(span=50, adjust=False).mean().to_numpy()
        signals = rng.random(n) < 0.04
        frame = pd.DataFrame({
            "open": open_prices,
            "close": close,
            "ema20": ema20,
            "ema50": ema50,
        })
        result = backtest(frame, signals, fee=0.001, slippage=0.0005)
        assert np.isfinite(result["equity_curve"]).all()
        assert result["final_balance"] >= 0
        assert 0 <= result["max_drawdown_pct"] <= 100
        assert 0 <= result["exposure_pct"] <= 100
        assert result["closed_trade_count"] == len(result["closed_trades"])


def test_backtest_large_dataset_finishes_within_performance_budget():
    n = 5000
    close = np.linspace(100, 150, n)
    frame = pd.DataFrame({
        "open": close,
        "close": close,
        "ema20": pd.Series(close).ewm(span=20, adjust=False).mean(),
        "ema50": pd.Series(close).ewm(span=50, adjust=False).mean(),
    })
    signals = pd.Series(np.arange(n) % 37 == 0)
    started = time.perf_counter()
    result = backtest(frame, signals, fee=0.001, slippage=0.0005)
    elapsed = time.perf_counter() - started
    assert result["equity_curve"]
    assert elapsed < 8.0

from concurrent.futures import ThreadPoolExecutor


def test_multiple_persistent_pool_instances_do_not_lose_updates(tmp_path):
    key = Fernet.generate_key()
    path = tmp_path / "shared-ledger.enc"
    first = SimulatedInvestmentPool(ledger_path=path, encryption_key=key)
    second = SimulatedInvestmentPool(ledger_path=path, encryption_key=key)
    first.add_investor("alice", "100")
    second.add_investor("bob", "200")
    refreshed = SimulatedInvestmentPool(ledger_path=path, encryption_key=key)
    assert set(refreshed.investors) == {"alice", "bob"}
    assert refreshed.summary()["investor_count"] == 2


def test_concurrent_persistent_allocations_are_serialized(tmp_path):
    key = Fernet.generate_key()
    path = tmp_path / "concurrent-ledger.enc"
    SimulatedInvestmentPool(ledger_path=path, encryption_key=key)

    def add_one(index):
        pool = SimulatedInvestmentPool(ledger_path=path, encryption_key=key)
        pool.add_investor(f"investor-{index}", "10")

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(add_one, range(16)))

    final = SimulatedInvestmentPool(ledger_path=path, encryption_key=key)
    assert final.summary()["investor_count"] == 16
    assert final.summary()["total_virtual_contributions"] == "160"


def test_persistent_ledger_reconciles_withdrawals_after_restart(tmp_path):
    key = Fernet.generate_key()
    path = tmp_path / "withdrawals.enc"
    pool = SimulatedInvestmentPool(ledger_path=path, encryption_key=key)
    pool.add_investor("alice", "100")
    pool.record_trade("25")
    pool.withdraw_virtual("alice", "40")
    restored = SimulatedInvestmentPool(ledger_path=path, encryption_key=key)
    report = restored.investor_report("alice")
    assert report["virtual_value"] == "85"
    assert report["withdrawn"] == "40"
    assert restored.summary()["current_virtual_balance"] == "85"
