"""Expandable trading-strategy knowledge base for NEXUS.

Educational metadata is not a live trading signal. Only strategies marked
implemented can be passed to the current signal engine; all others are
research-only until coded, tested, and independently validated.
"""

from copy import deepcopy

REGIMES = ("bullish", "bearish", "sideways", "high_volatility", "low_volatility")

# Each record explains the method, its operating logic, suitable conditions,
# failure modes, and the minimum data it needs. Rules are descriptive rather
# than a promise of profitability. Implemented IDs map to strategy_signals().
_STRATEGIES = [
    # Trend following
    ("ema_9_21", "EMA 9/21 crossover", "trend", "Cross of fast and slow exponential averages; enter on confirmed bullish cross and exit on bearish cross.", ["bullish"], ["sideways", "whipsaw"], "OHLCV, EMA 9/21", True),
    ("sma_20_50", "SMA 20/50 crossover", "trend", "Cross of 20- and 50-period simple averages; confirm with slope and volume.", ["bullish"], ["sideways", "late entries"], "OHLCV, SMA 20/50", True),
    ("ema_20_50_rsi", "EMA 20/50 + RSI", "trend_momentum", "Bullish EMA cross with RSI strength filter; exit when trend reverses.", ["bullish"], ["sideways", "overbought spikes"], "OHLCV, EMA 20/50, RSI", True),
    ("macd_cross", "MACD crossover", "momentum", "Enter when MACD crosses above its signal line; exit on reverse cross.", ["bullish", "high_volatility"], ["sideways", "divergence"], "OHLCV, MACD", True),
    ("ema_macd", "EMA trend + MACD", "trend_momentum", "Require bullish EMA structure and a fresh MACD cross to reduce countertrend entries.", ["bullish"], ["sideways", "late confirmation"], "OHLCV, EMA, MACD", True),
    ("adx_dmi", "ADX + Directional Movement", "trend", "Trade +DI/-DI direction only when ADX confirms sufficient trend strength.", ["bullish", "bearish"], ["sideways", "low_adx"], "OHLCV, ADX, +DI/-DI", True),
    ("supertrend", "Supertrend", "trend", "Follow ATR-based trend state; reverse or trail stop when the band flips.", ["bullish", "bearish", "high_volatility"], ["sideways", "band whipsaw"], "OHLCV, ATR", True),
    ("ichimoku", "Ichimoku Cloud", "trend", "Use cloud position, Tenkan/Kijun cross and Chikou confirmation; avoid signals inside cloud.", ["bullish", "bearish"], ["sideways", "cloud congestion"], "OHLCV, Ichimoku components", True),
    ("parabolic_sar", "Parabolic SAR", "trend", "Trail a stop beneath/above price and reverse on SAR flip; best as trend management.", ["bullish", "bearish"], ["sideways", "rapid reversals"], "OHLCV, SAR", False),
    ("donchian_breakout", "Donchian channel breakout", "breakout", "Enter on close beyond the prior range boundary; exit on opposite channel or trailing stop.", ["bullish", "bearish", "high_volatility"], ["sideways", "false breakouts"], "OHLCV, prior rolling highs/lows", True),
    ("keltner_breakout", "Keltner channel breakout", "breakout", "Trade a close outside an EMA/ATR envelope with volatility expansion confirmation.", ["bullish", "bearish", "high_volatility"], ["low_volatility", "mean-reverting ranges"], "OHLCV, EMA, ATR", True),
    ("opening_range", "Opening range breakout", "breakout", "Break the first session range with volume confirmation and a defined invalidation level.", ["high_volatility"], ["low_volume sessions", "choppy opens"], "Intraday OHLCV, session calendar, volume", False),
    # Mean reversion
    ("bollinger_reversion", "Bollinger Bands mean reversion", "mean_reversion", "In a range, fade statistically stretched moves toward the middle band; require rejection/confirmation.", ["sideways", "low_volatility"], ["strong_trends", "band-walk"], "OHLCV, Bollinger Bands", True),
    ("rsi_reversion", "RSI mean reversion", "mean_reversion", "Look for RSI recovery from oversold/overbought zones; confirm with structure.", ["sideways", "low_volatility"], ["strong_trends", "momentum collapse"], "OHLCV, RSI", True),
    ("stochastic_reversal", "Stochastic reversal", "mean_reversion", "Use %K/%D cross from an extreme zone only when the broader market is ranging.", ["sideways"], ["strong_trends", "persistent extremes"], "OHLCV, Stochastic", True),
    ("vwap_reversion", "VWAP reversion", "mean_reversion", "Fade distance from session VWAP after rejection; define stop beyond the excursion.", ["sideways", "low_volatility"], ["trend days", "thin liquidity"], "Intraday OHLCV, volume, session boundaries", False),
    ("zscore_reversion", "Z-score / statistical reversion", "mean_reversion", "Trade extreme standardized deviations only after testing stationarity and stable lookback behavior.", ["sideways", "low_volatility"], ["regime shifts", "non-stationary assets"], "Price/return series, rolling mean and deviation", True),
    ("rsi_divergence", "RSI divergence", "reversal", "Compare confirmed price and RSI swing pivots; enter only after a price-structure trigger.", ["sideways", "late_trend"], ["strong momentum", "unconfirmed pivots"], "OHLCV, RSI, pivot detection", False),
    ("cci_reversion", "CCI reversal", "mean_reversion", "Use CCI extreme exit/re-entry as a stretch signal, with trend and volatility filters.", ["sideways"], ["strong_trends", "noisy data"], "OHLCV, CCI", True),
    # Momentum and volatility
    ("roc_momentum", "Rate of Change momentum", "momentum", "Enter on positive ROC acceleration and exit when momentum weakens or reverses.", ["bullish", "high_volatility"], ["sideways", "momentum exhaustion"], "OHLCV, ROC", True),
    ("tsi_momentum", "True Strength Index", "momentum", "Use smoothed momentum and signal-line cross, ideally aligned with the higher-timeframe trend.", ["bullish", "bearish"], ["sideways", "lagging signals"], "OHLCV, double-smoothed momentum", True),
    ("williams_r", "Williams %R", "mean_reversion", "Use extreme-zone recovery as a timing trigger, not as a standalone buy/sell command.", ["sideways"], ["strong_trends", "persistent extremes"], "OHLCV, Williams %R", True),
    ("atr_breakout", "ATR channel breakout", "breakout", "Enter when price clears an ATR-scaled envelope; use ATR-based stop and position sizing.", ["bullish", "bearish", "high_volatility"], ["sideways", "volatility contraction"], "OHLCV, EMA, ATR", True),
    ("volatility_squeeze", "Bollinger/Keltner squeeze", "breakout", "Wait for volatility compression, then trade a confirmed expansion and directional break.", ["high_volatility"], ["false expansion", "low volume"], "OHLCV, Bollinger, Keltner, volume", False),
    ("atr_trailing", "ATR trailing stop", "risk_management", "Use ATR distance to trail an existing position; this is an exit/risk method, not a complete entry system.", ["bullish", "bearish", "high_volatility"], ["gaps", "abrupt liquidity loss"], "OHLCV, ATR", False),
    # Price action / market structure
    ("support_resistance", "Support and resistance", "price_action", "Mark validated swing zones; trade rejection or confirmed break/retest with invalidation beyond the zone.", ["sideways", "bullish", "bearish"], ["weakly defined levels", "news gaps"], "OHLCV, swing pivots, volume", False),
    ("break_retest", "Breakout and retest", "price_action", "Require a close beyond a meaningful level, then a successful retest before entry.", ["bullish", "bearish"], ["failed retests", "thin liquidity"], "OHLCV, levels, volume", False),
    ("candlestick_patterns", "Candlestick patterns", "price_action", "Use engulfing, pin bars and related patterns only at meaningful levels and with confirmation.", ["sideways", "reversal zones"], ["patterns in isolation", "low timeframe noise"], "OHLCV, context levels", False),
    ("elliott_wave", "Elliott Wave", "price_action", "Build alternative wave counts and trade only after explicit invalidation levels; subjective counts need strict tests.", ["bullish", "bearish"], ["ambiguous counts", "relabeling bias"], "OHLCV, swing structure", False),
    ("wyckoff", "Wyckoff accumulation/distribution", "volume_structure", "Interpret range phases, tests and supply/demand events; require objective volume/price rules.", ["sideways", "breakout transition"], ["subjective labeling", "poor volume data"], "OHLCV, volume, range structure", False),
    ("volume_profile", "Volume profile / market profile", "volume_structure", "Use value area, point of control and acceptance/rejection to frame entries and targets.", ["sideways", "breakout transition"], ["incomplete volume", "venue fragmentation"], "Trades or OHLCV volume, session profile", False),
    ("order_flow", "Order flow / footprint / delta", "microstructure", "Read aggressive buy/sell imbalance and absorption at levels; validate feed quality and venue scope.", ["high_volatility", "breakout transition"], ["spoofing", "fragmented venues", "missing tick data"], "Trades, bid/ask, order book snapshots", False),
    ("liquidity_sweep", "Liquidity sweep / stop run", "price_action", "Detect a sweep of a prior swing followed by reclaim/structure shift; avoid labeling every wick a sweep.", ["reversal zones", "high_volatility"], ["news spikes", "weak pivot definitions"], "OHLCV, swing levels, preferably trades", False),
    ("market_profile", "TPO / auction market theory", "volume_structure", "Assess balance, imbalance, value migration and acceptance outside value before directional trades.", ["sideways", "breakout transition"], ["session dependence", "incomplete data"], "Intraday price distribution, session calendar", False),
    # Quant / cross-market
    ("pairs_trading", "Pairs trading / cointegration", "statistical_arbitrage", "Trade spread deviations only after rolling cointegration/stability tests and hedge-ratio recalibration.", ["sideways"], ["correlation breakdown", "structural change"], "Synchronized prices for related assets", False),
    ("mean_reversion_spread", "Statistical spread reversion", "statistical_arbitrage", "Model a stationary spread and trade residual extremes with stop on model failure.", ["sideways"], ["non-stationary spread", "model drift"], "Multi-asset synchronized price history", False),
    ("momentum_rotation", "Cross-sectional momentum rotation", "portfolio", "Rank a defined universe by risk-adjusted momentum and rebalance with turnover/cost controls.", ["bullish", "sideways"], ["market-wide crash", "survivorship bias"], "Broad point-in-time asset universe, OHLCV", False),
    ("factor_model", "Factor investing", "portfolio", "Rank assets using tested value, momentum, quality/liquidity and risk factors; rebalance periodically.", ["bullish", "sideways"], ["factor crowding", "data snooping"], "Fundamental/market data, point-in-time universe", False),
    ("arbitrage", "Cross-exchange arbitrage", "arbitrage", "Compare executable bid/ask after fees, transfer delays, funding and inventory constraints; never use last price alone.", ["any"], ["latency", "withdrawal freezes", "fees", "slippage"], "Synchronized order books, balances, fee schedules", False),
    ("funding_basis", "Funding rate / basis trading", "carry", "Evaluate perpetual funding against spot/futures basis and hedge both legs; include liquidation and borrow costs.", ["sideways", "low_volatility"], ["funding flips", "basis widening", "liquidation"], "Funding, spot/perp books, margin and borrow data", False),
    ("grid", "Grid trading", "systematic", "Place bounded staggered orders inside a pre-defined range; stop/reconfigure if price leaves the regime.", ["sideways", "low_volatility"], ["persistent trends", "inventory accumulation"], "OHLCV, tick size, fees, inventory", False),
    ("dca", "Dollar-cost averaging", "systematic", "Schedule fixed notional purchases; define total budget and thesis invalidation. It is allocation, not guaranteed profit.", ["long_horizon", "low_volatility"], ["falling-knife risk", "uncapped averaging"], "Price, schedule, budget", False),
    ("market_making", "Market making", "microstructure", "Quote both sides around fair value with inventory skew and adverse-selection controls.", ["sideways", "low_volatility"], ["toxic flow", "gaps", "thin books"], "Live order book, trades, latency, inventory", False),
    ("scalping", "Scalping", "execution", "Capture small intraday moves only when spread, fees, latency and fill probability leave positive expected value.", ["high_liquidity", "low_spread"], ["high fees", "latency", "slippage"], "Tick/trade data, order book, execution simulator", False),
    ("swing", "Swing trading", "multi_timeframe", "Use higher-timeframe structure for bias and lower timeframe for entry; size to wider stops.", ["bullish", "bearish", "sideways"], ["event gaps", "overnight risk"], "Multi-timeframe OHLCV", False),
    ("position", "Position trading", "multi_timeframe", "Hold a thesis over weeks/months using macro/fundamental context and broad trend filters.", ["bullish", "bearish"], ["thesis decay", "macro regime change"], "Higher-timeframe OHLCV, fundamentals, macro", False),
    ("news_event", "News/event-driven", "event_driven", "Trade only timestamped, verified events with measured reaction and strict spread/liquidity gates.", ["high_volatility"], ["rumors", "headline latency", "event gaps"], "Timestamped reliable news, OHLCV, order book", False),
    ("onchain", "On-chain flow analysis", "fundamental", "Combine exchange flows, holder concentration, realized metrics and network activity; account for entity-label uncertainty.", ["bullish", "bearish", "sideways"], ["label errors", "chain coverage gaps"], "Chain data, entity labels, market prices", False),
    ("sentiment", "Sentiment / social analytics", "sentiment", "Aggregate source-weighted sentiment and change in attention; filter bots, manipulation and duplicate posts.", ["bullish", "bearish", "high_volatility"], ["spam", "coordinated manipulation", "sarcasm"], "Timestamped social/news text, source reliability", False),
    ("fundamental", "Fundamental / tokenomics", "fundamental", "Assess supply schedules, unlocks, utility, revenue, governance and valuation; use as a thesis filter not a precise timer.", ["long_horizon"], ["opaque supply", "insider concentration", "unverifiable claims"], "Audited/project disclosures, on-chain and financial data", False),
    ("ml_supervised", "Supervised ML prediction", "machine_learning", "Train time-aware models on point-in-time features with walk-forward validation and calibration.", ["any"], ["leakage", "overfitting", "distribution shift"], "Clean point-in-time features, labels, compute", False),
    ("ml_reinforcement", "Reinforcement learning", "machine_learning", "Train policies in realistic cost/slippage simulators; constrain actions and test out-of-sample.", ["any"], ["simulator exploitation", "unstable policy", "reward hacking"], "Market simulator, state/action/reward design", False),
    ("ensemble", "Ensemble / regime switching", "meta_strategy", "Combine independently validated strategies and allocate only when regime and confidence gates agree.", ["any"], ["correlated failures", "overfit weights"], "Validated component signals, regime labels, risk model", False),
]

