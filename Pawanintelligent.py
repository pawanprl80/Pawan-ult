# ============================================================
# 🧠 PAWAN MASTER ALGO SYSTEM — ALL-IN-ONE STREAMLIT
# NSE FUTURES • LIVE INDICATORS • SIGNAL VALIDATOR
# VISUAL VALIDATOR • ORDER PLACEMENT • ORDERBOOK • P&L
# PANIC BUTTON • PAPER MODE READY • PHASE 1-4 MERGED
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime as dt
import time

# ===================== CONFIG =====================
APP_NAME = "PAWAN MASTER ALGO SYSTEM"
TIMEFRAME = "5 Min"
MODE = "PAPER"
REFRESH_SEC = 1
MAX_TRADES_PER_SYMBOL = 2
TP_PCT = 0.05
QTY = 1

st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="expanded")

# ===================== STYLE =====================
st.markdown("""
<style>
body { background-color:#0b1020; color:white; }
thead tr th { background-color:#111827 !important; }
tbody tr td { font-family: monospace; font-size:14px; }
.buy { color:#00ff99; font-weight:bold; }
.sell { color:#ff4d4d; font-weight:bold; }
.neutral { color:#9ca3af; }
</style>
""", unsafe_allow_html=True)

# ===================== HEADER =====================
st.markdown(f"""
<h2 style='text-align:center;color:#00ff99'>{APP_NAME}</h2>
<p style='text-align:center'>🟢 WS | ⏱ {TIMEFRAME} | NSE FUT | {MODE}</p>
""", unsafe_allow_html=True)

