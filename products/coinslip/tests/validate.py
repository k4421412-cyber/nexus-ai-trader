#!/usr/bin/env python3
"""Dependency-free smoke checks for the CoinSlip static app."""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")

required_ids = {
    "seller", "client", "amount", "network", "wallet", "invoice", "due",
    "note", "generate", "saveDraft", "loadDraft", "clear", "paper",
    "copyWallet", "print", "download", "downloadCsv", "copyDetails", "pSeller", "pAmount", "pWallet",
}
ids = set(re.findall(r'\bid=["\']([^"\']+)["\']', HTML))
missing = sorted(required_ids - ids)
assert not missing, f"Missing required DOM ids: {missing}"
assert HTML.count('id="') == len(ids), "Duplicate HTML id attributes detected"
assert "localStorage.setItem('coinslip-draft-v1'" in HTML, "Local draft save missing"
assert "UNVERIFIED — AWAITING PAYMENT" in HTML, "Unverified-payment warning missing"
assert "Payment is not verified by this invoice." in HTML, "Payment disclaimer missing"
assert "no more than 6 decimal places" in HTML, "Six-decimal precision validation missing"
assert "downloadCsv" in HTML and "text/csv" in HTML, "CSV export missing"
assert "copyDetails" in HTML and "NOT VERIFIED" in HTML, "Payment-details copy warning missing"
assert "formula injection" in HTML.lower() or "/^[\\\\s]*[=+@-]/" in HTML, "CSV spreadsheet-formula protection missing"
assert "replace(/[^a-zA-Z0-9_-]/g" in HTML, "Export filename sanitization missing"
assert "private key" not in HTML.lower(), "App must never request private keys"

scripts = re.findall(r"<script>(.*?)</script>", HTML, flags=re.S)
assert scripts, "No inline application script found"
for index, script in enumerate(scripts):
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as handle:
        handle.write(script)
        handle.flush()
        result = subprocess.run(["node", "--check", handle.name], capture_output=True, text=True)
        if result.returncode:
            raise SystemExit(f"JavaScript syntax error in script {index}:\n{result.stderr}")

print(f"CoinSlip checks passed: {len(required_ids)} required controls, {len(scripts)} script(s).")
