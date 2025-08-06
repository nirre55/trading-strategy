"""
Module d'exécution des trades avec gestion des ordres
"""
import os
import time
import threading
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException
import config
from position_manager import PositionManager, load_api_credentials_from_env

class TradeExecutor:
    def __init__(self):
        """Initialise l'exécuteur de trades"""
        try:
            # Chargement des clés API
            api_key = load_api_credentials_from_env("BINANCE_API_KEY")
            api_secret = load_api_credentials_from_env("BINANCE_API_SECRET")
            
            # Client Binance Futures
            self.client = Client(api_key, api_secret)
            self.client.API_URL = 'https://fapi.binance.com'
            
            # Position Manager pour calculs et formatage
            self.position_manager = PositionManager()
            
            # Suivi des ordres actifs
            self.active_trades = {}  # Structure: {trade_id: {entry, sl, tp, side, quantity}}
            self.trade_counter = 0
            
            # Thread pour monitoring des ordres
            self.monitoring_active = False
            self.monitoring_thread = None
            
            print("✅ TradeExecutor initialisé avec succès")
            
        except Exception as e:
            print(f"❌ Erreur initialisation TradeExecutor: {e}")
            raise
    
    def get_current_price(self):
        """Récupère le prix market actuel du symbole"""
        try:
            ticker = self.client.futures_symbol_ticker(symbol=config.ASSET_CONFIG['SYMBOL'])
            price = float(ticker['price'])
            print(f"💰 Prix actuel {config.ASSET_CONFIG['SYMBOL']}: {price}")
            return price
            
        except BinanceAPIException as e:
            print(f"❌ Erreur API récupération prix: {e}")
            return None
        except Exception as e:
            print(f"❌ Erreur récupération prix: {e}")
            return None
    
    def calculate_limit_entry_price(self, side, current_price, spread_percent):
        """
        Calcule le prix d'entrée pour ordre LIMIT
        
        Args:
            side: 'BUY' ou 'SELL'
            current_price: Prix actuel du marché
            spread_percent: Pourcentage de spread à appliquer
            
        Returns:
            Prix formaté pour ordre limit
        """
        try:
            current_price = float(current_price)
            spread_percent = float(spread_percent)
            
            if side == 'BUY':  # LONG
                # Acheter légèrement en dessous du prix actuel
                limit_price = current_price - (current_price * spread_percent / 100)
                print(f"📈 LIMIT BUY: {current_price} - {spread_percent}% = {limit_price}")
            else:  # SELL / SHORT
                # Vendre légèrement au dessus du prix actuel
                limit_price = current_price + (current_price * spread_percent / 100)
                print(f"📉 LIMIT SELL: {current_price} + {spread_percent}% = {limit_price}")
            
            return self.position_manager.format_price(limit_price)
            
        except Exception as e:
            print(f"❌ Erreur calcul prix limit: {e}")
            return None
    
    def place_entry_order(self, side, quantity, order_type="MARKET", limit_price=None):
        """
        Place l'ordre d'entrée (MARKET ou LIMIT)
        
        Args:
            side: 'BUY' ou 'SELL'
            quantity: Quantité formatée
            order_type: 'MARKET' ou 'LIMIT'
            limit_price: Prix limit (requis si LIMIT)
            
        Returns:
            dict: {order_id, executed_price, executed_quantity, status}
        """
        try:
            print(f"🚀 Placement ordre {order_type} {side}: {quantity}")
            
            if order_type == 'MARKET':
                order = self.client.futures_create_order(
                    symbol=config.ASSET_CONFIG['SYMBOL'],
                    side=side,
                    type='MARKET',
                    quantity=quantity
                )
                
                # Pour ordre MARKET, récupérer immédiatement les détails
                time.sleep(0.5)  # Petit délai pour s'assurer que l'ordre est traité
                executed_price, executed_quantity = self._get_executed_order_details(order['orderId'])
                
                return {
                    'order_id': order['orderId'],
                    'executed_price': executed_price,
                    'executed_quantity': executed_quantity,
                    'status': 'FILLED'
                }
                
            elif order_type == 'LIMIT':
                if not limit_price:
                    raise ValueError("Prix limit requis pour ordre LIMIT")
                
                order = self.client.futures_create_order(
                    symbol=config.ASSET_CONFIG['SYMBOL'],
                    side=side,
                    type='LIMIT',
                    timeInForce='GTC',  # Good Till Cancelled
                    quantity=quantity,
                    price=str(limit_price)
                )
                
                return {
                    'order_id': order['orderId'],
                    'executed_price': None,  # Sera rempli après exécution
                    'executed_quantity': None,
                    'status': 'PENDING'
                }
            
            else:
                raise ValueError(f"Type d'ordre non supporté: {order_type}")
                
        except BinanceAPIException as e:
            print(f"❌ Erreur API placement ordre: {e}")
            return None
        except Exception as e:
            print(f"❌ Erreur placement ordre: {e}")
            return None
    
    def wait_for_order_execution(self, order_id, timeout=30):
        """
        Attend l'exécution d'un ordre et récupère les détails
        
        Args:
            order_id: ID de l'ordre à surveiller
            timeout: Timeout en secondes
            
        Returns:
            dict: {executed_price, executed_quantity, status}
        """
        try:
            print(f"⏳ Attente exécution ordre {order_id} (timeout: {timeout}s)")
            
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                order_status = self.client.futures_get_order(
                    symbol=config.ASSET_CONFIG['SYMBOL'],
                    orderId=order_id
                )
                
                if order_status['status'] == 'FILLED':
                    executed_price = float(order_status['avgPrice'])
                    executed_quantity = float(order_status['executedQty'])
                    
                    print(f"✅ Ordre {order_id} exécuté:")
                    print(f"   Prix: {executed_price}")
                    print(f"   Quantité: {executed_quantity}")
                    
                    return {
                        'executed_price': executed_price,
                        'executed_quantity': executed_quantity,
                        'status': 'FILLED'
                    }
                
                elif order_status['status'] in ['CANCELED', 'REJECTED', 'EXPIRED']:
                    print(f"❌ Ordre {order_id} échoué: {order_status['status']}")
                    return {
                        'executed_price': None,
                        'executed_quantity': None,
                        'status': order_status['status']
                    }
                
                time.sleep(1)  # Vérifier chaque seconde
            
            # Timeout atteint
            print(f"⏰ Timeout atteint pour ordre {order_id}")
            
            # Annuler l'ordre en cas de timeout
            try:
                self.client.futures_cancel_order(
                    symbol=config.ASSET_CONFIG['SYMBOL'],
                    orderId=order_id
                )
                print(f"🚫 Ordre {order_id} annulé (timeout)")
            except:
                pass  # Ignore si déjà exécuté
            
            return {
                'executed_price': None,
                'executed_quantity': None,
                'status': 'TIMEOUT'
            }
            
        except BinanceAPIException as e:
            print(f"❌ Erreur API attente exécution: {e}")
            return None
        except Exception as e:
            print(f"❌ Erreur attente exécution: {e}")
            return None
    
    def _get_executed_order_details(self, order_id):
        """Récupère les détails d'un ordre exécuté"""
        try:
            order_details = self.client.futures_get_order(
                symbol=config.ASSET_CONFIG['SYMBOL'],
                orderId=order_id
            )
            
            executed_price = float(order_details['avgPrice'])
            executed_quantity = float(order_details['executedQty'])
            
            return executed_price, executed_quantity
            
        except Exception as e:
            print(f"⚠️ Erreur récupération détails ordre: {e}")
            return None, None
    
    def place_stop_loss_order(self, side, quantity, stop_price, trade_id):
        """
        Place un ordre Stop Loss (STOP_MARKET)
        
        Args:
            side: 'BUY' ou 'SELL' (opposé à la position)
            quantity: Quantité à fermer
            stop_price: Prix de déclenchement du stop
            trade_id: ID du trade pour suivi
            
        Returns:
            Order ID ou None
        """
        try:
            print(f"🛡️ Placement Stop Loss: {side} {quantity} @ {stop_price}")
            
            order = self.client.futures_create_order(
                symbol=config.ASSET_CONFIG['SYMBOL'],
                side=side,
                type='STOP_MARKET',
                quantity=quantity,
                stopPrice=str(stop_price)
            )
            
            order_id = order['orderId']
            print(f"✅ Stop Loss placé: {order_id}")
            
            # Enregistrer dans les trades actifs
            if trade_id in self.active_trades:
                self.active_trades[trade_id]['stop_loss_order_id'] = order_id
            
            return order_id
            
        except BinanceAPIException as e:
            print(f"❌ Erreur API placement Stop Loss: {e}")
            return None
        except Exception as e:
            print(f"❌ Erreur placement Stop Loss: {e}")
            return None
    
    def place_take_profit_order(self, side, quantity, limit_price, trade_id):
        """
        Place un ordre Take Profit (LIMIT)
        
        Args:
            side: 'BUY' ou 'SELL' (opposé à la position)
            quantity: Quantité à fermer
            limit_price: Prix limite de profit
            trade_id: ID du trade pour suivi
            
        Returns:
            Order ID ou None
        """
        try:
            print(f"🎯 Placement Take Profit: {side} {quantity} @ {limit_price}")
            
            order = self.client.futures_create_order(
                symbol=config.ASSET_CONFIG['SYMBOL'],
                side=side,
                type='LIMIT',
                timeInForce='GTC',
                quantity=quantity,
                price=str(limit_price)
            )
            
            order_id = order['orderId']
            print(f"✅ Take Profit placé: {order_id}")
            
            # Enregistrer dans les trades actifs
            if trade_id in self.active_trades:
                self.active_trades[trade_id]['take_profit_order_id'] = order_id
            
            return order_id
            
        except BinanceAPIException as e:
            print(f"❌ Erreur API placement Take Profit: {e}")
            return None
        except Exception as e:
            print(f"❌ Erreur placement Take Profit: {e}")
            return None
    
    def cancel_order(self, order_id):
        """Annule un ordre spécifique"""
        try:
            self.client.futures_cancel_order(
                symbol=config.ASSET_CONFIG['SYMBOL'],
                orderId=order_id
            )
            print(f"🚫 Ordre {order_id} annulé")
            return True
            
        except BinanceAPIException as e:
            print(f"❌ Erreur API annulation ordre {order_id}: {e}")
            return False
        except Exception as e:
            print(f"❌ Erreur annulation ordre {order_id}: {e}")
            return False
    
    def execute_complete_trade(self, side, candles_data, signal_data=None):
        """
        Exécute un trade complet: entrée + SL + TP
        
        Args:
            side: 'LONG' ou 'SHORT'
            candles_data: Données des bougies pour calcul SL
            signal_data: Données du signal (optionnel)
            
        Returns:
            dict: Résultat du trade ou None si échec
        """
        try:
            print(f"\n🚀 === EXECUTION TRADE {side} ===")
            
            # 1. Validation conditions
            validation = self.position_manager.validate_trade_conditions()
            if not validation['status']:
                print(f"❌ Validation échouée: {validation['message']}")
                return None
            
            # 2. Récupération données de base
            balance = self.position_manager.get_account_balance(config.ASSET_CONFIG['BALANCE_ASSET'])
            current_price = self.get_current_price()
            
            if not current_price:
                print("❌ Impossible de récupérer le prix actuel")
                return None
            
            # 3. Calcul Stop Loss basé sur les bougies
            sl_side = 'SHORT' if side == 'LONG' else 'LONG'  # Côté opposé pour SL
            sl_price = self.position_manager.calculate_stop_loss_price(
                candles_data, 
                side,
                config.TRADING_CONFIG['STOP_LOSS_LOOKBACK_CANDLES'],
                config.TRADING_CONFIG['STOP_LOSS_OFFSET_PERCENT']
            )
            
            if not sl_price:
                print("❌ Impossible de calculer le Stop Loss")
                return None
            
            # 4. Calcul taille de position
            quantity = self.position_manager.calculate_position_size(
                balance,
                config.TRADING_CONFIG['RISK_PERCENT'],
                current_price,
                sl_price
            )
            
            if quantity <= 0:
                print("❌ Taille de position invalide")
                return None
            
            # 5. Préparation ordre d'entrée
            order_type = config.TRADING_CONFIG['ENTRY_ORDER_TYPE']
            entry_side = 'BUY' if side == 'LONG' else 'SELL'
            
            limit_price = None
            if order_type == 'LIMIT':
                limit_price = self.calculate_limit_entry_price(
                    entry_side,
                    current_price,
                    config.TRADING_CONFIG['LIMIT_SPREAD_PERCENT']
                )
            
            # 6. Placement ordre d'entrée
            entry_result = self.place_entry_order(entry_side, quantity, order_type, limit_price)
            
            if not entry_result:
                print("❌ Échec placement ordre d'entrée")
                return None
            
            # 7. Attendre exécution si ordre LIMIT
            if order_type == 'LIMIT' and entry_result['status'] == 'PENDING':
                execution_result = self.wait_for_order_execution(
                    entry_result['order_id'],
                    config.TRADING_CONFIG['ORDER_EXECUTION_TIMEOUT']
                )
                
                if not execution_result or execution_result['status'] != 'FILLED':
                    print("❌ Ordre d'entrée non exécuté dans les temps")
                    return None
                
                # Mettre à jour avec les données d'exécution
                entry_result['executed_price'] = execution_result['executed_price']
                entry_result['executed_quantity'] = execution_result['executed_quantity']
                entry_result['status'] = 'FILLED'
            
            executed_price = entry_result['executed_price']
            executed_quantity = entry_result['executed_quantity']
            
            print(f"✅ Entrée exécutée: {executed_quantity} @ {executed_price}")
            
            # 8. Calcul Take Profit basé sur prix d'exécution réel
            tp_price = self.position_manager.calculate_take_profit_price(
                executed_price,
                side,
                config.TRADING_CONFIG['TAKE_PROFIT_PERCENT']
            )
            
            if not tp_price:
                print("❌ Impossible de calculer le Take Profit")
                # Fermer la position immédiatement
                self._emergency_close_position(entry_side, executed_quantity)
                return None
            
            # 9. Créer un ID unique pour ce trade
            self.trade_counter += 1
            trade_id = f"trade_{self.trade_counter}_{int(time.time())}"
            
            # 10. Enregistrer le trade
            self.active_trades[trade_id] = {
                'side': side,
                'entry_side': entry_side,
                'entry_order_id': entry_result['order_id'],
                'entry_price': executed_price,
                'quantity': executed_quantity,
                'stop_loss_price': sl_price,
                'take_profit_price': tp_price,
                'stop_loss_order_id': None,
                'take_profit_order_id': None,
                'timestamp': datetime.now().isoformat(),
                'signal_data': signal_data
            }
            
            # 11. Placement Stop Loss
            sl_order_side = 'SELL' if side == 'LONG' else 'BUY'  # Opposé à l'entrée
            sl_order_id = self.place_stop_loss_order(
                sl_order_side,
                executed_quantity,
                sl_price,
                trade_id
            )
            
            # 12. Placement Take Profit
            tp_order_side = 'SELL' if side == 'LONG' else 'BUY'  # Opposé à l'entrée
            tp_order_id = self.place_take_profit_order(
                tp_order_side,
                executed_quantity,
                tp_price,
                trade_id
            )
            
            if not sl_order_id or not tp_order_id:
                print("⚠️ Échec placement SL/TP - Position ouverte sans protection!")
                # TODO: Implementer fermeture d'urgence
            
            # 13. Démarrer monitoring si pas déjà actif
            if not self.monitoring_active:
                self.start_order_monitoring()
            
            # 14. Résultat final
            trade_result = {
                'trade_id': trade_id,
                'status': 'ACTIVE',
                'side': side,
                'entry_price': executed_price,
                'quantity': executed_quantity,
                'stop_loss_price': sl_price,
                'take_profit_price': tp_price,
                'risk_amount': abs(executed_price - sl_price) * executed_quantity,
                'potential_profit': abs(tp_price - executed_price) * executed_quantity
            }
            
            print(f"✅ Trade {trade_id} créé avec succès!")
            print(f"   Entrée: {executed_price}")
            print(f"   SL: {sl_price}")
            print(f"   TP: {tp_price}")
            print(f"   Risque: {trade_result['risk_amount']:.2f}")
            print(f"   Profit potentiel: {trade_result['potential_profit']:.2f}")
            
            return trade_result
            
        except Exception as e:
            print(f"❌ Erreur exécution trade: {e}")
            return None
    
    def _emergency_close_position(self, original_side, quantity):
        """Ferme une position en urgence"""
        try:
            emergency_side = 'SELL' if original_side == 'BUY' else 'BUY'
            print(f"🚨 Fermeture d'urgence: {emergency_side} {quantity}")
            
            self.client.futures_create_order(
                symbol=config.ASSET_CONFIG['SYMBOL'],
                side=emergency_side,
                type='MARKET',
                quantity=quantity
            )
            print("✅ Position fermée en urgence")
            
        except Exception as e:
            print(f"❌ Erreur fermeture d'urgence: {e}")
    
    def start_order_monitoring(self):
        """Démarre la surveillance des ordres dans un thread séparé"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self.monitor_orders_and_cleanup,
            daemon=True
        )
        self.monitoring_thread.start()
        print("👁️ Monitoring des ordres démarré")
    
    def monitor_orders_and_cleanup(self):
        """
        Surveille les ordres SL/TP et nettoie automatiquement
        Fonction exécutée dans un thread séparé
        """
        print("👁️ Démarrage monitoring des ordres...")
        
        while self.monitoring_active:
            try:
                # Copie pour éviter modification pendant itération
                trades_to_check = self.active_trades.copy()
                
                for trade_id, trade_info in trades_to_check.items():
                    sl_order_id = trade_info.get('stop_loss_order_id')
                    tp_order_id = trade_info.get('take_profit_order_id')
                    
                    # Vérifier status des ordres
                    sl_executed = False
                    tp_executed = False
                    
                    if sl_order_id:
                        sl_status = self._check_order_status(sl_order_id)
                        if sl_status == 'FILLED':
                            sl_executed = True
                            print(f"🛡️ Stop Loss déclenché pour {trade_id}")
                    
                    if tp_order_id:
                        tp_status = self._check_order_status(tp_order_id)
                        if tp_status == 'FILLED':
                            tp_executed = True
                            print(f"🎯 Take Profit atteint pour {trade_id}")
                    
                    # Nettoyage si un ordre est exécuté
                    if sl_executed or tp_executed:
                        self._cleanup_trade(trade_id, sl_executed, tp_executed)
                
                time.sleep(5)  # Vérifier toutes les 5 secondes
                
            except Exception as e:
                print(f"❌ Erreur monitoring: {e}")
                time.sleep(10)  # Attendre plus longtemps en cas d'erreur
        
        print("👁️ Monitoring des ordres arrêté")
    
    def _check_order_status(self, order_id):
        """Vérifie le status d'un ordre"""
        try:
            order = self.client.futures_get_order(
                symbol=config.ASSET_CONFIG['SYMBOL'],
                orderId=order_id
            )
            return order['status']
            
        except Exception as e:
            print(f"⚠️ Erreur vérification ordre {order_id}: {e}")
            return None
    
    def _cleanup_trade(self, trade_id, sl_executed, tp_executed):
        """Nettoie les ordres après exécution de SL ou TP"""
        try:
            if trade_id not in self.active_trades:
                return
            
            trade_info = self.active_trades[trade_id]
            
            if sl_executed and trade_info.get('take_profit_order_id'):
                # SL déclenché -> annuler TP
                self.cancel_order(trade_info['take_profit_order_id'])
                print(f"🚫 Take Profit annulé pour {trade_id}")
                
            elif tp_executed and trade_info.get('stop_loss_order_id'):
                # TP atteint -> annuler SL
                self.cancel_order(trade_info['stop_loss_order_id'])
                print(f"🚫 Stop Loss annulé pour {trade_id}")
            
            # Marquer le trade comme terminé
            trade_info['status'] = 'CLOSED'
            trade_info['close_reason'] = 'STOP_LOSS' if sl_executed else 'TAKE_PROFIT'
            trade_info['close_timestamp'] = datetime.now().isoformat()
            
            # Retirer des trades actifs
            del self.active_trades[trade_id]
            
            print(f"✅ Trade {trade_id} fermé: {trade_info['close_reason']}")
            
        except Exception as e:
            print(f"❌ Erreur nettoyage trade {trade_id}: {e}")
    
    def get_active_trades(self):
        """Retourne la liste des trades actifs"""
        return self.active_trades.copy()
    
    def stop_monitoring(self):
        """Arrête le monitoring des ordres"""
        self.monitoring_active = False
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)
        print("🛑 Monitoring arrêté")
    
    def close_all_positions(self):
        """Ferme toutes les positions et annule tous les ordres"""
        try:
            print("🚨 Fermeture de toutes les positions...")
            
            # Annuler tous les ordres en attente
            for trade_id, trade_info in self.active_trades.items():
                if trade_info.get('stop_loss_order_id'):
                    self.cancel_order(trade_info['stop_loss_order_id'])
                if trade_info.get('take_profit_order_id'):
                    self.cancel_order(trade_info['take_profit_order_id'])
            
            # Fermer toutes les positions ouvertes
            positions = self.position_manager.get_current_positions()
            for pos in positions:
                close_side = 'SELL' if pos['side'] == 'LONG' else 'BUY'
                self.client.futures_create_order(
                    symbol=config.ASSET_CONFIG['SYMBOL'],
                    side=close_side,
                    type='MARKET',
                    quantity=pos['size']
                )
                print(f"✅ Position {pos['side']} fermée: {pos['size']}")
            
            # Vider les trades actifs
            self.active_trades.clear()
            
            print("✅ Toutes les positions fermées")
            
        except Exception as e:
            print(f"❌ Erreur fermeture positions: {e}")

if __name__ == "__main__":
    # Test du module
    try:
        print("🧪 Test TradeExecutor...")
        
        te = TradeExecutor()
        
        # Test récupération prix
        current_price = te.get_current_price()
        
        # Test calcul prix limit
        if current_price:
            limit_buy = te.calculate_limit_entry_price('BUY', current_price, 0.01)
            limit_sell = te.calculate_limit_entry_price('SELL', current_price, 0.01)
            
            print(f"💰 Prix actuel: {current_price}")
            print(f"📈 Limit BUY: {limit_buy}")
            print(f"📉 Limit SELL: {limit_sell}")
        
        # Test récupération trades actifs
        active_trades = te.get_active_trades()
        print(f"📊 Trades actifs: {len(active_trades)}")
        
        # Test validation positions existantes
        positions = te.position_manager.get_current_positions()
        
        print("✅ Test TradeExecutor terminé avec succès")
        
    except Exception as e:
        print(f"❌ Erreur test TradeExecutor: {e}")