# NEXUS Strategy Intelligence — Knowledge Catalogue

## Purpose

This is an expandable reference catalogue, not a claim to contain every strategy ever published. It currently records more than 40 families and variants across trend following, momentum, mean reversion, breakouts, price action, volume/microstructure, statistical arbitrage, portfolio methods, execution, event-driven, fundamental, sentiment, on-chain, and machine learning.

Each entry documents:
- the core operating idea and a practical usage outline;
- market conditions where it is commonly considered;
- conditions where it commonly fails or should be avoided;
- required input data;
- whether an executable signal implementation currently exists in NEXUS.

## Execution safety

Only entries marked `signal_engine_available` have an existing signal implementation. Research-only entries are educational knowledge and must never be treated as executable signals. A method becomes executable only after implementation, unit tests, realistic fees/slippage, no-lookahead checks, walk-forward/out-of-sample tests, and regime-specific evaluation.

The current executable set is the 11 methods in `nexus.strategy_lab.strategy_signals`. The larger catalogue does not mean the other methods have already been coded or validated.

## Regime guidance

- **Bullish / bearish trend:** trend-following, momentum, and confirmed breakouts are candidates; countertrend oscillators can stay extreme.
- **Sideways / low volatility:** bounded mean-reversion, VWAP, range and grid methods may be candidates; trend systems can whipsaw.
- **High volatility:** breakout and volatility-aware methods may be candidates, but spreads, slippage, liquidation and gaps must be modeled.
- **Any regime:** no method should be selected solely from a label. Check liquidity, data quality, costs, timeframe, asset behavior and risk limits.

Regime labels are probabilistic context, not certainty. Crypto markets can change regime abruptly and multiple regimes can coexist across timeframes.

## Required research and validation before promotion

1. Obtain primary-source methodology and document its assumptions.
2. Translate the method into deterministic, testable rules; record parameter ranges and version.
3. Validate data quality, timestamp alignment, survivorship bias, look-ahead leakage and repainting.
4. Simulate realistic maker/taker fees, spread, slippage, funding, borrow, latency, partial fills and minimum order sizes where relevant.
5. Run chronological train/validation/test splits and walk-forward testing, not random shuffles.
6. Test separately by asset, timeframe, and market regime with at least 100 closed trades per evaluated strategy/regime when sufficient data exists.
7. Apply the project gate: win rate >= 80%, positive net return, positive expectancy, and Profit Factor > 1 (or infinite), plus risk/drawdown limits. The threshold is a user-defined filter, not proof of future profitability.
8. Keep a strategy disabled when evidence is insufficient; never manufacture trades to reach 100.
9. Monitor drift and automatically disable a strategy if its live/paper evidence degrades.

## Important limitation

The catalogue describes common families and practical heuristics. It does not promise profitability, and “best conditions” are starting hypotheses to test—not universal truths. A strategy can behave differently across assets, exchanges, fees, timeframes and market eras.


## Regime-specific candidate screening

`nexus.strategy_selection.screen_regime_candidates` screens the 11 currently implemented signal strategies on the first 70% of a chronological history by default. It keeps the final 30% untouched as a holdout and applies the hard gate separately for bullish, bearish and sideways regimes: at least 100 closed trades, at least 80% winners, positive net return, positive expectancy and Profit Factor above 1 (or infinite with no losing trades). It reports only research candidates and explicitly sets `execution_approved=false`. The `validate_regime_candidates` step then evaluates the training-selected candidate on that untouched holdout using causal signals and entry-regime labels. The candidate must pass the same closed-trade, win-rate, net-return, expectancy and Profit Factor gates again. Even then, `execution_approved` remains false: replication across additional symbols/timeframes and a separate risk review are still required. This screening is not a proof of future performance.


`validate_across_markets` adds a conservative replication gate: the same candidate must pass the per-regime training and untouched-holdout checks on every supplied dataset. The UI can compare multiple symbols on the selected exchange/timeframe. This still does not grant execution permission; cross-exchange and cross-timeframe replication plus risk review remain separate gates.
