import pandas as pd

def ema_rsi_signals(df):
    buy = (df["ema20"] > df["ema50"]) & (df["ema20"].shift() <= df["ema50"].shift()) & (df["rsi"] < 70)
    return buy.fillna(False)

def backtest(df, signals, fee=0.001, slippage=0.0005):
    cash, units, trades = 1000.0, 0.0, 0
    equity = []
    for i in range(1, len(df)):
        price = float(df.iloc[i]["close"])
        if bool(signals.iloc[i]) and units == 0 and cash > 0:
            cost = price * (1 + fee + slippage)
            units = cash / cost
            cash = 0.0
            trades += 1
        elif units > 0 and (float(df.iloc[i]["ema20"]) < float(df.iloc[i]["ema50"])):
            cash = units * price * (1 - fee - slippage)
            units = 0.0
            trades += 1
        equity.append(cash + units * price)
    final = equity[-1] if equity else 1000.0
    return {"initial_balance": 1000, "final_balance": round(final, 2),
            "net_return_pct": round((final/1000-1)*100, 2), "closed_and_open_actions": trades}
