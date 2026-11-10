import pytest
from cryptography.fernet import Fernet

from nexus.ledger_backup import backup_encrypted_ledger, restore_encrypted_ledger
from nexus.social_investment import SimulatedInvestmentPool


def test_encrypted_backup_restore_round_trip(tmp_path):
    key = Fernet.generate_key()
    source = tmp_path / "live" / "ledger.enc"
    backup = tmp_path / "backups" / "ledger-1.enc"
    restored = tmp_path / "restore" / "ledger.enc"
    pool = SimulatedInvestmentPool(ledger_path=source, encryption_key=key)
    pool.add_investor("alice", "125")
    pool.record_trade("15", "2")
    backup_encrypted_ledger(source, backup, key)
    restore_encrypted_ledger(backup, restored, key)
    recovered = SimulatedInvestmentPool(ledger_path=restored, encryption_key=key)
    assert recovered.investor_report("alice") == pool.investor_report("alice")
    assert recovered.ledger == pool.ledger
    assert backup.read_bytes() == source.read_bytes()


def test_backup_rejects_wrong_key_and_does_not_create_file(tmp_path):
    key = Fernet.generate_key()
    source = tmp_path / "ledger.enc"
    SimulatedInvestmentPool(ledger_path=source, encryption_key=key)
    destination = tmp_path / "bad-backup.enc"
    with pytest.raises(ValueError, match="could not be verified"):
        backup_encrypted_ledger(source, destination, Fernet.generate_key())
    assert not destination.exists()


def test_restore_refuses_to_overwrite_existing_file_by_default(tmp_path):
    key = Fernet.generate_key()
    source = tmp_path / "source.enc"
    backup = tmp_path / "backup.enc"
    SimulatedInvestmentPool(ledger_path=source, encryption_key=key)
    backup_encrypted_ledger(source, backup, key)
    destination = tmp_path / "existing.enc"
    destination.write_bytes(b"preserve-me")
    with pytest.raises(FileExistsError):
        restore_encrypted_ledger(backup, destination, key)
    assert destination.read_bytes() == b"preserve-me"
