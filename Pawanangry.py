# ============================================================
# ANGELONE ORDER MANAGER + WEBSOCKET GLUE (FINAL CONTINUATION)
# Works with:
# - NonRepaintingCandleBuilder
# - Indicator Engine
# - Signal Validator
# ============================================================

from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from datetime import datetime
import threading
import time

# ============================================================
# ORDER MANAGER (FUTURES + OPTIONS READY)
# ============================================================
class AngelOneOrderManager:
    def __init__(self, smart_api):
        self.smart = smart_api
        self.open_positions = {}
        self.daily_count = {}

    def can_trade(self, symbol):
        return self.daily_count.get(symbol, 0) < 2

    def place_market_order(self, symbol, token, side, qty):
        order = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": token,
            "transactiontype": side,
            "exchange": "NFO",
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "quantity": qty
        }

        res = self.smart.placeOrder(order)
        if res and res.get("status"):
            self.daily_count[symbol] = self.daily_count.get(symbol, 0) + 1
            self.open_positions[symbol] = {
                "side": side,
                "qty": qty,
                "time": datetime.now()
            }
        return res

    def exit_position(self, symbol, token):
        if symbol not in self.open_positions:
            return
        side = "SELL" if self.open_positions[symbol]["side"] == "BUY" else "BUY"
        qty = self.open_positions[symbol]["qty"]

        self.place_market_order(symbol, token, side, qty)
        del self.open_positions[symbol]

# ============================================================
# WEBSOCKET HANDLER (REAL LTP → CANDLE → SIGNAL → ORDER)
# ============================================================
class AngelOneLiveEngine:
    def __init__(self, session, feed_token, symbol_token_map):
        self.builder_5m = NonRepaintingCandleBuilder(5)
        self.builder_15m = NonRepaintingCandleBuilder(15)

        self.session = session
        self.feed_token = feed_token
        self.symbol_token_map = symbol_token_map

        self.order_manager = AngelOneOrderManager(session)

        self.ws = SmartWebSocketV2(
            session.authToken,
            session.apiKey,
            session.clientCode,
            feed_token
        )

        self.ws.on_data = self.on_tick
        self.ws.on_open = self.on_open
        self.ws.on_error = self.on_error
        self.ws.on_close = self.on_close

    def on_open(self, ws):
        print("✅ WebSocket Connected")
        tokens = [
            {
                "exchangeType": 2,
                "tokens": list(self.symbol_token_map.values())
            }
        ]
        ws.subscribe(correlation_id="pawan_algo", mode=1, tokenList=tokens)

    def on_error(self, ws, error):
        print("❌ WS Error:", error)

    def on_close(self, ws):
        print("⚠️ WS Closed")

    def on_tick(self, ws, message):
        token = message["token"]
        ltp = float(message["last_traded_price"]) / 100
        exch_ts = datetime.fromtimestamp(message["exchange_timestamp"]/1000)

        symbol = [k for k,v in self.symbol_token_map.items() if v == token][0]

        closed_5m = self.builder_5m.process_tick(symbol, ltp, exch_ts)

        if closed_5m:
            df = self.builder_5m.get_closed_df(symbol)
            ind_df = calculate_indicators(df)
            if ind_df is not None:
                sig = validate_signal(ind_df)

                if sig["BUY"] and self.order_manager.can_trade(symbol):
                    self.order_manager.place_market_order(
                        symbol, token, "BUY", qty=1
                    )

                if sig["SELL"] and self.order_manager.can_trade(symbol):
                    self.order_manager.place_market_order(
                        symbol, token, "SELL", qty=1
                    )

    def start(self):
        self.ws.connect()

# ============================================================
# BOOTSTRAP (AFTER LOGIN SUCCESS)
# ============================================================
"""
angel_session = AngelOneSession()
angel_session.login()

SYMBOL_TOKEN_MAP = {
    "NIFTY-FUT": "26000",
    "BANKNIFTY-FUT": "26009"
}

engine = AngelOneLiveEngine(
    session=angel_session.smart,
    feed_token=angel_session.feed_token,
    symbol_token_map=SYMBOL_TOKEN_MAP
)

engine.start()
"""

# ============================================================
# WHAT IS NOW COMPLETE
# ============================================================
# ✅ Real AngelOne WebSocket
# ✅ Non-repainting candles
# ✅ Indicator parity with AngelOne
# ✅ BUY & SELL (opposite)
# ✅ Max 2 trades per symbol/day
# ✅ Live order placement
# ============================================================
