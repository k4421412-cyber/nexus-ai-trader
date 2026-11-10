# Social investment and profit sharing

## Product goal

Provide an optional area where capital providers can allocate capital to a strategy operator, and net trading profits (if any) are shared according to terms accepted by all participants. This is a high-risk financial feature, not a promise of returns.

## Roles

- **Capital provider / investor:** chooses an eligible strategy/operator, reviews its verified track record and risk disclosures, chooses an amount within limits, and accepts the agreement.
- **Strategy operator / manager:** publishes a strategy profile, risk limits, historical performance with methodology, fee/profit-share terms, and operating status.
- **Platform:** provides records, reporting, risk controls, and agreement workflows. The platform must not imply that it guarantees principal, profits, or operator conduct.

## Required agreement before allocation

Every allocation must have a clear, versioned agreement showing:
- allocated amount, asset/currency, start time, duration or withdrawal rules;
- exact profit-share percentage and who receives each share;
- definition of **net realized profit**, including trading fees, funding, gas, slippage, and other costs;
- loss allocation and whether losses reduce the investor's capital (never leave this ambiguous);
- maximum drawdown / loss limits, leverage limits, eligible markets, and stop conditions;
- withdrawal notice, settlement schedule, early-exit rules, and any lock-up;
- operator/platform fees, conflicts of interest, and dispute/contact process.

No allocation may start until each party has explicitly accepted the same agreement version. Terms cannot be changed retroactively.

## Accounting and fair profit calculation

- Maintain an auditable, append-only allocation ledger for deposits, withdrawals, realized P&L, fees, profit-share accruals, and settlements.
- Calculate profit share only from realized net profit, not unrealized gains or headline ROI.
- Prevent double-charging and double-counting. Use a documented high-water-mark or equivalent loss-recovery rule before charging performance share again after losses.
- Attribute results per investor allocation and time period; disclose deposits/withdrawals so performance is not misleading.
- Reconcile ledger balances against the authoritative execution/custody records. Pause settlement on reconciliation mismatch.
- Show gross and net returns, drawdown, open exposure, fees, and all allocation-level transactions.

## Safety, security, and compliance

- **MVP:** paper/simulated allocations only. No real deposits, pooled real assets, custody, withdrawal processing, or live copy-trading.
- A real-money release is a separate gated project requiring jurisdiction-specific legal/compliance review, identity/AML controls where applicable, tax and consumer disclosures, operational risk assessment, and explicit approval by the platform owner.
- Prefer a properly audited non-custodial or regulated custody architecture for any future real-money version. Never ask users to share seed phrases or private keys. Never store raw private keys.
- Use least-privilege API credentials, withdrawal-disabled exchange permissions, strong authentication, role-based access, rate limits, and an emergency pause/kill switch.
- Enforce per-investor and per-operator allocation caps, strategy exposure limits, drawdown circuit breakers, and cooling-off/withdrawal policies.
- Publish no guaranteed-return claims. Prominently disclose that investors can lose some or all allocated capital, operators can make mistakes, and historical performance does not predict future results.
- Screen operators and strategies for manipulation, fabricated performance, wash trading, conflicts of interest, and suspicious activity. Keep tamper-evident audit logs.
- Do not market this feature as a bank deposit, savings account, or insured product unless that status is legally established.

## MVP workflow

1. Operator creates a simulated strategy profile with risk settings and a proposed profit-share agreement.
2. Investor reviews the profile, paper track record, fees, drawdown, loss terms, and agreement version.
3. Investor accepts and allocates virtual funds.
4. The paper engine records simulated trades and allocation-level net P&L.
5. The system calculates illustrative profit share and updates both parties' virtual ledgers.
6. Both parties can inspect the same transaction history and export a statement.
7. Tests cover agreement versioning, accounting invariants, fee calculations, loss recovery, partial withdrawals, rounding, concurrency, and emergency stops.

## Acceptance criteria

- No real-money flow is reachable in the MVP.
- No allocation can be created without explicit acceptance and complete loss/profit terms.
- The same input ledger always produces the same allocation balances and profit-share results.
- Investors can see risks, costs, net performance, and losses as clearly as gains.
- Any accounting mismatch or risk-limit breach pauses new allocations and settlement pending review.
- Language localization applies to all screens and disclosures, without changing underlying financial calculations.