IMPLEMENTED_IDS = frozenset(row[0] for row in _STRATEGIES if row[-1])


def list_strategies(category=None):
    """Return defensive copies; optional category filter."""
    rows = _STRATEGIES if category is None else [row for row in _STRATEGIES if row[2] == category]
    return [
        {
            "id": r[0], "name": r[1], "category": r[2], "how_to_use": r[3],
            "best_conditions": list(r[4]), "avoid_conditions": list(r[5]),
            "required_data": r[6], "implemented": r[7],
            "status": "signal_engine_available" if r[7] else "research_only",
        }
        for r in rows
    ]


def get_strategy(strategy_id):
    """Get one strategy by stable ID, or None if unknown."""
    return next((item for item in list_strategies() if item["id"] == strategy_id), None)


def recommend_strategies(regime, *, include_research=False):
    """Rank methods by documented regime fit; never promote research-only methods to execution."""
    if regime not in REGIMES and regime != "any":
        raise ValueError(f"Unknown regime: {regime}")
    candidates = []
    for item in list_strategies():
        if regime == "any" or regime in item["best_conditions"] or "any" in item["best_conditions"]:
            if item["implemented"] or include_research:
                candidates.append(item)
    return candidates


def executable_strategy_ids():
    """Only IDs with a matching, existing signal implementation are executable."""
    return sorted(IMPLEMENTED_IDS)
