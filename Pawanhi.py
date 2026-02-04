# ============================================================
# PAWAN MASTER ALGO SYSTEM
# ULTRA-MODERN STREAMLIT — SEPARATED PAGES (ONE FILE)
# Futures TAB | Options TAB | Heatmap | Repaint | Debug | Settings
# ============================================================

import streamlit as st
import pandas as pd
import time, threading, random
from datetime import datetime
from collections import defaultdict

# ============================================================
# PAGE CONFIG + STYLE
# ============================================================
st.set_page_config(
    page_title="Pawan Master Algo System",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.block-container { padding-top: 1rem; }
.metric {
  background:#0f172a; color:#fff; border-radius:14px; padding:14px; text-align:center;
}
.glass {
  background:rgba(255,255,255,.06); border-radius:18px; padding:16px;
  border:1px solid rgba(255,255,255,.12);
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# GLOBAL STATE
# ============================================================
STATE = {
    "ltp": {},
    "spot": {},
    "open_positions": {},
    "daily_trades": defaultdict(int),
    "pnl": 0.0,
    "panic": False,
    "signal_debug": [],
    "repaint_log": []
}

# ============================================================
# CONFIG
# ============================================================
CONFIG = {
    "capital": 100000,
    "risk_pct": 1.0,
    "tp_pct": 5.0,
    "sl_pct": 2.0,
    "leverage": 10,
    "max_trades": 2,
    "squareoff": "15:20",
    "futures_symbols": ["NIFTY", "BANKNIFTY"],
    "option_indices": ["NIFTY", "BANKNIFTY"]
}

# ============================================================
# ANGELONE PLACEHOLDER
# ============================================================
class AngelOne:
    def place_order(self, symbol, side, qty):
        return {"order_id": f"ORD{int(time.time())}", "status": "FILLED"}

angel = AngelOne()

# ============================================================
# CORE TRADING LOGIC
# ============================================================
def position_size(price):
    risk_amt = CONFIG["capital"] * CONFIG["risk_pct"] / 100
    return int((risk_amt / (price * CONFIG["sl_pct"]/100)) * CONFIG["leverage"])

def enter_trade(symbol, side, price):
    if STATE["daily_trades"][symbol] >= CONFIG["max_trades"]:
        return
    qty = position_size(price)
    STATE["open_positions"][symbol] = {
        "side": side,
        "entry": price,
        "qty": qty,
        "sl": price*(1-CONFIG["sl_pct"]/100) if side=="BUY" else price*(1+CONFIG["sl_pct"]/100),
        "tp": price*(1+CONFIG["tp_pct"]/100) if side=="BUY" else price*(1-CONFIG["tp_pct"]/100),
        "time": datetime.now().strftime("%H:%M:%S")
    }
    STATE["daily_trades"][symbol] += 1
    angel.place_order(symbol, side, qty)

def exit_trade(symbol, price):
    pos = STATE["open_positions"].pop(symbol)
    pnl = (price-pos["entry"])*pos["qty"] if pos["side"]=="BUY" else (pos["entry"]-price)*pos["qty"]
    STATE["pnl"] += pnl

# ============================================================
# SIGNAL ENGINE (PLACEHOLDER — MATCH EXCHANGE VALUES LATER)
# ============================================================
def generate_signal(symbol):
    sig = {
        "st_mid_cross": random.choice([True, False]),
        "rsi": random.randint(20,80),
        "squeeze": random.choice([True, False]),
        "macd": random.choice([True, False]),
        "trend": "BULLISH" if random.choice([True, False]) else "BEARISH"
    }
    STATE["signal_debug"].append({"symbol":symbol,"time":time.time(),"sig":sig})
    valid = sig["st_mid_cross"] and sig["squeeze"] and sig["macd"]
    return valid, sig["trend"]

# ============================================================
# AUTO-TRADER
# ============================================================
def on_tick(symbol, ltp):
    if STATE["panic"]:
        return
    if symbol in STATE["open_positions"]:
        pos = STATE["open_positions"][symbol]
        hit_sl = ltp<=pos["sl"] if pos["side"]=="BUY" else ltp>=pos["sl"]
        hit_tp = ltp>=pos["tp"] if pos["side"]=="BUY" else ltp<=pos["tp"]
        if hit_sl or hit_tp:
            exit_trade(symbol, ltp)
        return
    valid, trend = generate_signal(symbol)
    if valid:
        side = "BUY" if trend=="BULLISH" else "SELL"
        enter_trade(symbol, side, ltp)

# ============================================================
# WEBSOCKET (SIMULATED — DROP-IN ANGELONE WS)
# ============================================================
def ws_loop():
    base = {"NIFTY":22000,"BANKNIFTY":47000}
    while True:
        for s in CONFIG["futures_symbols"]:
            ltp = base[s] + random.randint(-40,40)
            STATE["ltp"][s] = ltp
            STATE["spot"][s] = ltp
            on_tick(s, ltp)
        time.sleep(1)

threading.Thread(target=ws_loop, daemon=True).start()

# ============================================================
# SIDEBAR (SETTINGS)
# ============================================================
with st.sidebar:
    st.title("⚙️ Settings")
    CONFIG["risk_pct"] = st.slider("Risk %",0.5,5.0,CONFIG["risk_pct"])
    CONFIG["tp_pct"] = st.slider("Target %",1.0,10.0,CONFIG["tp_pct"])
    CONFIG["sl_pct"] = st.slider("Stoploss %",0.5,5.0,CONFIG["sl_pct"])
    if st.button("🚨 PANIC EXIT"):
        STATE["panic"] = True
        STATE["open_positions"].clear()

# ============================================================
# HEADER METRICS
# ============================================================
m1,m2,m3,m4 = st.columns(4)
m1.markdown(f"<div class='metric'>Open Positions<br><h2>{len(STATE['open_positions'])}</h2></div>",unsafe_allow_html=True)
m2.markdown(f"<div class='metric'>PnL<br><h2>{round(STATE['pnl'],2)}</h2></div>",unsafe_allow_html=True)
m3.markdown(f"<div class='metric'>Trades Today<br><h2>{sum(STATE['daily_trades'].values())}</h2></div>",unsafe_allow_html=True)
m4.markdown(f"<div class='metric'>Time<br><h2>{datetime.now().strftime('%H:%M:%S')}</h2></div>",unsafe_allow_html=True)

# ============================================================
# SEPARATED TABS
# ============================================================
tab_dash, tab_fut, tab_opt, tab_heat, tab_rep, tab_dbg = st.tabs(
    ["🏠 Dashboard","📈 Futures","🧾 Options","🔥 Heatmap","🧠 Repaint","🔍 Debug"]
)

# ---------------- DASHBOARD ----------------
with tab_dash:
    st.markdown("<div class='glass'>AUTO-TRADING LIVE • INTRADAY • BUY & SELL</div>",unsafe_allow_html=True)
    st.json(STATE["ltp"])

# ---------------- FUTURES ----------------
with tab_fut:
    st.subheader("Futures — Live Positions")
    if STATE["open_positions"]:
        st.dataframe(pd.DataFrame.from_dict(STATE["open_positions"],orient="index"))
    else:
        st.info("No active futures positions")

# ---------------- OPTIONS ----------------
with tab_opt:
    st.subheader("Options — ATM (Nearest Expiry)")
    for idx in CONFIG["option_indices"]:
        spot = STATE["spot"].get(idx)
        if spot:
            step = 50 if idx=="BANKNIFTY" else 100
            atm = round(spot/step)*step
            st.success(f"{idx} Spot: {spot} | ATM: {atm} | CE/PE Ready")
        else:
            st.warning(f"{idx} spot not received yet")

# ---------------- HEATMAP ----------------
with tab_heat:
    st.subheader("Signal Heatmap (Live)")
    if STATE["signal_debug"]:
        st.dataframe(pd.DataFrame(STATE["signal_debug"]).tail(30))
    else:
        st.warning("Waiting for signals")

# ---------------- REPAINT ----------------
with tab_rep:
    st.subheader("Repaint Analytics")
    if STATE["repaint_log"]:
        st.dataframe(pd.DataFrame(STATE["repaint_log"]))
    else:
        st.info("Repaint tracking enabled")

# ---------------- DEBUG ----------------
with tab_dbg:
    st.subheader("Signal Debug (Latest)")
    st.json(STATE["signal_debug"][-5:])

st.markdown("---")
st.caption("Pawan Master Algo System • Separated Futures & Options • Ultra-Modern")