# ===================== SESSION STATE =====================
for key, default in {
    "last_price": {},
    "latest_rows": [],
    "orders": [],
    "positions": [],
    "trade_count": {},
    "panic": False,
    "realized_pnl": 0.0
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ===================== SYMBOLS =====================
SYMBOLS = [
    "TCSFUT","INFYFUT","RELIANCEFUT","HDFCBANKFUT","ICICIBANKFUT",
    "SBINFUT","LTIMFUT","AXISBANKFUT","BAJFINANCEFUT","ITCFUT"
]

# ===================== INDICATOR FUNCTIONS =====================
def compute_indicators(prices):
    close = prices
    mid = close.rolling(20).mean().iloc[-1]
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
    macd = (
        close.ewm(span=12, adjust=False).mean()
        - close.ewm(span=26, adjust=False).mean()
    ).iloc[-1]
    tr = close.diff().abs().rolling(10).mean().iloc[-1]
    supertrend = close.iloc[-1] - (3 * tr)
    return round(mid,2), round(rsi,1), round(macd,2), round(supertrend,2)

def signal_logic(close, mid, rsi, macd, st_val):
    if close > mid and rsi >= 70 and macd > 0 and close > st_val:
        return "BUY"
    if close < mid and rsi <= 30 and macd < 0 and close < st_val:
        return "SELL"
    return None

# ===================== ORDER HELPERS =====================
def can_trade(symbol):
    today = dt.date.today().isoformat()
    key = f"{symbol}_{today}"
    return st.session_state.trade_count.get(key, 0) < MAX_TRADES_PER_SYMBOL

def record_trade(symbol):
    today = dt.date.today().isoformat()
    key = f"{symbol}_{today}"
    st.session_state.trade_count[key] = st.session_state.trade_count.get(key, 0) + 1

def place_order(symbol, side, price):
    if not can_trade(symbol):
        return False, "Max trades reached"

    order = {
        "Time": dt.datetime.now().strftime("%H:%M:%S"),
        "Symbol": symbol,
        "Side": side,
        "Qty": QTY,
        "Price": price,
        "Status": "FILLED"
    }
    st.session_state.orders.append(order)

    tp = price * (1 + TP_PCT) if side == "BUY" else price * (1 - TP_PCT)

    position = {
        "Symbol": symbol,
        "Side": side,
        "Entry": price,
        "Qty": QTY,
        "TP": round(tp,2),
        "OpenTime": dt.datetime.now(),
        "Status": "OPEN"
    }
    st.session_state.positions.append(position)
    record_trade(symbol)
    return True, "Order Placed"

# ===================== SIDEBAR NAVIGATION =====================
page = st.sidebar.radio("📊 MENU", [
    "Dashboard",
    "Signal Validator",
    "Visual Validator",
    "Order Placement",
    "Order Book",
    "Position Book",
    "Profit/Loss",
    "🚨 PANIC BUTTON"
])

# ===================== DASHBOARD / MARKET GRID =====================
if page == "Dashboard":
    st.subheader("📊 MARKET GRID (LIVE)")

    placeholder = st.empty()
    rows = []

    for sym in SYMBOLS:
        base = st.session_state.last_price.get(sym, 1000 + np.random.randn()*50)
        ltp = round(base + np.random.randn()*5, 2)
        st.session_state.last_price[sym] = ltp

        prices = pd.Series(np.random.randn(60).cumsum() + ltp)
        mid, rsi, macd, st_val = compute_indicators(prices)
        signal = signal_logic(ltp, mid, rsi, macd, st_val)

        delta = ltp - base
        arrow = "🟢" if delta >= 0 else "🔴"

        rows.append({
            "Symbol": sym,
            "LTP": f"{ltp} {arrow}",
            "Δ": round(delta,2),
            "RSI": rsi,
            "ST": "↑" if ltp > st_val else "↓",
            "MACD": "+" if macd > 0 else "-",
            "Signal": "💎 BUY" if signal=="BUY" else "💎 SELL" if signal=="SELL" else ""
        })

    df = pd.DataFrame(rows)
    st.session_state.latest_rows = rows
    placeholder.dataframe(df, use_container_width=True)

# ===================== SIGNAL VALIDATOR =====================
elif page == "Signal Validator":
    st.subheader("🧠 SIGNAL VALIDATOR")
    if not st.session_state.latest_rows:
        st.info("No market data yet")
    else:
        symbols = [r["Symbol"] for r in st.session_state.latest_rows]
        selected = st.selectbox("Select Symbol", symbols)
        row = next(r for r in st.session_state.latest_rows if r["Symbol"] == selected)

        st.markdown(f"### {selected}")
        logic = [
            ("Price > BB Mid", row["LTP"] > float(str(row["LTP"]).split()[0])),
            ("RSI ≥ 70 (BUY)", row["RSI"] >= 70),
            ("RSI ≤ 30 (SELL)", row["RSI"] <= 30),
            ("MACD > 0", row["MACD"]=="+"),
            ("MACD < 0", row["MACD"]=="-"),
            ("Price > Supertrend", row["ST"]=="↑"),
            ("Price < Supertrend", row["ST"]=="↓")
        ]
        logic_df = pd.DataFrame(logic, columns=["Condition", "True / False"])
        st.table(logic_df)

        if row["Signal"] == "💎 BUY":
            st.success("💎 FINAL SIGNAL: BUY")
        elif row["Signal"] == "💎 SELL":
            st.error("💎 FINAL SIGNAL: SELL")
        else:
            st.warning("NO VALID SIGNAL")

# ===================== VISUAL VALIDATOR =====================
elif page == "Visual Validator":
    st.subheader("👁 VISUAL VALIDATOR")
    if not st.session_state.latest_rows:
        st.warning("No validated market data")
    else:
        symbols = [r["Symbol"] for r in st.session_state.latest_rows]
        symbol = st.selectbox("Select Symbol", symbols)
        row = next(r for r in st.session_state.latest_rows if r["Symbol"] == symbol)

        n = 80
        base = float(str(row["LTP"]).split()[0])
        prices = np.cumsum(np.random.randn(n)) + base
        df = pd.DataFrame({
            "open": prices + np.random.randn(n),
            "high": prices + abs(np.random.randn(n)),
            "low": prices - abs(np.random.randn(n)),
            "close": prices
        })

        df["mid"] = df["close"].rolling(20).mean()
        delta = df["close"].diff()
        gain = delta.where(delta>0,0).rolling(14).mean()
        loss = -delta.where(delta<0,0).rolling(14).mean()
        df["rsi"] = 100 - (100 / (1 + (gain / loss)))
        df["macd"] = df["close"].ewm(span=12,adjust=False).mean() - df["close"].ewm(span=26,adjust=False).mean()
        tr = df["close"].diff().abs().rolling(10).mean()
        df["supertrend"] = df["close"] - (3*tr)

        signal_idx = None
        if row["Signal"] in ["💎 BUY","💎 SELL"]:
            signal_idx = df.index[-1]

        fig = go.Figure()
        fig.add_candlestick(open=df["open"], high=df["high"], low=df["low"], close=df["close"], name="Price")
        fig.add_trace(go.Scatter(y=df["mid"], name="BB Mid", line=dict(color="orange")))
        fig.add_trace(go.Scatter(y=df["supertrend"], name="Supertrend", line=dict(color="cyan")))
        if signal_idx is not None:
            fig.add_trace(go.Scatter(
                x=[signal_idx],
                y=[df["close"].iloc[-1]],
                mode="markers",
                marker=dict(symbol="diamond", size=16,
                            color="lime" if row["Signal"]=="💎 BUY" else "red"),
                name=row["Signal"]
            ))
        fig.update_layout(height=520, template="plotly_dark", title=f"{symbol} • Visual Validator", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("RSI", round(df["rsi"].iloc[-1],1))
        c2.metric("MACD", round(df["macd"].iloc[-1],2))
        c3.metric("BB Mid", round(df["mid"].iloc[-1],2))
        c4.metric("Supertrend", round(df["supertrend"].iloc[-1],2))

        if row["Signal"] in ["💎 BUY","💎 SELL"]:
            st.success(f"💎 SIGNAL CONFIRMED: {row['Signal']}")

# ===================== ORDER PLACEMENT =====================
elif page == "Order Placement":
    st.subheader("⚡ EXECUTION ENGINE")
    if not st.session_state.latest_rows:
        st.info("No signals")
    else:
        tradable = [r for r in st.session_state.latest_rows if r["Signal"] in ["💎 BUY","💎 SELL"]]
        if tradable:
            for r in tradable:
                col1,col2,col3 = st.columns([3,2,2])
                col1.markdown(f"**{r['Symbol']}** → {r['Signal']}")
                col2.write(f"LTP: {r['LTP']}")
                if col3.button(f"PLACE {r['Signal']} {r['Symbol']}", key=r['Symbol']):
                    ok,msg = place_order(r["Symbol"], "BUY" if r['Signal']=="💎 BUY" else "SELL", float(str(r["LTP"]).split()[0]))
                    st.toast(msg)
        else:
            st.info("No confirmed signals")

# ===================== ORDER BOOK =====================
elif page == "Order Book":
    st.subheader("📘 ORDER BOOK")
    if st.session_state.orders:
        st.table(pd.DataFrame(st.session_state.orders))
    else:
        st.info("No orders yet")

# ===================== POSITION BOOK =====================
elif page == "Position Book":
    st.subheader("📦 POSITION BOOK")
    live_pnl = 0.0
    rows = []
    for p in st.session_state.positions:
        if p["Status"] != "OPEN":
            continue
        ltp = p["Entry"] + np.random.randn()*5
        if p["Side"]=="BUY":
            pnl = (ltp-p["Entry"])*p["Qty"]
            hit_tp = ltp>=p["TP"]
        else:
            pnl = (p["Entry"]-ltp)*p["Qty"]
            hit_tp = ltp<=p["TP"]
        live_pnl += pnl
        if hit_tp:
            p["Status"]="CLOSED"
            st.session_state.realized_pnl += pnl
            continue
        rows.append({
            "Symbol":p["Symbol"], "Side":p["Side"], "Entry":p["Entry"], "LTP":round(ltp,2),
            "TP":p["TP"], "P&L":round(pnl,2)
        })
    if rows:
        st.table(pd.DataFrame(rows))
    else:
        st.info("No open positions")

# ===================== PROFIT / LOSS =====================
elif page == "Profit/Loss":
    st.subheader("💰 PROFIT & LOSS")
    c1,c2 = st.columns(2)
    c1.metric("Realized P&L", round(st.session_state.realized_pnl,2))
    live_pnl = sum(
        ((p["Entry"]- (p["Entry"]+np.random.randn()*5))*p["Qty"] if p["Side"]=="SELL" else
         ((p["Entry"]+np.random.randn()*5)-p["Entry"])*p["Qty"])
        for p in st.session_state.positions if p["Status"]=="OPEN"
    )
    c2.metric("Live P&L", round(live_pnl,2))

# ===================== PANIC BUTTON =====================
elif page == "🚨 PANIC BUTTON":
    st.subheader("🚨 PANIC")
    if st.button("🚨 KILL ALL POSITIONS"):
        st.session_state.positions = []
        st.session_state.orders = []
        st.session_state.panic = True
        st.error("SYSTEM HALTED — ALL POSITIONS CLOSED")
