# Quality, security and release test plan

This plan applies to the simulation-only MVP. Passing CI is evidence for the covered cases, not a proof that the application is bug-free or safe for live funds.

## Automated coverage

- Core correctness: OHLCV validation, indicators, signal input validation, paper-wallet accounting and failure atomicity.
- Financial scenarios: fees, slippage, open-position liquidation estimate, drawdown, exposure, expectancy, profit factor, profit/loss allocation, high-water mark and 100 seeded randomized backtest scenarios.
- Persistence/security: Fernet authenticated encryption, wrong-key rejection, ciphertext tamper rejection, event hash-chain validation, file-write failure rollback and explicit key/path configuration.
- Performance: deterministic 5,000-candle backtest budget in CI. This is a regression guard, not a production load test.
- UI/mobile smoke: Streamlit AppTest on every navigation page and responsive CSS rules for narrow screens, readable metrics, horizontally scrollable data tables and touch-sized buttons.
- Static security: Bandit scan and dependency vulnerability audit in GitHub Actions.

## Encrypted investment ledger configuration

The collaborative-investment module remains simulation-only. Persistent storage is opt-in and requires both environment variables on the server:

- `NEXUS_LEDGER_KEY`: a Fernet key supplied through the hosting platform's secret manager.
- `NEXUS_LEDGER_PATH`: optional encrypted file path; defaults to `data/investment-ledger.enc`.

Generate a key in a trusted administrative environment with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Store the key outside the repository and outside the ledger file. Do not commit it, paste it into chat, or expose it in logs. Back up the key separately: loss of the key makes the ledger unreadable. Fernet provides authenticated encryption; a SHA-256 event chain provides additional ordering/tamper diagnostics. The application uses atomic replacement and restrictive file permissions where supported.

If these variables are absent, the application clearly reports that the ledger is session-memory only. A persistent file on one server is not yet a multi-user database, replicated backup, or production custody system.

## Mobile acceptance checklist

Test at 320px, 375px, 390px and 430px viewport widths on Android Chrome and iOS Safari:
- no page-level horizontal overflow;
- sidebar navigation remains reachable;
- tables scroll within their own region;
- metric labels and long symbols wrap without clipping;
- primary controls are at least 44px high;
- Persian RTL and mixed Latin ticker/address text remain legible;
- all nine pages render without exceptions.

Streamlit AppTest checks page rendering in CI; physical-device and browser viewport checks remain manual until browser automation is added.

## Backtest limitations and next release gates

The current engine is a simple long-only candle simulator. Before any live-trading discussion, add and validate: out-of-sample splits, walk-forward evaluation, parameter-sensitivity checks, realistic partial fills, spread/market impact, funding/borrow costs where relevant, exchange precision/minimum-notional rules, delisted assets and survivorship-bias controls, and independent reconciliation of trade ledgers. A high win rate alone is not an acceptance criterion; net expectancy, drawdown, tail loss and risk-adjusted return matter.

No live orders, real deposits, withdrawals, private keys or seed phrases are supported by this release.


## Additional release gates implemented in this pass

- Cross-process file locking and reload-before-write prevent concurrent Streamlit sessions from silently overwriting one another's ledger updates on a single shared filesystem.
- Ledger reload reconciles investor contributions, investor P/L, pool totals, finite balances and high-water mark before accepting the state.
- Simulated partial withdrawals are recorded as ledger events, limited to each investor's available virtual balance, and subsequent simulated P/L is allocated using remaining virtual balances.
- Walk-forward evaluation selects among supplied causal strategy signal streams using only each past training window, then evaluates the selected candidate on the next untouched test window. Each fold starts with a separate virtual balance; fold returns are not compounded.
- Browser-level responsive checks run at 320, 375, 390 and 430 CSS pixels across the navigation pages. This is browser emulation, not a substitute for physical Android/iOS device acceptance.
- A CI concurrency test creates multiple ledger clients and submits simultaneous virtual allocations to detect lost updates.

### Persistent ledger operational setup

The application code cannot install its own secret on an external hosting account. An authorized operator must configure `NEXUS_LEDGER_KEY` in the hosting provider's secret manager and set `NEXUS_LEDGER_PATH` to a persistent mounted volume. The volume must support atomic rename and file locking. Keep encrypted backups and the Fernet key separately, test restore procedures, restrict filesystem access, and monitor disk capacity. Do not use ephemeral container storage for a production ledger. The ledger remains simulation-only until separate legal, operational and security review.
