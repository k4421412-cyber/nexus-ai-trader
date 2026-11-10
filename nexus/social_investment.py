"""Simulation-only investment accounting with optional encrypted persistence.

Real-money custody, deposits, withdrawals and exchange orders are not supported.
Set an explicit Fernet key and ledger path to enable durable encrypted storage.
"""
import copy
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


_ZERO_HASH = "0" * 64


def _amount(value, field, *, allow_zero=True):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field} must be a valid decimal amount") from None
    if not amount.is_finite() or amount < 0 or (not allow_zero and amount == 0):
        raise ValueError(f"{field} must be a finite {'non-negative' if allow_zero else 'positive'} amount")
    return amount


def _event_digest(event):
    payload = {key: value for key, value in event.items() if key != "event_hash"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SimulatedInvestmentPool:
    """Virtual allocations with pro-rata P/L, HWM and an auditable event chain."""

    def __init__(self, manager_profit_share_bps=0, *, ledger_path=None, encryption_key=None):
        if isinstance(manager_profit_share_bps, bool) or not isinstance(manager_profit_share_bps, int):
            raise ValueError("manager_profit_share_bps must be an integer")
        if not 0 <= manager_profit_share_bps <= 10000:
            raise ValueError("manager_profit_share_bps must be between 0 and 10000")
        if (ledger_path is None) != (encryption_key is None):
            raise ValueError("ledger_path and encryption_key must be supplied together")

        self.manager_profit_share_bps = manager_profit_share_bps
        self.investors = {}
        self.ledger = []
        self.total_contributed = Decimal("0")
        self.cumulative_net_pnl = Decimal("0")
        self.high_water_mark = Decimal("0")
        self.started = False
        self.ledger_path = Path(ledger_path).expanduser() if ledger_path is not None else None
        try:
            self._cipher = Fernet(
                encryption_key.encode("ascii") if isinstance(encryption_key, str) else encryption_key
            ) if encryption_key is not None else None
        except (TypeError, ValueError) as exc:
            raise ValueError("encryption_key must be a valid Fernet key") from exc

        if self.ledger_path is not None and self.ledger_path.exists():
            self._load()
        else:
            self._append("pool_created", manager_profit_share_bps=manager_profit_share_bps)

    @property
    def persistent(self):
        return self.ledger_path is not None

    def _state_payload(self):
        return {
            "schema_version": 1,
            "manager_profit_share_bps": self.manager_profit_share_bps,
            "investors": {
                key: {name: str(value) for name, value in account.items()}
                for key, account in self.investors.items()
            },
            "total_contributed": str(self.total_contributed),
            "cumulative_net_pnl": str(self.cumulative_net_pnl),
            "high_water_mark": str(self.high_water_mark),
            "started": self.started,
            "ledger": self.ledger,
        }

    def _persist(self):
        if not self.persistent:
            return
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        plaintext = json.dumps(
            self._state_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        encrypted = self._cipher.encrypt(plaintext)
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=self.ledger_path.parent, prefix=f".{self.ledger_path.name}.",
                suffix=".tmp", delete=False
            ) as temp:
                temp_name = temp.name
                os.chmod(temp_name, 0o600)
                temp.write(encrypted)
                temp.flush()
                os.fsync(temp.fileno())
            os.replace(temp_name, self.ledger_path)
            temp_name = None
            try:
                dir_fd = os.open(self.ledger_path.parent, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass
        finally:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)

    def _load(self):
        try:
            payload = json.loads(self._cipher.decrypt(self.ledger_path.read_bytes()).decode("utf-8"))
            if payload.get("schema_version") != 1:
                raise ValueError("Unsupported encrypted ledger schema")
            if payload.get("manager_profit_share_bps") != self.manager_profit_share_bps:
                raise ValueError("Ledger manager share does not match configured share")
            events = payload.get("ledger")
            if not isinstance(events, list) or not events:
                raise ValueError("Encrypted ledger has no valid event history")
            previous = _ZERO_HASH
            for sequence, event in enumerate(events, start=1):
                if not isinstance(event, dict) or event.get("sequence") != sequence:
                    raise ValueError("Ledger sequence validation failed")
                if event.get("previous_hash") != previous or event.get("event_hash") != _event_digest(event):
                    raise ValueError("Ledger integrity validation failed")
                previous = event["event_hash"]

            raw_investors = payload.get("investors")
            if not isinstance(raw_investors, dict):
                raise ValueError("Invalid investor state in encrypted ledger")
            self.investors = {
                key: {name: Decimal(value) for name, value in account.items()}
                for key, account in raw_investors.items()
            }
            self.total_contributed = Decimal(payload["total_contributed"])
            self.cumulative_net_pnl = Decimal(payload["cumulative_net_pnl"])
            self.high_water_mark = Decimal(payload["high_water_mark"])
            self.started = bool(payload["started"])
            self.ledger = events
        except (InvalidToken, OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError,
                TypeError, InvalidOperation) as exc:
            raise ValueError("Unable to decrypt or validate the investment ledger") from exc

    def _append(self, event, **fields):
        previous = self.ledger[-1]["event_hash"] if self.ledger else _ZERO_HASH
        row = {
            "sequence": len(self.ledger) + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "previous_hash": previous,
            **{key: str(value) if isinstance(value, Decimal) else value for key, value in fields.items()},
        }
        row["event_hash"] = _event_digest(row)
        self.ledger.append(row)
        try:
            self._persist()
        except Exception:
            self.ledger.pop()
            raise

    def add_investor(self, investor_id, contribution):
        if self.started:
            raise ValueError("New allocations are disabled after the first simulated trade")
        if not isinstance(investor_id, str) or not investor_id.strip():
            raise ValueError("investor_id must be a non-empty string")
        investor_id = investor_id.strip()
        if investor_id in self.investors:
            raise ValueError("Investor already exists in this pool")
        amount = _amount(contribution, "contribution", allow_zero=False)
        self.investors[investor_id] = {"contributed": amount, "net_pnl": Decimal("0")}
        self.total_contributed += amount
        try:
            self._append("virtual_allocation", investor_id=investor_id, amount=amount)
        except Exception:
            self.total_contributed -= amount
            del self.investors[investor_id]
            raise
        return self.investor_report(investor_id)

    def record_trade(self, realized_pnl, fees=0):
        if not self.investors:
            raise ValueError("Add at least one virtual investor before recording trades")
        try:
            raw_pnl = Decimal(str(realized_pnl))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("realized_pnl must be a valid decimal amount") from None
        if not raw_pnl.is_finite():
            raise ValueError("realized_pnl must be finite")
        fee = _amount(fees, "fees")
        net = raw_pnl - fee
        previous_profit = self.cumulative_net_pnl
        next_profit = previous_profit + net
        if next_profit < -self.total_contributed:
            raise ValueError("Trade loss and fees cannot exceed the pool's remaining virtual capital")
        fee_base = max(Decimal("0"), next_profit - max(self.high_water_mark, previous_profit))
        manager_fee = fee_base * Decimal(self.manager_profit_share_bps) / Decimal(10000)
        investor_net = net - manager_fee
        if self.total_contributed + previous_profit + investor_net < 0:
            raise ValueError("Settlement would make investor virtual balances negative")

        old_investors = copy.deepcopy(self.investors)
        old_state = (self.cumulative_net_pnl, self.high_water_mark, self.started)
        self.started = True
        self.cumulative_net_pnl = next_profit - manager_fee
        self.high_water_mark = max(self.high_water_mark, self.cumulative_net_pnl)
        for investor_id, account in self.investors.items():
            share = account["contributed"] / self.total_contributed
            account["net_pnl"] += investor_net * share
        try:
            self._append(
                "simulated_trade_settlement",
                realized_pnl=raw_pnl,
                trading_fees=fee,
                net_before_manager_share=net,
                manager_profit_share=manager_fee,
                investor_net_pnl=investor_net,
                pool_cumulative_net_pnl=self.cumulative_net_pnl,
                high_water_mark=self.high_water_mark,
            )
        except Exception:
            self.investors = old_investors
            self.cumulative_net_pnl, self.high_water_mark, self.started = old_state
            raise
        return self.summary()

    def investor_report(self, investor_id):
        if investor_id not in self.investors:
            raise KeyError("Unknown investor")
        account = self.investors[investor_id]
        return {
            "investor_id": investor_id,
            "contributed": str(account["contributed"]),
            "net_pnl": str(account["net_pnl"]),
            "virtual_value": str(account["contributed"] + account["net_pnl"]),
            "share_pct": str(account["contributed"] / self.total_contributed * 100),
        }

    def summary(self):
        return {
            "investor_count": len(self.investors),
            "total_virtual_contributions": str(self.total_contributed),
            "pool_cumulative_net_pnl": str(self.cumulative_net_pnl),
            "high_water_mark": str(self.high_water_mark),
            "manager_profit_share_bps": self.manager_profit_share_bps,
            "investors": [self.investor_report(key) for key in self.investors],
            "ledger_entries": len(self.ledger),
            "simulation_only": True,
            "persistent_encrypted": self.persistent,
        }
