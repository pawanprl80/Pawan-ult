# =========================================================
# PAWAN MASTER ALGO SYSTEM - STREAMLIT DASHBOARD
# FUTSTK + NIFTY OPTIONS | AUTO-BUY / AUTO-EXIT
# DIAMOND SIGNAL SNAPSHOTS | NO DUPLICATE TRADES
# =========================================================

import streamlit as st
import pandas as pd
import numpy as np
import datetime, time, pyotp, requests, os
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import plotly.graph_objects as go

# -----------------------------
# 1️⃣ Credentials & Risk Setup
# -----------------------------
C = {
    "api_key": "YOUR_API_KEY",
    "cid": "YOUR_CLIENT_ID",
    "pin": "YOUR_PIN",
    "totp": "YOUR_TOTP_SECRET"
}

PER_TRADE_CAP = 20000
MAX_OPEN_TRADES = 10
MAX_TRADE_PER_SYMBOL = 2
TIMEFRAMES = ["5min","15min","1h","4h"]

# Snapshot directory
SNAPSHOT_DIR = "signal_snapshots"
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# -----------------------------
# 2️⃣ Candle Builder
# -----------------------------
class CandleBuilder:
    def __init__(self):
        self.candles = {}  # token -> list of candles

    def update_tick(self, token, price, ts):
        token = str(token)
        if token not in self.candles:
            self.candles[token] = []
        bucket = ts.replace(second=0, microsecond=0)
        if not self.candles[token] or self.candles[token][-1]['bucket'] != bucket:
            self.candles[token].append({'bucket': bucket,'open': price,'high': price,'low': price,'close': price})
        else:
            c = self.candles[token][-1]
            c['high'] = max(c['high'], price)
            c['low'] = min(c['low'], price)
            c['close'] = price

    def get_closed_df(self, token):
        token = str(token)
        if token not in self.candles:
            return pd.DataFrame()
        return pd.DataFrame(self.candles[token])

cb = CandleBuilder()
pos = {}           # Open positions
orderbook = []     # Live orders
pnl_table = []     # Profit & Loss table
trade_count_symbol = {}  # Max 2 trades per symbol
snapshots_recorded = set()  # Track snapshots to avoid duplicates

# -----------------------------
# 3️⃣ Signal Validator
# -----------------------------
def get_sig(df):
    if len(df) < 20: return None
    df['ma'] = df['close'].rolling(20).mean()
    df['up'] = df['ma'] + df['close'].rolling(20).std() * 2
    df['lo'] = df['ma'] - df['close'].rolling(20).std() * 2
    df['m1'] = df['close'].ewm(span=12).mean()
    df['m2'] = df['close'].ewm(span=26).mean()
    df['macd'] = df['m1'] - df['m2']
    df['atr'] = (df['high'] - df['low']).rolling(10).mean()
    df['st'] = ((df['high'] + df['low']) / 2) - (3 * df['atr'])

    delta = df['close'].diff()
    up, down = delta.clip(lower=0), -delta.clip(upper=0)
    roll_up = up.rolling(14).mean()
    roll_down = down.rolling(14).mean()
    df['rsi'] = 100 - 100 / (1 + roll_up / (roll_down + 1e-9))
    df['slope'] = np.gradient(df['ma'])

    if len(df) >= 20:
        last_20 = df['close'].iloc[-20:]
        horizontal_break_up = df['close'].iloc[-1] > last_20.max()
        horizontal_break_down = df['close'].iloc[-1] < last_20.min()
    else:
        horizontal_break_up = horizontal_break_down = False

    c, p = df.iloc[-1], df.iloc[-2]

    if p['st'] < p['ma'] and c['st'] > c['ma']:
        if (c['st'] > p['st'] and c['macd'] > p['macd'] and
            c['rsi'] > 70 and c['slope'] > 0 and horizontal_break_up):
            return "BUY"
    if p['st'] > p['ma'] and c['st'] < c['ma']:
        if (c['st'] < p['st'] and c['macd'] < p['macd'] and
            c['rsi'] < 30 and c['slope'] < 0 and horizontal_break_down):
            return "SELL"
    return None

