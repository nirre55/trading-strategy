import time
from dataclass.trading_config import TradingConfig
from exchange.binance_manager import BinanceHedgeTrader
from indicator.atr_manager import calculate_atr_simple

def get_atr(binance_trader):
    df = binance_trader.get_binance_data(TradingConfig.SYMBOL, TradingConfig.TIMEFRAME, limit=100)
    basic_atr = calculate_atr_simple(df, TradingConfig.ATR_PERIOD)
    if basic_atr is None:
        raise ValueError("ATR calculation returned None. Check input data and parameters.")

    current_price, current_atr, atr_percent = basic_atr
    print(f"\n🎯 ATR DE BASE:")
    print(f"   Prix actuel: {current_price:,.2f} USDT")
    print(f"   ATR ({TradingConfig.ATR_PERIOD}): {current_atr:.2f} USDT")
    print(f"   ATR %: {atr_percent:.2f}%")
    return round(current_atr, 2)

def update_take_profil(binance_trader, quantity, order_id, price, side, current_position_side):
    result = binance_trader.cancel_order(TradingConfig.SYMBOL, order_id)
    if result:
        print(f"✅ Ordre {order_id} annulé avec succès!")
        new_order = binance_trader.place_limit_order(TradingConfig.SYMBOL, side, quantity, price, position_side=current_position_side, reduce_only=True)
        return new_order['orderId']
    else:
        print(f"⚠️ Échec de l'annulation de l'ordre {order_id}")
        return None


quantity_add_per_trade = 0.002  # Quantité ajoutée par trade

# Test de connexion à Binance Futures Testnet
binance_trader = BinanceHedgeTrader(testnet=True, 
  symbol=TradingConfig.SYMBOL,
  leverage=TradingConfig.LEVERAGE, 
  margin_type="CROSSED", 
  hedge_mode=True)


current_price = binance_trader.get_current_price(TradingConfig.SYMBOL)
if current_price is None:
    raise ValueError(f"Could not fetch current price for symbol {TradingConfig.SYMBOL}")
quantity = (TradingConfig.POSITION_SIZE_USDT * TradingConfig.LEVERAGE) / current_price
print(f"Placing orders with quantity: {quantity} for symbol {TradingConfig.SYMBOL}")


long_price = current_price * (1 - TradingConfig.OFFSET_INIT_PCT)
short_price = current_price * (1 + TradingConfig.OFFSET_INIT_PCT)

long_order = binance_trader.place_limit_order(TradingConfig.SYMBOL, "BUY", quantity, long_price, position_side="LONG", reduce_only=False)
short_order = binance_trader.place_limit_order(TradingConfig.SYMBOL, "SELL", quantity, short_price, position_side="SHORT", reduce_only=False)

# Stockage des IDs des ordres
long_order_id = long_order['orderId']
short_order_id = short_order['orderId']

is_any_order_executed = False

long_status = "NEW"
short_status = "NEW"

print(f"\n✅ Ordres placés avec succès:")
print(f"   LONG Order ID: {long_order_id}")
print(f"   SHORT Order ID: {short_order_id}")

print(f"\n👀 Surveillance des ordres (vérification toutes les {TradingConfig.CHECK_INTERVAL}s)...")

while not is_any_order_executed:
  # Vérification du statut de l'ordre LONG
  long_status = binance_trader.get_simple_order_status(TradingConfig.SYMBOL, long_order_id)
  #print(f"   LONG Status: {long_status}")

  # Vérification du statut de l'ordre SHORT
  short_status = binance_trader.get_simple_order_status(TradingConfig.SYMBOL, short_order_id)
  #print(f"   SHORT Status: {short_status}")

  # Vérification si l'ordre LONG a été exécuté
  if long_status == "FILLED":
      print(f"\n🎯 Ordre LONG exécuté! Annulation de l'ordre SHORT...")
      result = binance_trader.cancel_order(TradingConfig.SYMBOL, short_order_id)
      if result:
          print("✅ Ordre SHORT annulé avec succès!")
          print("📊 Stratégie terminée - Position LONG ouverte")
      else:
          print("⚠️ Échec de l'annulation de l'ordre SHORT")
      is_any_order_executed = True

  # Vérification si l'ordre SHORT a été exécuté
  elif short_status == "FILLED":
      print(f"\n🎯 Ordre SHORT exécuté! Annulation de l'ordre LONG...")
      result = binance_trader.cancel_order(TradingConfig.SYMBOL, long_order_id)
      if result:
          print("✅ Ordre LONG annulé avec succès!")
          print("📊 Stratégie terminée - Position SHORT ouverte")
      else:
          print("⚠️ Échec de l'annulation de l'ordre LONG")
      is_any_order_executed = True

  # Attente avant la prochaine vérification
  time.sleep(TradingConfig.CHECK_INTERVAL)

