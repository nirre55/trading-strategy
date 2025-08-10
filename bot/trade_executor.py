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
from retry_manager import RetryManager
from trading_logger import trading_logger

# 1. Import du nouveau module (ajouter en haut du fichier)
try:
    from delayed_sltp_manager import DelayedSLTPManager
    DELAYED_SLTP_AVAILABLE = True
    print("✅ DelayedSLTPManager disponible")
except ImportError as e:
    print(f"⚠️ DelayedSLTPManager non disponible: {e}")
    DELAYED_SLTP_AVAILABLE = False

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
            
            # NOUVEAU: Gestionnaire SL/TP retardé
            self.delayed_sltp_manager = None
            if DELAYED_SLTP_AVAILABLE and config.DELAYED_SLTP_CONFIG.get('ENABLED', False):
                try:
                    self.delayed_sltp_manager = DelayedSLTPManager(self, None)
                    print("✅ Gestion SL/TP retardée activée")
                    trading_logger.info("Gestion SL/TP retardée activée")
                except Exception as e:
                    print(f"⚠️ Erreur initialisation SL/TP retardé: {e}")
                    self.delayed_sltp_manager = None
            else:
                print("📊 Gestion SL/TP immédiate (mode classique)")
            
            print("✅ TradeExecutor initialisé avec succès")
            
        except Exception as e:
            print(f"❌ Erreur initialisation TradeExecutor: {e}")
            trading_logger.error_occurred("INIT_TRADE_EXECUTOR", str(e))
            raise
    
    def get_current_price(self):
        """Récupère le prix market actuel du symbole"""
        try:
            # Retry configuré pour récupération de prix
            @RetryManager.with_configured_retry('PRICE')
            def _get_ticker():
                return self.client.futures_symbol_ticker(symbol=config.ASSET_CONFIG['SYMBOL'])

            ticker = _get_ticker()
            price = float(ticker['price'])
            print(f"💰 Prix actuel {config.ASSET_CONFIG['SYMBOL']}: {price}")
            return price
            
        except BinanceAPIException as e:
            print(f"❌ Erreur API récupération prix: {e}")
            trading_logger.error_occurred("GET_PRICE_API", str(e))
            return None
        except Exception as e:
            print(f"❌ Erreur récupération prix: {e}")
            trading_logger.error_occurred("GET_PRICE", str(e))
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
            trading_logger.error_occurred("CALCUL_LIMIT_PRICE", str(e))
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
            trading_logger.error_occurred("PLACE_ENTRY_ORDER_API", str(e))
            return None
        except Exception as e:
            print(f"❌ Erreur placement ordre: {e}")
            trading_logger.error_occurred("PLACE_ENTRY_ORDER", str(e))
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
                # Retry léger sur status order
                @RetryManager.with_configured_retry('ORDER_STATUS')
                def _get_order():
                    return self.client.futures_get_order(
                        symbol=config.ASSET_CONFIG['SYMBOL'],
                        orderId=order_id
                    )
                order_status = _get_order()
                
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
                @RetryManager.with_configured_retry('ORDER_CANCELLATION')
                def _cancel():
                    return self.client.futures_cancel_order(
                        symbol=config.ASSET_CONFIG['SYMBOL'],
                        orderId=order_id
                    )
                _cancel()
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
            trading_logger.error_occurred("WAIT_ORDER_EXEC_API", str(e))
            return None
        except Exception as e:
            print(f"❌ Erreur attente exécution: {e}")
            trading_logger.error_occurred("WAIT_ORDER_EXEC", str(e))
            return None
    
    def execute_market_fallback(self, side, quantity, original_order_type):
        """
        Exécute un ordre MARKET en fallback après échec d'un ordre LIMIT
        
        Args:
            side: 'BUY' ou 'SELL'
            quantity: Quantité à trader
            original_order_type: Type d'ordre original pour les logs
            
        Returns:
            dict: Résultat de l'ordre MARKET ou None si échec
        """
        try:
            print(f"⚡ FALLBACK MARKET: Exécution ordre {side} {quantity} après échec {original_order_type}")
            
            # Vérifier si fallback activé dans config
            if not config.TRADING_CONFIG.get('MARKET_FALLBACK_ENABLED', True):
                print("🚫 Fallback MARKET désactivé dans configuration")
                return None
            
            # Récupérer prix actuel pour validation
            current_price = self.get_current_price()
            if not current_price:
                print("❌ Impossible de récupérer prix actuel pour fallback")
                return None
            
            print(f"📊 Prix actuel pour fallback: {current_price}")
            
            # Placer ordre MARKET
            @RetryManager.with_configured_retry('ORDER_PLACEMENT')
            def _place_market():
                return self.client.futures_create_order(
                    symbol=config.ASSET_CONFIG['SYMBOL'],
                    side=side,
                    type='MARKET',
                    quantity=quantity
                )
            order = _place_market()
            
            order_id = order['orderId']
            print(f"⚡ Ordre MARKET fallback placé: {order_id}")
            
            # Attendre exécution (MARKET généralement instantané)
            time.sleep(0.5)
            executed_price, executed_quantity = self._get_executed_order_details(order_id)
            
            if executed_price and executed_quantity:
                # Calculer slippage par rapport au prix attendu
                slippage = None
                if original_order_type == 'LIMIT':
                    slippage = abs(executed_price - current_price) / current_price * 100
                    print(f"📊 Slippage fallback: {slippage:.3f}%")
                
                # Respecter le seuil de slippage si défini
                max_slippage = config.TRADING_CONFIG.get('FALLBACK_MAX_SLIPPAGE')
                if slippage is not None and max_slippage is not None and slippage > float(max_slippage):
                    print(f"🚫 Slippage {slippage:.3f}% > seuil {max_slippage:.3f}% - annulation du fallback")
                    try:
                        # Fermer immédiatement la position ouverte par erreur
                        self._emergency_close_position('BUY' if side == 'SELL' else 'SELL', executed_quantity)
                    except Exception:
                        pass
                    return None
                
                print(f"✅ Fallback MARKET exécuté avec succès:")
                print(f"   Prix d'exécution: {executed_price}")
                print(f"   Quantité: {executed_quantity}")
                
                return {
                    'order_id': order_id,
                    'executed_price': executed_price,
                    'executed_quantity': executed_quantity,
                    'status': 'FILLED',
                    'is_fallback': True,
                    'original_type': original_order_type
                }
            else:
                print("❌ Échec récupération détails ordre MARKET fallback")
                return None
                
        except BinanceAPIException as e:
            print(f"❌ Erreur API fallback MARKET: {e}")
            trading_logger.error_occurred("FALLBACK_MARKET_API", str(e))
            return None
        except Exception as e:
            print(f"❌ Erreur fallback MARKET: {e}")
            trading_logger.error_occurred("FALLBACK_MARKET", str(e))
            return None
    
    def _get_executed_order_details(self, order_id):
        """Récupère les détails d'un ordre exécuté"""
        try:
            @RetryManager.with_configured_retry('ORDER_STATUS')
            def _get_order_details():
                return self.client.futures_get_order(
                    symbol=config.ASSET_CONFIG['SYMBOL'],
                    orderId=order_id
                )
            order_details = _get_order_details()
            
            executed_price = float(order_details['avgPrice'])
            executed_quantity = float(order_details['executedQty'])
            
            return executed_price, executed_quantity
            
        except Exception as e:
            print(f"⚠️ Erreur récupération détails ordre: {e}")
            trading_logger.error_occurred("GET_ORDER_DETAILS", str(e))
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
            
            @RetryManager.with_configured_retry('ORDER_PLACEMENT')
            def _place_sl():
                return self.client.futures_create_order(
                    symbol=config.ASSET_CONFIG['SYMBOL'],
                    side=side,
                    type='STOP_MARKET',
                    quantity=quantity,
                    stopPrice=str(stop_price)
                )
            order = _place_sl()
            
            order_id = order['orderId']
            print(f"✅ Stop Loss placé: {order_id}")
            
            # Enregistrer dans les trades actifs
            if trade_id in self.active_trades:
                self.active_trades[trade_id]['stop_loss_order_id'] = order_id
            
            return order_id
            
        except BinanceAPIException as e:
            print(f"❌ Erreur API placement Stop Loss: {e}")
            trading_logger.error_occurred("PLACE_SL_API", str(e))
            return None
        except Exception as e:
            print(f"❌ Erreur placement Stop Loss: {e}")
            trading_logger.error_occurred("PLACE_SL", str(e))
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
            
            @RetryManager.with_configured_retry('ORDER_PLACEMENT')
            def _place_tp():
                return self.client.futures_create_order(
                    symbol=config.ASSET_CONFIG['SYMBOL'],
                    side=side,
                    type='LIMIT',
                    timeInForce='GTC',
                    quantity=quantity,
                    price=str(limit_price)
                )
            order = _place_tp()
            
            order_id = order['orderId']
            print(f"✅ Take Profit placé: {order_id}")
            
            # Enregistrer dans les trades actifs
            if trade_id in self.active_trades:
                self.active_trades[trade_id]['take_profit_order_id'] = order_id
            
            return order_id
            
        except BinanceAPIException as e:
            print(f"❌ Erreur API placement Take Profit: {e}")
            trading_logger.error_occurred("PLACE_TP_API", str(e))
            return None
        except Exception as e:
            print(f"❌ Erreur placement Take Profit: {e}")
            trading_logger.error_occurred("PLACE_TP", str(e))
            return None
    
    def cancel_order(self, order_id):
        """Annule un ordre spécifique"""
        try:
            @RetryManager.with_configured_retry('ORDER_CANCELLATION')
            def _cancel_any():
                return self.client.futures_cancel_order(
                    symbol=config.ASSET_CONFIG['SYMBOL'],
                    orderId=order_id
                )
            _cancel_any()
            print(f"🚫 Ordre {order_id} annulé")
            return True
            
        except BinanceAPIException as e:
            print(f"❌ Erreur API annulation ordre {order_id}: {e}")
            trading_logger.error_occurred("CANCEL_ORDER_API", str(e))
            return False
        except Exception as e:
            print(f"❌ Erreur annulation ordre {order_id}: {e}")
            trading_logger.error_occurred("CANCEL_ORDER", str(e))
            return False
    
    def execute_complete_trade_with_delayed_sltp(self, side, candles_data, current_candle_time, signal_data=None):
        """
        Exécute un trade complet avec gestion retardée des SL/TP
        
        Args:
            side: 'LONG' ou 'SHORT'
            candles_data: Données des bougies pour calcul SL
            current_candle_time: Timestamp de la bougie actuelle d'entrée
            signal_data: Données du signal (optionnel)
            
        Returns:
            dict: Résultat du trade ou None si échec
        """
        try:
            print(f"\n🚀 === EXECUTION TRADE {side} AVEC SL/TP RETARDÉ ===")
            
            # 1. Validation conditions
            validation = self.position_manager.validate_trade_conditions()
            if not validation['status']:
                print(f"❌ Validation échouée: {validation['message']}")
                trading_logger.trade_conditions_check(validation)
                return None
            
            # 2. Récupération données de base
            balance = self.position_manager.get_account_balance(config.ASSET_CONFIG['BALANCE_ASSET'])
            current_price = self.get_current_price()
            
            if not current_price:
                print("❌ Impossible de récupérer le prix actuel")
                trading_logger.trade_failed("PRIX_ACTUEL_INDISPONIBLE", signal_data)
                return None
            
            # 3. Calcul Stop Loss basé sur les bougies
            sl_side = 'SHORT' if side == 'LONG' else 'LONG'
            sl_price = self.position_manager.calculate_stop_loss_price(
                candles_data, 
                side,
                config.TRADING_CONFIG['STOP_LOSS_LOOKBACK_CANDLES'],
                config.TRADING_CONFIG['STOP_LOSS_OFFSET_PERCENT']
            )
            
            if not sl_price:
                print("❌ Impossible de calculer le Stop Loss")
                trading_logger.trade_failed("CALCUL_SL_IMPOSSIBLE", signal_data)
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
                trading_logger.trade_failed("TAILLE_POSITION_INVALIDE", signal_data)
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
                trading_logger.trade_failed("ECHEC_ORDER_ENTREE", signal_data)
                return None
            
            # 7. Attendre exécution si ordre LIMIT
            if order_type == 'LIMIT' and entry_result['status'] == 'PENDING':
                execution_result = self.wait_for_order_execution(
                    entry_result['order_id'],
                    config.TRADING_CONFIG['ORDER_EXECUTION_TIMEOUT']
                )
                
                if execution_result and execution_result['status'] == 'FILLED':
                    # Ordre LIMIT exécuté avec succès
                    entry_result['executed_price'] = execution_result['executed_price']
                    entry_result['executed_quantity'] = execution_result['executed_quantity']
                    entry_result['status'] = 'FILLED'
                    
                elif execution_result and execution_result['status'] == 'TIMEOUT':
                    # TIMEOUT - Tenter fallback MARKET si activé
                    print(f"⏰ Ordre LIMIT timeout - Tentative fallback MARKET")
                    trading_logger.timeout_order(entry_result['order_id'], 'LIMIT', config.TRADING_CONFIG['ORDER_EXECUTION_TIMEOUT'])
                    
                    fallback_result = self.execute_market_fallback(
                        entry_side, 
                        quantity, 
                        'LIMIT'
                    )
                    
                    if fallback_result and fallback_result['status'] == 'FILLED':
                        # Fallback MARKET réussi
                        entry_result = fallback_result
                        print(f"✅ Fallback MARKET réussi - Trade continue")
                        trading_logger.fallback_executed('MARKET', 'LIMIT')
                    else:
                        # Fallback échoué aussi
                        print("❌ Fallback MARKET échoué - Trade abandonné")
                        trading_logger.fallback_failed('MARKET', 'LIMIT', 'EXECUTION_ECHOUEE')
                        return None
                else:
                    # Autre erreur d'exécution
                    print("❌ Ordre d'entrée non exécuté - Trade abandonné")
                    trading_logger.trade_failed("ENTREE_NON_EXECUTEE", signal_data)
                    return None
            
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
                self._emergency_close_position(entry_side, executed_quantity)
                trading_logger.trade_failed("CALCUL_TP_IMPOSSIBLE", signal_data)
                return None
            
            # 9. Créer un ID unique pour ce trade
            self.trade_counter += 1
            trade_id = f"trade_{self.trade_counter}_{int(time.time())}"
            
            # 10. NOUVEAU: Enregistrer le trade SANS placer SL/TP immédiatement
            self.active_trades[trade_id] = {
                'side': side,
                'entry_side': entry_side,
                'entry_order_id': entry_result['order_id'],
                'entry_price': executed_price,
                'quantity': executed_quantity,
                'stop_loss_price': sl_price,  # Prix calculé original
                'take_profit_price': tp_price,  # Prix calculé original
                'stop_loss_order_id': None,  # Sera rempli après placement retardé
                'take_profit_order_id': None,  # Sera rempli après placement retardé
                'timestamp': datetime.now().isoformat(),
                'signal_data': signal_data,
                'delayed_sltp': True  # Marqueur pour gestion retardée
            }
            
            # 11. NOUVEAU: Enregistrer pour gestion retardée des SL/TP
            if self.delayed_sltp_manager:
                delayed_success = self.delayed_sltp_manager.register_trade_for_delayed_sltp(
                    trade_result={
                        'trade_id': trade_id,
                        'side': side,
                        'entry_price': executed_price,
                        'quantity': executed_quantity
                    },
                    entry_candle_time=current_candle_time,
                    original_sl_price=sl_price,
                    original_tp_price=tp_price
                )
                
                if delayed_success:
                    print(f"📅 Trade {trade_id} enregistré pour SL/TP retardé")
                    print(f"   ⏰ SL/TP seront placés après fermeture de la bougie d'entrée")
                    trading_logger.info(f"Trade {trade_id} en attente de SL/TP retardé")
                else:
                    print(f"⚠️ Erreur enregistrement SL/TP retardé - Placement immédiat en fallback")
                    # Fallback: placement immédiat si erreur
                    self._place_immediate_sltp_fallback(trade_id, side, executed_quantity, sl_price, tp_price)
            else:
                # Pas de gestion retardée disponible - placement immédiat
                print(f"📊 Gestion retardée non disponible - Placement SL/TP immédiat")
                self._place_immediate_sltp_fallback(trade_id, side, executed_quantity, sl_price, tp_price)
            
            # 12. Démarrer monitoring si pas déjà actif
            if not self.monitoring_active:
                self.start_order_monitoring()
            
            # 13. Résultat final
            trade_result = {
                'trade_id': trade_id,
                'status': 'ACTIVE',
                'side': side,
                'entry_price': executed_price,
                'quantity': executed_quantity,
                'stop_loss_price': sl_price,  # Prix original calculé
                'take_profit_price': tp_price,  # Prix original calculé
                'risk_amount': abs(executed_price - sl_price) * executed_quantity,
                'potential_profit': abs(tp_price - executed_price) * executed_quantity,
                'delayed_sltp': self.delayed_sltp_manager is not None
            }
            
            print(f"✅ Trade {trade_id} créé avec succès!")
            print(f"   Entrée: {executed_price}")
            print(f"   SL calculé: {sl_price}")
            print(f"   TP calculé: {tp_price}")
            print(f"   Risque: {trade_result['risk_amount']:.2f}")
            print(f"   Profit potentiel: {trade_result['potential_profit']:.2f}")
            
            if self.delayed_sltp_manager:
                print(f"   🕐 Mode: SL/TP retardé après fermeture bougie")
            else:
                print(f"   ⚡ Mode: SL/TP immédiat")
            
            return trade_result
            
        except Exception as e:
            error_msg = f"Erreur exécution trade retardé: {str(e)}"
            print(f"❌ {error_msg}")
            trading_logger.trade_failed(error_msg, signal_data)
            return None

    # 4. NOUVELLE FONCTION _place_immediate_sltp_fallback
    def _place_immediate_sltp_fallback(self, trade_id, side, quantity, sl_price, tp_price):
        """
        Placement immédiat des SL/TP en cas de fallback
        (Méthode de secours si gestion retardée non disponible)
        """
        try:
            print(f"⚡ Placement SL/TP immédiat pour {trade_id} (fallback)")
            
            # Côtés des ordres (opposés à l'entrée)
            sl_order_side = 'SELL' if side == 'LONG' else 'BUY'
            tp_order_side = 'SELL' if side == 'LONG' else 'BUY'
            
            # Placement Stop Loss
            sl_order_id = self.place_stop_loss_order(
                sl_order_side,
                quantity,
                sl_price,
                trade_id
            )
            
            # Placement Take Profit  
            tp_order_id = self.place_take_profit_order(
                tp_order_side,
                quantity,
                tp_price,
                trade_id
            )
            
            if sl_order_id and tp_order_id:
                print(f"✅ SL/TP immédiat placé avec succès")
                # Marquer comme non-retardé
                if trade_id in self.active_trades:
                    self.active_trades[trade_id]['delayed_sltp'] = False
            else:
                print(f"⚠️ Échec placement SL/TP immédiat - Position sans protection!")
                trading_logger.warning(f"SL_TP_IMMEDIATE_FAILED pour {trade_id}")
                
        except Exception as e:
            error_msg = f"Erreur placement SL/TP immédiat: {str(e)}"
            print(f"❌ {error_msg}")
            trading_logger.error_occurred("IMMEDIATE_SLTP_FALLBACK", error_msg)

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
                trading_logger.trade_conditions_check(validation)
                return None
            
            # 2. Récupération données de base
            balance = self.position_manager.get_account_balance(config.ASSET_CONFIG['BALANCE_ASSET'])
            current_price = self.get_current_price()
            
            if not current_price:
                print("❌ Impossible de récupérer le prix actuel")
                trading_logger.trade_failed("PRIX_ACTUEL_INDISPONIBLE", signal_data)
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
                trading_logger.trade_failed("CALCUL_SL_IMPOSSIBLE", signal_data)
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
                trading_logger.trade_failed("TAILLE_POSITION_INVALIDE", signal_data)
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
                trading_logger.trade_failed("ECHEC_ORDER_ENTREE", signal_data)
                return None
            
            # 7. Attendre exécution si ordre LIMIT
            if order_type == 'LIMIT' and entry_result['status'] == 'PENDING':
                execution_result = self.wait_for_order_execution(
                    entry_result['order_id'],
                    config.TRADING_CONFIG['ORDER_EXECUTION_TIMEOUT']
                )
                
                if execution_result and execution_result['status'] == 'FILLED':
                    # Ordre LIMIT exécuté avec succès
                    entry_result['executed_price'] = execution_result['executed_price']
                    entry_result['executed_quantity'] = execution_result['executed_quantity']
                    entry_result['status'] = 'FILLED'
                    
                elif execution_result and execution_result['status'] == 'TIMEOUT':
                    # TIMEOUT - Tenter fallback MARKET si activé
                    print(f"⏰ Ordre LIMIT timeout - Tentative fallback MARKET")
                    trading_logger.timeout_order(entry_result['order_id'], 'LIMIT', config.TRADING_CONFIG['ORDER_EXECUTION_TIMEOUT'])
                    
                    fallback_result = self.execute_market_fallback(
                        entry_side, 
                        quantity, 
                        'LIMIT'
                    )
                    
                    if fallback_result and fallback_result['status'] == 'FILLED':
                        # Fallback MARKET réussi
                        entry_result = fallback_result
                        print(f"✅ Fallback MARKET réussi - Trade continue")
                        trading_logger.fallback_executed('MARKET', 'LIMIT')
                    else:
                        # Fallback échoué aussi
                        print("❌ Fallback MARKET échoué - Trade abandonné")
                        trading_logger.fallback_failed('MARKET', 'LIMIT', 'EXECUTION_ECHOUEE')
                        return None
                else:
                    # Autre erreur d'exécution
                    print("❌ Ordre d'entrée non exécuté - Trade abandonné")
                    trading_logger.trade_failed("ENTREE_NON_EXECUTEE", signal_data)
                    return None
            
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
                trading_logger.trade_failed("CALCUL_TP_IMPOSSIBLE", signal_data)
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
                trading_logger.warning("SL_TP_NON_PLACES - Position sans protection")
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
            trading_logger.trade_failed(str(e), signal_data)
            return None
    
    def _emergency_close_position(self, original_side, quantity):
        """Ferme une position en urgence"""
        try:
            emergency_side = 'SELL' if original_side == 'BUY' else 'BUY'
            print(f"🚨 Fermeture d'urgence: {emergency_side} {quantity}")
            
            @RetryManager.with_configured_retry('ORDER_PLACEMENT')
            def _emergency():
                return self.client.futures_create_order(
                    symbol=config.ASSET_CONFIG['SYMBOL'],
                    side=emergency_side,
                    type='MARKET',
                    quantity=quantity
                )
            _emergency()
            print("✅ Position fermée en urgence")
            
        except Exception as e:
            print(f"❌ Erreur fermeture d'urgence: {e}")
            trading_logger.error_occurred("EMERGENCY_CLOSE", str(e))
    
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
        
        # CORRIGÉ: Arrêter aussi le monitoring SL/TP retardé
        if (hasattr(self, 'delayed_sltp_manager') and 
            self.delayed_sltp_manager is not None):
            self.delayed_sltp_manager.stop_monitoring()
    
        print("🛑 Monitoring arrêté")
            
    # 6. NOUVELLE FONCTION get_complete_trading_status
    def get_complete_trading_status(self):
        """Retourne un statut complet incluant les trades retardés"""
        status = {
            'active_trades': self.get_active_trades(),
            'delayed_sltp_status': None
        }
        
        if (hasattr(self, 'delayed_sltp_manager') and 
            self.delayed_sltp_manager is not None):
            status['delayed_sltp_status'] = self.delayed_sltp_manager.get_pending_trades_status()
        
        return status

    # 7. NOUVELLE FONCTION force_process_delayed_trade
    def force_process_delayed_trade(self, trade_id):
        """Force le traitement d'un trade avec SL/TP retardé"""
        if (not hasattr(self, 'delayed_sltp_manager') or 
            self.delayed_sltp_manager is None):
            print("❌ Gestionnaire SL/TP retardé non disponible")
            return False
        
        return self.delayed_sltp_manager.force_process_trade(trade_id)
    
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