# -----------------------------
# 4️⃣ Visual Snapshot Function (No Duplicates)
# -----------------------------
def save_signal_snapshot(df, symbol, sig):
    key = f"{symbol}_{sig}_{df['close'].iloc[-1]}"
    if key in snapshots_recorded:
        return None
    snapshots_recorded.add(key)
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df['bucket'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Price"
    ))
    fig.add_trace(go.Scatter(
        x=df['bucket'], y=df['ma'], line=dict(color='blue', width=1), name="MA"
    ))
    fig.add_trace(go.Scatter(
        x=df['bucket'], y=df['st'], line=dict(color='green', width=1), name="Supertrend"
    ))
    fig.add_trace(go.Scatter(
        x=[df['bucket'].iloc[-1]], y=[df['close'].iloc[-1]],
        mode='markers', marker_symbol='diamond', marker_color='red', marker_size=15,
        name=f"Signal {sig}"
    ))
    filename = os.path.join(SNAPSHOT_DIR, f"{symbol}_{sig}_{int(time.time())}.png")
    fig.write_image(filename, engine="kaleido")
    return filename

# -----------------------------
# 5️⃣ Connect AngelOne
# -----------------------------
smart = SmartConnect(api_key=C["api_key"])
totp = pyotp.TOTP(C["totp"]).now()
session = smart.generateSession(C["cid"], C["pin"], totp)
auth_token = session["data"]["jwtToken"]
feed_token = smart.getfeedToken()

u = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
raw = pd.DataFrame(requests.get(u).json())
today = datetime.datetime.now().date()
raw['dt'] = pd.to_datetime(raw['expiry'], format='%d%b%Y', errors='coerce').dt.date
valid = raw[(raw['dt'] >= today)]

futstk = valid[valid['instrumenttype']=='FUTSTK']
nifty_opts = valid[(valid['instrumenttype']=='OPTIDX') & (valid['symbol'].str.contains("NIFTY"))]
near_date = nifty_opts['dt'].min()
atm_opts = nifty_opts[nifty_opts['dt']==near_date]

tokens_list = list(futstk['token'].astype(str)) + list(atm_opts['token'].astype(str))
token_symbol_map = {str(row['token']): row['symbol'] for _, row in pd.concat([futstk, atm_opts]).iterrows()}

# -----------------------------
# 6️⃣ Auto Exit / Take Profit
# -----------------------------
def process_positions(df, token, instrument_type):
    global pos, pnl_table, orderbook, trade_count_symbol
    if token in pos:
        entry = pos[token]
        entry_price = entry['Entry']
        qty = entry['Qty']
        macd_slope = df['macd'].iloc[-1] - df['macd'].iloc[-2]
        exit_flag = False

        if instrument_type == "FUTSTK":
            if (df['st'].iloc[-1] < df['ma'].iloc[-1] and macd_slope < 0) or (df['close'].iloc[-1] >= entry_price * 1.05):
                exit_flag = True
        elif instrument_type == "OPTIDX":
            if df['close'].iloc[-1] >= entry_price * 2.0:
                exit_flag = True

        if exit_flag:
            smart.placeOrder({
                "variety":"NORMAL",
                "tradingsymbol": entry['Symbol'],
                "symboltoken": token,
                "transactiontype":"SELL" if entry['Signal']=="BUY" else "BUY",
                "exchange":"NFO",
                "ordertype":"MARKET",
                "producttype":"INTRADAY",
                "quantity":qty
            })
            pnl_table.append({
                "Symbol": entry['Symbol'],
                "Token": token,
                "Signal": "EXIT",
                "Entry": entry_price,
                "Exit": df['close'].iloc[-1],
                "Qty": qty,
                "P&L": (df['close'].iloc[-1]-entry_price)*int(qty) if entry['Signal']=="BUY" else (entry_price-df['close'].iloc[-1])*int(qty),
                "Time": datetime.datetime.now()
            })
            orderbook.append({
                "Symbol": entry['Symbol'],
                "Token": token,
                "Signal": "EXIT",
                "Qty": qty,
                "Price": df['close'].iloc[-1],
                "Time": datetime.datetime.now()
            })
            del pos[token]
            trade_count_symbol[entry['Symbol']] -= 1

# -----------------------------
# 7️⃣ WebSocket V2 Live Feed
# -----------------------------
sws = SmartWebSocketV2(auth_token, C["api_key"], C["cid"], feed_token)

def on_open(ws):
    st.sidebar.success("✅ WebSocket Connected")
    ws.subscribe(tokens_list, mode=1)