current_atr = get_atr(binance_trader) / 10

new_short_price = long_price - round(current_atr, 2)
new_long_price = short_price + round(current_atr, 2)
short_order_stop_limit = None
short_order_stop_limit_status = None
long_order_stop_limit = None
long_order_stop_limit_status = None

take_profit_long_order_stop_limit = None
take_profit_short_order_stop_limit = None
take_profit_long_order_stop_limit_status = None
take_profit_short_order_stop_limit_status = None

take_profit_long = new_long_price + (current_atr * TradingConfig.TP_ATR_MULTIPLIER)
take_profit_short = new_short_price - (current_atr * TradingConfig.TP_ATR_MULTIPLIER)

if long_status == "FILLED":
    new_long_price = long_price
    take_profit_long = long_price + (current_atr * TradingConfig.TP_ATR_MULTIPLIER)
if short_status == "FILLED":
    new_short_price = short_price
    take_profit_short = short_price - (current_atr * TradingConfig.TP_ATR_MULTIPLIER)

quantity_tp_long = quantity
quantity_tp_short = quantity

count = 1
while True:
  if long_status == "FILLED":     
      short_order_stop_limit = binance_trader.place_stop_limit_order(TradingConfig.SYMBOL, "SELL",
                                                                      quantity_add_per_trade, new_short_price,
                                                                        new_short_price * (1 - TradingConfig.STOP_LIMIT_OFFSET_MULTIPLIER),
                                                                          position_side="SHORT", reduce_only=False)
      long_status = "NEW"  # Réinitialiser le statut pour la prochaine itération
      take_profit_long_order_stop_limit = update_take_profil(binance_trader, quantity_tp_long,
                                                              take_profit_long_order_stop_limit, take_profit_long,
                                                                  "SELL", "LONG")

  if short_status == "FILLED":
      long_order_stop_limit = binance_trader.place_stop_limit_order(TradingConfig.SYMBOL, "BUY", quantity_add_per_trade, new_long_price, new_long_price * (1 - TradingConfig.STOP_LIMIT_OFFSET_MULTIPLIER), position_side="LONG", reduce_only=False)
      short_status = "NEW"  # Réinitialiser le statut pour la prochaine itération
      take_profit_short_order_stop_limit = update_take_profil(binance_trader, quantity_tp_short,
                                                              take_profit_short_order_stop_limit, take_profit_short,
                                                                  "BUY", "SHORT")

  if take_profit_long_order_stop_limit is not None:
      take_profit_long_order_stop_limit_status = binance_trader.get_simple_order_status(TradingConfig.SYMBOL, take_profit_long_order_stop_limit)
  if take_profit_short_order_stop_limit is not None:
      take_profit_short_order_stop_limit_status = binance_trader.get_simple_order_status(TradingConfig.SYMBOL, take_profit_short_order_stop_limit)

  if long_order_stop_limit is not None:
      long_order_id_stop_limit = long_order_stop_limit['orderId']
      long_order_stop_limit_status = binance_trader.get_simple_order_status(TradingConfig.SYMBOL, long_order_id_stop_limit)

  if short_order_stop_limit is not None:
      short_order_id_stop_limit = short_order_stop_limit['orderId']
      short_order_stop_limit_status = binance_trader.get_simple_order_status(TradingConfig.SYMBOL, short_order_id_stop_limit)



  if long_order_stop_limit is not None and long_order_stop_limit_status == "FILLED":
      print(f"🎯 Ordre STOP-LIMIT LONG exécuté! Position LONG {count} ouverte.\n")
      long_status = "FILLED"  # Réinitialiser le statut pour la prochaine itération
      count += 1
      long_order_stop_limit = None
      long_order_stop_limit_status = None

  if short_order_stop_limit is not None and short_order_stop_limit_status == "FILLED":
      print(f"🎯 Ordre STOP-LIMIT SHORT exécuté! Position SHORT {count} ouverte.\n")
      short_status = "FILLED"  # Réinitialiser le statut pour la prochaine itération
      count += 1
      short_order_stop_limit = None
      short_order_stop_limit_status = None

  if take_profit_long_order_stop_limit is not None and take_profit_long_order_stop_limit_status == "FILLED":
        print(f"🎯 Ordre TAKE PROFIT LONG exécuté! Position LONG {count} fermée.\n")
        take_profit_long_order_stop_limit = None
        take_profit_long_order_stop_limit_status = None

  if take_profit_short_order_stop_limit is not None and take_profit_short_order_stop_limit_status == "FILLED":
      print(f"🎯 Ordre TAKE PROFIT SHORT exécuté! Position SHORT {count} fermée.\n")
      take_profit_short_order_stop_limit = None
      take_profit_short_order_stop_limit_status = None

  time.sleep(TradingConfig.CHECK_INTERVAL)




