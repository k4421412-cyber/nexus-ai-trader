import pandas as pd

def add_indicators(df):
    x = df.copy()
    x["ema20"] = x["close"].ewm(span=20, adjust=False).mean()
    x["ema50"] = x["close"].ewm(span=50, adjust=False).mean()
    delta = x["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, float("nan"))
    x["rsi"] = 100 - (100 / (1 + rs))
    tr = pd.concat([(x["high"]-x["low"]), (x["high"]-x["close"].shift()).abs(),
                    (x["low"]-x["close"].shift()).abs()], axis=1).max(axis=1)
    x["atr"] = tr.rolling(14).mean()
    return x
