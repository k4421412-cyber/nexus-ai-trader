"""Verified encrypted investment-ledger backup and restore helpers."""
import json
import os
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


def _verify(path, encryption_key):
    source = Path(path)
    try:
        cipher = Fernet(
            encryption_key.encode("ascii") if isinstance(encryption_key, str) else encryption_key
        )
        encrypted = source.read_bytes()
        payload = json.loads(cipher.decrypt(encrypted).decode("utf-8"))
        if payload.get("schema_version") != 1 or not isinstance(payload.get("ledger"), list):
            raise ValueError("Unsupported or malformed encrypted ledger backup")
        return encrypted
    except (InvalidToken, OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, AttributeError) as exc:
        raise ValueError("Encrypted ledger backup could not be verified") from exc


def _atomic_copy(encrypted, destination):
    target = Path(destination).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False
        ) as temp:
            temp_name = temp.name
            os.chmod(temp_name, 0o600)
            temp.write(encrypted)
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_name, target)
        temp_name = None
        return target
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def backup_encrypted_ledger(source, destination, encryption_key):
    """Verify and copy ciphertext; plaintext is never written to the backup."""
    encrypted = _verify(source, encryption_key)
    return _atomic_copy(encrypted, destination)


def restore_encrypted_ledger(backup_path, destination, encryption_key, *, overwrite=False):
    """Restore only a decryptable backup; refuse to overwrite by default."""
    encrypted = _verify(backup_path, encryption_key)
    target = Path(destination).expanduser()
    if target.exists() and not overwrite:
        raise FileExistsError("Destination exists; pass overwrite=True after making a separate backup")
    return _atomic_copy(encrypted, target)
