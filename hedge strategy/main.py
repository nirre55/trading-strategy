# === 📦 IMPORTATIONS ===
import time
from datetime import datetime
from dataclass.trading_config import TradingConfig
from exchange.binance_manager import BinanceHedgeTrader
from indicator.atr_manager import calculate_atr_simple


# === 🔧 INITIALISATION DU TRADER ===
def initialize_trader():
    return BinanceHedgeTrader(
        testnet=False,
        symbol=TradingConfig.SYMBOL,
        leverage=TradingConfig.LEVERAGE,
        margin_type="CROSSED",
        hedge_mode=True
    )


# === 📈 CALCUL DE L'ATR ===
def get_current_atr(trader):
    df = trader.get_binance_data(TradingConfig.SYMBOL, TradingConfig.TIMEFRAME, limit=100)
    atr_data = calculate_atr_simple(df, TradingConfig.ATR_PERIOD)
    if atr_data is None:
        raise ValueError("ATR invalide")
    current_price, atr_value, atr_pct = atr_data
    print(f"[ATR] Prix actuel: {current_price:.2f}, ATR: {atr_value:.2f} ({atr_pct:.2f}%)")
    print(f"[ATR] TP LONG ({current_price + (atr_value*2):.2f}$)")
    print(f"[ATR] TP SHORT ({current_price - (atr_value*2):.2f}$)")
    return current_price, round(atr_value, 2)


# === 🛒 PLACEMENT DES ORDRES INITIAUX ===
def place_initial_orders(trader, quantity, price):
    long_price = price * (1 - TradingConfig.OFFSET_INIT_PCT)
    short_price = price * (1 + TradingConfig.OFFSET_INIT_PCT)
    long_order = trader.place_limit_order(TradingConfig.SYMBOL, "BUY", quantity, long_price, position_side="LONG")
    short_order = trader.place_limit_order(TradingConfig.SYMBOL, "SELL", quantity, short_price, position_side="SHORT")
    return long_order, short_order, long_price, short_price


# === 📡 SURVEILLANCE DES ORDRES INITIAUX ===
def wait_for_fill(trader, long_order, short_order):
    print(f"[🔍] Attente exécution initiale...")
    while True:
        long_status = trader.get_simple_order_status(TradingConfig.SYMBOL, long_order["orderId"])
        short_status = trader.get_simple_order_status(TradingConfig.SYMBOL, short_order["orderId"])

        if long_status == "FILLED":
            trader.cancel_order(TradingConfig.SYMBOL, short_order["orderId"])
            print(f"[✅] LONG exécuté @ {long_order['price']}")
            return "LONG", float(long_order["price"])

        elif short_status == "FILLED":
            trader.cancel_order(TradingConfig.SYMBOL, long_order["orderId"])
            print(f"[✅] SHORT exécuté @ {short_order['price']}")
            return "SHORT", float(short_order["price"])

        time.sleep(TradingConfig.CHECK_INTERVAL)


# === 🎯 GESTION DU TAKE PROFIT ===
def update_take_profit(trader, old_order_id, total_qty, tp_price, side, stop_price):
    if old_order_id:
        trader.cancel_order(TradingConfig.SYMBOL, old_order_id)
    order = trader.create_take_profit_limit(
        TradingConfig.SYMBOL, side, tp_price, stop_price, total_qty)
    return order["orderId"]

# === 🔁 STRATÉGIE DE RENFORCEMENT CROISÉ ===
def run_strategy(trader, initial_side, initial_price, atr):
    initial_qty = round((TradingConfig.POSITION_SIZE_USDT * TradingConfig.LEVERAGE) / initial_price, 3)
    step_qty = 0.006
    step = atr

    side_quantities = {
        "LONG": initial_qty if initial_side == "LONG" else 0.0,
        "SHORT": initial_qty if initial_side == "SHORT" else 0.0
    }

    direction = initial_side
    last_price = initial_price
    count = 1

    while True:
        qty = step_qty
        side_quantities[direction] += qty

        if direction == "LONG":
            entry_price = last_price - step
            order = trader.place_stop_market_order(
                TradingConfig.SYMBOL, "SELL", qty, entry_price, position_side="SHORT"
            )
            next_direction = "SHORT"
        else:
            entry_price = last_price + step
            order = trader.place_stop_market_order(
                TradingConfig.SYMBOL, "BUY", qty, entry_price, position_side="LONG"
            )
            next_direction = "LONG"
        while True:
            order_status = trader.get_simple_order_status(TradingConfig.SYMBOL, order["orderId"])
            if order_status == "FILLED":
                print(f"[🟢] {next_direction} #{count} exécuté @ {entry_price}")
                direction = next_direction
                last_price = entry_price
                break
            time.sleep(TradingConfig.CHECK_INTERVAL)

        count += 1


# === 🚀 MAIN ===
def main():
    trader = initialize_trader()
    current_price = trader.get_current_price(TradingConfig.SYMBOL)
    if current_price is None:
        raise ValueError("Le prix actuel est None, impossible de calculer la quantité.")
    quantity = 0.003

    long_order, short_order, long_price, short_price = place_initial_orders(trader, quantity, current_price)
    initial_side, initial_price = wait_for_fill(trader, long_order, short_order)

    _, atr = get_current_atr(trader)
    run_strategy(trader, initial_side, initial_price, atr)


if __name__ == "__main__":
    print(f"=== 🧠 STRATÉGIE BREAKOUT HEDGE ALTERNÉE === {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    main()
