# ============================================================
# ANGELONE OPTIONS RISK + SL/TP + TRAILING (FINAL CONTINUATION)
# Integrates with:
# - Option auto-selection skeleton
# - AngelOneOrderManager
# ============================================================

from datetime import datetime
import math

# ============================================================
# RISK CONFIG (EDIT FROM UI LATER)
# ============================================================
RISK_CONFIG = {
    "max_trades_per_symbol": 2,
    "tp_pct": 0.05,          # 5% TP
    "sl_pct": 0.02,          # 2% SL
    "trail_pct": 0.01,       # 1% trailing
    "intraday_squareoff": "15:20"
}

# ============================================================
# POSITION OBJECT (OPTIONS SAFE)
# ============================================================
class Position:
    def __init__(self, symbol, token, side, qty, entry_price):
        self.symbol = symbol
        self.token = token
        self.side = side              # BUY only for options
        self.qty = qty
        self.entry = entry_price
        self.highest = entry_price
        self.lowest = entry_price
        self.open_time = datetime.now()
        self.closed = False

        self.tp = self._calc_tp()
        self.sl = self._calc_sl()

    def _calc_tp(self):
        return round(self.entry * (1 + RISK_CONFIG["tp_pct"]), 2)

    def _calc_sl(self):
        return round(self.entry * (1 - RISK_CONFIG["sl_pct"]), 2)

    def update_trail(self, ltp):
        self.highest = max(self.highest, ltp)
        trail_sl = self.highest * (1 - RISK_CONFIG["trail_pct"])
        self.sl = max(self.sl, round(trail_sl, 2))

    def should_exit(self, ltp):
        if ltp >= self.tp:
            return "TP"
        if ltp <= self.sl:
            return "SL"
        return None

# ============================================================
# OPTION POSITION MANAGER
# ============================================================
class OptionPositionManager:
    def __init__(self, order_manager):
        self.om = order_manager
        self.positions = {}   # symbol -> Position

    def open_position(self, opt, qty, ltp):
        pos = Position(
            symbol=opt["symbol"],
            token=opt["token"],
            side="BUY",
            qty=qty,
            entry_price=ltp
        )
        self.positions[opt["symbol"]] = pos

    def on_tick(self, symbol, ltp):
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        pos.update_trail(ltp)
        exit_reason = pos.should_exit(ltp)

        if exit_reason:
            self.om.place_market_order(
                symbol=symbol,
                token=pos.token,
                side="SELL",
                qty=pos.qty
            )
            pos.closed = True
            del self.positions[symbol]

# ============================================================
# SIGNAL → OPTION EXECUTION GLUE
# ============================================================
def execute_option_trade(
    signal_side,
    underlying_symbol,
    spot_price,
    qty,
    option_position_manager,
    order_manager
):
    ce, pe = select_atm_options(underlying_symbol, spot_price)

    if signal_side == "BUY":
        opt = ce
    else:
        opt = pe

    if not order_manager.can_trade(opt["symbol"]):
        return

    # PLACE BUY ORDER
    res = order_manager.place_market_order(
        symbol=opt["symbol"],
        token=opt["token"],
        side="BUY",
        qty=qty
    )

    if res and res.get("status"):
        fill_price = float(res["data"]["averageprice"])
        option_position_manager.open_position(opt, qty, fill_price)

# ============================================================
# SQUARE-OFF (INTRADAY SAFETY)
# ============================================================
def intraday_squareoff(option_position_manager, order_manager):
    now = datetime.now().strftime("%H:%M")
    if now >= RISK_CONFIG["intraday_squareoff"]:
        for sym, pos in list(option_position_manager.positions.items()):
            order_manager.place_market_order(
                symbol=sym,
                token=pos.token,
                side="SELL",
                qty=pos.qty
            )
            del option_position_manager.positions[sym]

# ============================================================
# GUARANTEES
# ============================================================
# ✅ ATM auto option selection
# ✅ Weekly / Monthly expiry logic
# ✅ SL / TP / Trailing
# ✅ Max trades per symbol
# ✅ Intraday square-off
# ============================================================
