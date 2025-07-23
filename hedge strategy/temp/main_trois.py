from binance.client import Client
from binance.exceptions import BinanceAPIException

class BinanceFuturesTrader:
    def __init__(self, api_key, api_secret):
        self.client = Client(api_key, api_secret, testnet=True)
        self.ensure_hedge_mode()
    
    def ensure_hedge_mode(self):
        """Activer le mode hedge si nécessaire"""
        position_mode = self.client.futures_get_position_mode()
        if not position_mode['dualSidePosition']:
            self.client.futures_change_position_mode(dualSidePosition=True)
    
    def place_hedge_trade_with_tp_sl(self, symbol, side, quantity, tp_price, sl_price):
        """
        Placer un trade avec Take Profit et Stop Loss optimisés pour frais maker
        """
        try:
            # Déterminer positionSide selon le side
            position_side = 'LONG' if side == 'BUY' else 'SHORT'
            
            # 1. Ordre d'entrée
            entry_order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                positionSide=position_side,
                type='MARKET',
                quantity=quantity
            )
            
            print(f"Ordre d'entrée placé: {entry_order['orderId']}")
            
            # 2. Take Profit avec frais maker
            tp_side = 'SELL' if side == 'BUY' else 'BUY'
            tp_order = self.client.futures_create_order(
                symbol=symbol,
                side=tp_side,
                positionSide=position_side,
                type='TAKE_PROFIT',  # ✅ Type correct (pas TAKE_PROFIT_LIMIT)
                quantity=quantity,
                price=tp_price,           # Prix limite pour frais maker
                stopPrice=tp_price * 0.999 if tp_side == 'SELL' else tp_price * 1.001,
                timeInForce='GTX',        # Post Only - garantit frais maker
                workingType='MARK_PRICE',
                priceProtect=True
            )
            
            print(f"Take Profit placé: {tp_order['orderId']}")
            
            # 3. Stop Loss avec frais maker
            sl_side = 'SELL' if side == 'BUY' else 'BUY'
            sl_order = self.client.futures_create_order(
                symbol=symbol,
                side=sl_side,
                positionSide=position_side,
                type='STOP',             # ✅ Type correct (pas STOP_LIMIT)
                quantity=quantity,
                price=sl_price,          # Prix limite pour frais maker
                stopPrice=sl_price * 1.001 if sl_side == 'SELL' else sl_price * 0.999,
                timeInForce='GTX',       # Post Only - garantit frais maker
                workingType='MARK_PRICE',
                priceProtect=True
            )
            
            print(f"Stop Loss placé: {sl_order['orderId']}")
            
            return {
                'entry': entry_order,
                'take_profit': tp_order,
                'stop_loss': sl_order
            }
            
        except BinanceAPIException as e:
            if e.code == -1116:
                print(f"Erreur type d'ordre: {e.message}")
                # Fallback vers ordres market (frais taker)
                return self.place_market_tp_sl_fallback(symbol, side, quantity, tp_price, sl_price)
            else:
                raise e
    
    def place_market_tp_sl_fallback(self, symbol, side, quantity, tp_price, sl_price):
        """
        Fallback avec ordres market si les ordres limite échouent
        """
        position_side = 'LONG' if side == 'BUY' else 'SHORT'
        
        # Ordre d'entrée
        entry_order = self.client.futures_create_order(
            symbol=symbol,
            side=side,
            positionSide=position_side,
            type='MARKET',
            quantity=quantity
        )
        
        # Take Profit market (frais taker)
        tp_side = 'SELL' if side == 'BUY' else 'BUY'
        tp_order = self.client.futures_create_order(
            symbol=symbol,
            side=tp_side,
            positionSide=position_side,
            type='TAKE_PROFIT_MARKET',  # Market order - frais taker
            quantity=quantity,
            stopPrice=tp_price,
            timeInForce='GTC',
            workingType='MARK_PRICE'
        )
        
        # Stop Loss market (frais taker)
        sl_side = 'SELL' if side == 'BUY' else 'BUY'
        sl_order = self.client.futures_create_order(
            symbol=symbol,
            side=sl_side,
            positionSide=position_side,
            type='STOP_MARKET',         # Market order - frais taker
            quantity=quantity,
            stopPrice=sl_price,
            timeInForce='GTC',
            workingType='MARK_PRICE'
        )
        
        return {
            'entry': entry_order,
            'take_profit': tp_order,
            'stop_loss': sl_order
        }

# Exemple d'utilisation
if __name__ == "__main__":
    API_KEY_TESTNET="71c0d61b99b727d02a7399fd9d05aefdeafd3f9c984a51fad08314518fe9ad6b"
    SECRET_KEY_TESTNET="06b6bef900e4f9700039716b08d24ba8306d58c0055019856d9336ac8791d0c6"
    # Initialiser le trader
    trader = BinanceFuturesTrader(api_key=API_KEY_TESTNET, api_secret=SECRET_KEY_TESTNET)
    
    # Placer un trade LONG avec TP/SL optimisé
    orders = trader.place_hedge_trade_with_tp_sl(
        symbol='BTCUSDT',
        side='BUY',
        quantity=0.001,
        tp_price=121000,  # Take profit à 121k
        sl_price=120000   # Stop loss à 45k
    )
    
    print("Trade placé avec succès!")
    print(f"Entrée: {orders['entry']['orderId']}")
    print(f"Take Profit: {orders['take_profit']['orderId']}")
    print(f"Stop Loss: {orders['stop_loss']['orderId']}")