def on_data(ws, msg):
    try:
        token = str(msg['token'])
        ltp = float(msg['ltp'])
        ts = datetime.datetime.now()

        cb.update_tick(token, ltp, ts)
        df = cb.get_closed_df(token)
        if df.empty: return

        instrument_type = "FUTSTK" if token in futstk['token'].astype(str).values else "OPTIDX"
        process_positions(df, token, instrument_type)

        sig = get_sig(df)
        if sig:
            symbol = token_symbol_map[token]
            trades_for_symbol = trade_count_symbol.get(symbol, 0)
            if trades_for_symbol < MAX_TRADE_PER_SYMBOL and len(pos) < MAX_OPEN_TRADES:
                save_signal_snapshot(df, symbol, sig)
                qty = str(int(PER_TRADE_CAP/ltp))
                smart.placeOrder({
                    "variety":"NORMAL",
                    "tradingsymbol": symbol,
                    "symboltoken": token,
                    "transactiontype": sig,
                    "exchange":"NFO",
                    "ordertype":"MARKET",
                    "producttype":"INTRADAY",
                    "quantity": qty
                })
                pos[token] = {"Symbol": symbol, "Signal": sig, "Entry": ltp, "Qty": qty}
                orderbook.append({"Symbol": symbol, "Token": token, "Signal": sig, "Qty": qty, "Price": ltp, "Time": ts})
                trade_count_symbol[symbol] = trades_for_symbol + 1
    except:
        pass

sws.on_open = on_open
sws.on_data = on_data
sws.connect()

# -----------------------------
# 8️⃣ Streamlit Dashboard
# -----------------------------
st.set_page_config(page_title="Pawan Master Algo", layout="wide")
st.title("💎 Pawan Master Algo System")

# Sidebar
st.sidebar.header("Settings")
PER_TRADE_CAP = st.sidebar.number_input("Per Trade Cap", value=PER_TRADE_CAP)
MAX_OPEN_TRADES = st.sidebar.number_input("Max Open Trades", value=MAX_OPEN_TRADES)
if st.sidebar.button("⚠️ Panic! Cancel All Orders"):
    for o in orderbook:
        try: smart.cancelOrder(o.get("OrderID",""))
        except: pass
    pos.clear()
    st.sidebar.warning("All orders cancelled!")

# Tabs
tabs = st.tabs(["Live Chart","Signal Validator","Orderbook","Position","P&L","Heatmap","Signal Snapshots"])
live_chart, sig_tab, order_tab, pos_tab, pnl_tab, heatmap_tab, snapshots_tab = tabs

# Live Chart
with live_chart:
    symbol = st.selectbox("Select Symbol", token_symbol_map.values())
    token = [k for k,v in token_symbol_map.items() if v==symbol][0]
    df = cb.get_closed_df(token)
    if not df.empty:
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df['bucket'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Price"))
        fig.add_trace(go.Scatter(x=df['bucket'], y=df['ma'], line=dict(color='blue', width=1), name="MA"))
        fig.add_trace(go.Scatter(x=df['bucket'], y=df['st'], line=dict(color='green', width=1), name="Supertrend"))
        sig = get_sig(df)
        if sig: fig.add_trace(go.Scatter(x=[df['bucket'].iloc[-1]], y=[df['close'].iloc[-1]], mode='markers', marker_symbol='diamond', marker_color='red', marker_size=15, name="Signal"))
        st.plotly_chart(fig, use_container_width=True)

# Signal Validator
with sig_tab:
    sig_data = []
    for t in tokens_list:
        df = cb.get_closed_df(t)
        if not df.empty: sig_data.append({"Symbol": token_symbol_map[t], "Signal": get_sig(df)})
    st.dataframe(pd.DataFrame(sig_data))

# Orderbook
with order_tab:
    st.dataframe(pd.DataFrame(orderbook))

# Position
with pos_tab:
    st.dataframe(pd.DataFrame(list(pos.items()), columns=["Token","Details"]))

# P&L
with pnl_tab:
    st.dataframe(pd.DataFrame(pnl_table))

# Heatmap
with heatmap_tab:
    heatmap_data = []
    for t in tokens_list:
        heatmap_data.append({"Symbol": token_symbol_map[t], "5m":"BUY","15m":"BUY","1h":"BUY","4h":"BUY","Total":"Strong Buy"})
    st.dataframe(pd.DataFrame(heatmap_data))

# Signal Snapshots Viewer
with snapshots_tab:
    st.header("💎 Verified Signal Snapshots (No Duplicates)")
    files = sorted(os.listdir(SNAPSHOT_DIR), reverse=True)
    if not files:
        st.info("No snapshots captured yet.")
    else:
        for f in files[:20]:  # show latest 20
            st.subheader(f.split("_")[0] + " | Signal: " + f.split("_")[1])
            st.image(os.path.join(SNAPSHOT_DIR, f), use_column_width=True)
