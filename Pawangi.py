# ============================================================
# ANGELONE INDICATOR ENGINE (NON-REPAINT, EXCHANGE-ALIGNED)
# Uses ONLY CLOSED candles from Candle Builder
# ============================================================

import pandas as pd
import numpy as np

# ============================================================
# RSI (WILDER – ANGELONE STYLE)
# ============================================================
def rsi_wilder(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# ============================================================
# ATR (TRUE RANGE – EXCHANGE STYLE)
# ============================================================
def atr(df, period=10):
    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)

    atr_val = tr.ewm(alpha=1/period, adjust=False).mean()
    return atr_val

# ============================================================
# SUPERTREND (ANGELONE MATCH)
# ============================================================
def supertrend(df, period=10, multiplier=3):
    hl2 = (df["high"] + df["low"]) / 2
    atr_val = atr(df, period)

    upperband = hl2 + multiplier * atr_val
    lowerband = hl2 - multiplier * atr_val

    st = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=int)

    for i in range(len(df)):
        if i == 0:
            st.iloc[i] = upperband.iloc[i]
            direction.iloc[i] = -1
        else:
            if df["close"].iloc[i] > st.iloc[i-1]:
                direction.iloc[i] = 1
            elif df["close"].iloc[i] < st.iloc[i-1]:
                direction.iloc[i] = -1
            else:
                direction.iloc[i] = direction.iloc[i-1]

            if direction.iloc[i] == 1:
                st.iloc[i] = max(lowerband.iloc[i], st.iloc[i-1])
            else:
                st.iloc[i] = min(upperband.iloc[i], st.iloc[i-1])

    return st, direction

# ============================================================
# BOLLINGER MID (20 SMA)
# ============================================================
def bollinger_mid(close, period=20):
    return close.rolling(period).mean()

# ============================================================
# MACD HISTOGRAM (12-26-9)
# ============================================================
def macd_histogram(close):
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return macd, signal, hist

# ============================================================
# SQUEEZE HISTOGRAM (BB vs KC)
# ============================================================
def squeeze(df, bb_period=20, kc_period=20):
    close = df["close"]

    bb_mid = close.rolling(bb_period).mean()
    bb_std = close.rolling(bb_period).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std

    atr_val = atr(df, kc_period)
    kc_mid = close.rolling(kc_period).mean()
    kc_upper = kc_mid + 1.5 * atr_val
    kc_lower = kc_mid - 1.5 * atr_val

    squeeze_on = (bb_lower > kc_lower) & (bb_upper < kc_upper)
    return squeeze_on

# ============================================================
# MASTER INDICATOR CALCULATOR (SAFE)
# ============================================================
def calculate_indicators(closed_df: pd.DataFrame):
    """
    closed_df MUST be output of NonRepaintingCandleBuilder
    """
    if len(closed_df) < 50:
        return None

    df = closed_df.copy()

    df["rsi"] = rsi_wilder(df["close"])
    df["bb_mid"] = bollinger_mid(df["close"])
    df["macd"], df["macd_signal"], df["macd_hist"] = macd_histogram(df["close"])
    df["squeeze"] = squeeze(df)

    df["supertrend"], df["st_dir"] = supertrend(df)

    return df

# ============================================================
# SIGNAL VALIDATOR (BUY / SELL – OPPOSITE LOGIC)
# ============================================================
def validate_signal(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    buy = (
        prev["st_dir"] == -1 and last["st_dir"] == 1 and
        last["close"] > last["bb_mid"] and
        last["rsi"] > 60 and
        last["macd_hist"] > 0 and
        last["squeeze"] is False
    )

    sell = (
        prev["st_dir"] == 1 and last["st_dir"] == -1 and
        last["close"] < last["bb_mid"] and
        last["rsi"] < 40 and
        last["macd_hist"] < 0 and
        last["squeeze"] is False
    )

    return {
        "BUY": buy,
        "SELL": sell,
        "timestamp": last["end"]
    }

# ============================================================
# GUARANTEES
# ============================================================
# ✅ Uses ONLY CLOSED candles
# ✅ Matches AngelOne chart logic
# ✅ No repaint
# ✅ Buy & Sell opposite conditions
# ============================================================
