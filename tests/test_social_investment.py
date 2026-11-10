from decimal import Decimal

import pytest

from nexus.social_investment import SimulatedInvestmentPool


def test_allocations_and_profit_are_shared_pro_rata():
    pool = SimulatedInvestmentPool()
    pool.add_investor("alice", "100")
    pool.add_investor("bob", "300")
    pool.record_trade("40", "0")
    assert Decimal(pool.investor_report("alice")["net_pnl"]) == Decimal("10")
    assert Decimal(pool.investor_report("bob")["net_pnl"]) == Decimal("30")


def test_losses_are_also_shared_pro_rata():
    pool = SimulatedInvestmentPool()
    pool.add_investor("alice", "100")
    pool.add_investor("bob", "100")
    pool.record_trade("-20", "0")
    assert Decimal(pool.investor_report("alice")["net_pnl"]) == Decimal("-10")
    assert Decimal(pool.investor_report("bob")["net_pnl"]) == Decimal("-10")


def test_fees_reduce_investor_profit():
    pool = SimulatedInvestmentPool()
    pool.add_investor("alice", "100")
    pool.record_trade("20", "5")
    assert Decimal(pool.investor_report("alice")["net_pnl"]) == Decimal("15")


def test_manager_share_only_applies_to_new_profit_above_high_water_mark():
    pool = SimulatedInvestmentPool(manager_profit_share_bps=2000)
    pool.add_investor("alice", "100")
    pool.record_trade("100")
    assert Decimal(pool.investor_report("alice")["net_pnl"]) == Decimal("80")
    pool.record_trade("-30")
    pool.record_trade("30")
    # The recovery to the previous high-water mark does not trigger a second fee.
    assert Decimal(pool.investor_report("alice")["net_pnl"]) == Decimal("80")


def test_manager_share_is_charged_on_incremental_new_high():
    pool = SimulatedInvestmentPool(manager_profit_share_bps=1000)
    pool.add_investor("alice", "100")
    pool.record_trade("100")
    pool.record_trade("50")
    assert Decimal(pool.investor_report("alice")["net_pnl"]) == Decimal("135")


def test_new_allocation_is_blocked_after_trading_starts():
    pool = SimulatedInvestmentPool()
    pool.add_investor("alice", "100")
    pool.record_trade("1")
    with pytest.raises(ValueError, match="after the first"):
        pool.add_investor("bob", "50")


@pytest.mark.parametrize("amount", ["0", "-1", "NaN", "Infinity", "not-money"])
def test_invalid_allocations_are_rejected(amount):
    pool = SimulatedInvestmentPool()
    with pytest.raises(ValueError):
        pool.add_investor("alice", amount)


def test_duplicate_and_unknown_investors_are_rejected():
    pool = SimulatedInvestmentPool()
    pool.add_investor("alice", "10")
    with pytest.raises(ValueError, match="already exists"):
        pool.add_investor("alice", "20")
    with pytest.raises(KeyError):
        pool.investor_report("nobody")


def test_invalid_fees_and_non_finite_pnl_are_rejected():
    pool = SimulatedInvestmentPool()
    pool.add_investor("alice", "100")
    with pytest.raises(ValueError):
        pool.record_trade("1", "-1")
    with pytest.raises(ValueError):
        pool.record_trade("NaN")


def test_ledger_is_sequential_and_summary_is_simulation_only():
    pool = SimulatedInvestmentPool()
    pool.add_investor("alice", "100")
    pool.record_trade("5", "1")
    assert [row["sequence"] for row in pool.ledger] == [1, 2, 3]
    assert pool.summary()["simulation_only"] is True


@pytest.mark.parametrize("bps", [-1, 10001, True, 1.5])
def test_invalid_manager_profit_share_is_rejected(bps):
    with pytest.raises(ValueError):
        SimulatedInvestmentPool(manager_profit_share_bps=bps)


def test_pool_rejects_losses_beyond_remaining_virtual_capital_without_mutation():
    pool = SimulatedInvestmentPool()
    pool.add_investor("alice", "100")
    before_ledger = list(pool.ledger)
    with pytest.raises(ValueError, match="remaining virtual capital"):
        pool.record_trade("-101", "0")
    assert pool.investor_report("alice")["virtual_value"] == "100"
    assert pool.ledger == before_ledger
    assert pool.started is False


def test_pool_rejects_fees_that_exceed_remaining_virtual_capital():
    pool = SimulatedInvestmentPool()
    pool.add_investor("alice", "100")
    with pytest.raises(ValueError, match="remaining virtual capital"):
        pool.record_trade("0", "101")
    assert pool.investor_report("alice")["virtual_value"] == "100"


def test_partial_virtual_withdrawal_updates_balance_and_ledger():
    pool = SimulatedInvestmentPool()
    pool.add_investor("alice", "100")
    pool.add_investor("bob", "300")
    pool.record_trade("40")
    report = pool.withdraw_virtual("alice", "20")
    assert Decimal(report["virtual_value"]) == Decimal("90")
    assert Decimal(report["withdrawn"]) == Decimal("20")
    assert pool.ledger[-1]["event"] == "virtual_withdrawal"
    assert Decimal(pool.summary()["current_virtual_balance"]) == Decimal("420")


def test_future_profit_is_allocated_by_remaining_virtual_balance_after_withdrawal():
    pool = SimulatedInvestmentPool()
    pool.add_investor("alice", "100")
    pool.add_investor("bob", "100")
    pool.withdraw_virtual("alice", "50")
    pool.record_trade("15")
    assert Decimal(pool.investor_report("alice")["net_pnl"]) == Decimal("5")
    assert Decimal(pool.investor_report("bob")["net_pnl"]) == Decimal("10")


@pytest.mark.parametrize("amount", ["0", "-1", "NaN", "Infinity", "101"])
def test_invalid_or_excess_virtual_withdrawals_are_rejected_without_mutation(amount):
    pool = SimulatedInvestmentPool()
    pool.add_investor("alice", "100")
    before = pool.summary()
    before_ledger = list(pool.ledger)
    with pytest.raises(ValueError):
        pool.withdraw_virtual("alice", amount)
    assert pool.summary() == before
    assert pool.ledger == before_ledger


def test_virtual_withdrawal_cannot_make_balance_negative():
    pool = SimulatedInvestmentPool()
    pool.add_investor("alice", "100")
    pool.record_trade("-25")
    with pytest.raises(ValueError, match="available virtual balance"):
        pool.withdraw_virtual("alice", "76")
    assert pool.investor_report("alice")["virtual_value"] == "75"


def test_virtual_withdrawal_write_failure_rolls_back_account():
    pool = SimulatedInvestmentPool()
    pool.add_investor("alice", "100")
    before = pool.investor_report("alice")
    pool._persist = lambda: (_ for _ in ()).throw(OSError("disk full"))
    with pytest.raises(OSError):
        pool.withdraw_virtual("alice", "25")
    assert pool.investor_report("alice") == before
