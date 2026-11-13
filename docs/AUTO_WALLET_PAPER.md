# NEXUS Auto Wallet — Paper Trading Phase

## Scope

The Auto Wallet page is a simulation-only feature. It can replay any of the 20 strategies currently implemented by the signal engine, or use a regime-to-strategy map produced by the multi-market validation page. In adaptive mode, only strategies that passed the training and untouched holdout gates on every supplied exchange/symbol/timeframe dataset are considered. The UI restricts this mode to an exact exchange, timeframe, symbol and candle-history length combination included in the validation run; the simulator switches using the prior completed candle's regime and closes a position when that regime changes. Signals from candle N are executed at candle N+1 open to avoid same-candle lookahead. Research-only catalogue entries are rejected by the simulator. This adaptive mode remains paper-only and does not set `execution_approved`.

The simulator:
- starts with a configurable virtual USDT balance (default: 1 USDT);
- uses a configurable target balance (default: 5 USDT);
- applies a maximum loss threshold and maximum position allocation;
- accounts for estimated entry/exit fees and slippage;
- liquidates at the target, risk limit, or end of the supplied historical range;
- reports trade history, selected strategy and regime, signal/execution candle indices, equity curve, and maximum drawdown.

## Safety boundaries

This phase does not:
- create or custody a blockchain wallet;
- accept real deposits or withdrawals;
- request seed phrases or private keys;
- connect exchange API credentials;
- send live orders or run continuously in the background.

The 1-to-5 USDT target is only a simulation target, not a forecast or promise. The account may lose money in the replay. Historical results do not establish future profitability.

## Before any live integration

A separate phase and explicit user approval are required. The preferred first live architecture is an exchange sub-account/API key with trade-only permission and withdrawals disabled. Secrets must be stored outside the repository in a managed secret store or environment, never in Streamlit state, source files, or logs. Add independent security review, order-size and daily-loss caps, a kill switch, exchange minimum-notional checks, precision/lot-size checks, and paper-vs-live parity tests before enabling any live order path.

A 1 USDT balance may be below an exchange's minimum order amount and may be uneconomic after fees. The app must not imply that the target is achievable or that the exchange will accept such orders.
