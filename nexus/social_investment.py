"""Simulation-only pooled investment accounting.

No custody, deposits, withdrawals, exchange orders, or real-money handling.
All amounts use Decimal and every operation appends an auditable ledger event.
"""
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone


def _amount(value, field, *, allow_zero=True):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field} must be a valid decimal amount") from None
    if not amount.is_finite() or amount < 0 or (not allow_zero and amount == 0):
        raise ValueError(f"{field} must be a finite {'non-negative' if allow_zero else 'positive'} amount")
    return amount


class SimulatedInvestmentPool:
    """One-time virtual allocations with pro-rata P/L and a pool high-water mark."""

    def __init__(self, manager_profit_share_bps=0):
        if isinstance(manager_profit_share_bps, bool) or not isinstance(manager_profit_share_bps, int):
            raise ValueError("manager_profit_share_bps must be an integer")
        if not 0 <= manager_profit_share_bps <= 10000:
            raise ValueError("manager_profit_share_bps must be between 0 and 10000")
        self.manager_profit_share_bps = manager_profit_share_bps
        self.investors = {}
        self.ledger = []
        self.total_contributed = Decimal("0")
        self.cumulative_net_pnl = Decimal("0")
        self.high_water_mark = Decimal("0")
        self.started = False
        self._append("pool_created", manager_profit_share_bps=manager_profit_share_bps)

    def _append(self, event, **fields):
        self.ledger.append({
            "sequence": len(self.ledger) + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **{key: str(value) if isinstance(value, Decimal) else value for key, value in fields.items()},
        })

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
        self._append("virtual_allocation", investor_id=investor_id, amount=amount)
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
        self.started = True
        self.cumulative_net_pnl = next_profit - manager_fee
        self.high_water_mark = max(self.high_water_mark, self.cumulative_net_pnl)
        for investor_id, account in self.investors.items():
            share = account["contributed"] / self.total_contributed
            account["net_pnl"] += investor_net * share
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
        }
