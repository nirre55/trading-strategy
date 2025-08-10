"""
Module pour la gestion retardée des ordres Stop Loss et Take Profit
Attend la fermeture de la bougie d'entrée + applique des offsets dynamiques
"""
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable
import config
from trading_logger import trading_logger
from typing import Dict, Optional, TYPE_CHECKING
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from trade_executor import TradeExecutor
    from binance_client import BinanceClient

class DelayedSLTPManager:
    def __init__(self, trade_executor: 'TradeExecutor', binance_client: Optional['BinanceClient']):
        """
        Initialise le gestionnaire de SL/TP retardés
        
        Args:
            trade_executor: Instance de TradeExecutor
            binance_client: Instance de BinanceClient
        """
        
        self.trade_executor = trade_executor
        self.binance_client = binance_client
        
        # Trades en attente de SL/TP
        self.pending_trades: Dict[str, Dict] = {}
        
        # Thread de monitoring
        self.monitoring_active = False
        self.monitoring_thread = None
        
        # Configuration depuis config
        self.offset_percent = config.DELAYED_SLTP_CONFIG.get('PRICE_OFFSET_PERCENT', 0.01)
        self.check_interval = config.DELAYED_SLTP_CONFIG.get('CHECK_INTERVAL_SECONDS', 10)
        
        print("✅ DelayedSLTPManager initialisé")
        trading_logger.info("DelayedSLTPManager initialisé")
    
    def register_trade_for_delayed_sltp(self, trade_result, entry_candle_time, original_sl_price, original_tp_price):
        """
        Enregistre un trade pour la gestion retardée des SL/TP
        
        Args:
            trade_result: Résultat du trade (contient trade_id, side, etc.)
            entry_candle_time: Timestamp de la bougie d'entrée
            original_sl_price: Prix SL calculé original
            original_tp_price: Prix TP calculé original
        """
        try:
            trade_id = trade_result['trade_id']
            
            # Calculer le temps de fin de la bougie d'entrée
            timeframe = config.ASSET_CONFIG['TIMEFRAME']
            candle_duration = self._get_candle_duration_seconds(timeframe)
            end_of_candle = entry_candle_time + timedelta(seconds=candle_duration)
            
            # Enregistrer le trade en attente
            self.pending_trades[trade_id] = {
                'trade_result': trade_result,
                'entry_candle_time': entry_candle_time,
                'end_of_candle_time': end_of_candle,
                'original_sl_price': original_sl_price,
                'original_tp_price': original_tp_price,
                'sl_tp_placed': False,
                'registration_time': datetime.now()
            }
            
            print(f"📅 Trade {trade_id} enregistré pour SL/TP retardé")
            print(f"   Bougie d'entrée: {entry_candle_time}")
            print(f"   Attente jusqu'à: {end_of_candle}")
            
            trading_logger.info(f"Trade {trade_id} enregistré pour SL/TP retardé - Attente jusqu'à {end_of_candle}")
            
            # Démarrer le monitoring si pas déjà actif
            if not self.monitoring_active:
                self.start_monitoring()
            
            return True
            
        except Exception as e:
            error_msg = f"Erreur enregistrement trade retardé: {str(e)}"
            print(f"❌ {error_msg}")
            trading_logger.error_occurred("DELAYED_SLTP_REGISTER", error_msg)
            return False
    
    def _get_candle_duration_seconds(self, timeframe):
        """Convertit un timeframe en secondes"""
        timeframe_map = {
            '1m': 60,
            '3m': 180,
            '5m': 300,
            '15m': 900,
            '30m': 1800,
            '1h': 3600,
            '2h': 7200,
            '4h': 14400,
            '6h': 21600,
            '8h': 28800,
            '12h': 43200,
            '1d': 86400,
            '3d': 259200,
            '1w': 604800,
            '1M': 2592000  # Approximation 30 jours
        }
        
        return timeframe_map.get(timeframe, 300)  # Défaut 5m
    
    def start_monitoring(self):
        """Démarre le monitoring des trades en attente"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self.monitoring_thread.start()
        print("👁️ Monitoring SL/TP retardé démarré")
        trading_logger.info("Monitoring SL/TP retardé démarré")
    
    def _monitoring_loop(self):
        """Boucle principale de monitoring"""
        print("🔄 Boucle monitoring SL/TP retardé active")
        
        while self.monitoring_active:
            try:
                current_time = datetime.now()
                trades_to_process = []
                
                # Identifier les trades prêts à être traités
                for trade_id, trade_info in self.pending_trades.items():
                    if not trade_info['sl_tp_placed'] and current_time >= trade_info['end_of_candle_time']:
                        trades_to_process.append(trade_id)
                
                # Traiter les trades prêts
                for trade_id in trades_to_process:
                    self._process_delayed_trade(trade_id)
                
                # Nettoyer les trades terminés
                self._cleanup_completed_trades()
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                error_msg = f"Erreur boucle monitoring SL/TP: {str(e)}"
                print(f"❌ {error_msg}")
                trading_logger.error_occurred("DELAYED_SLTP_MONITORING", error_msg)
                time.sleep(30)  # Attendre plus longtemps en cas d'erreur
        
        print("🛑 Monitoring SL/TP retardé arrêté")
    
    def _process_delayed_trade(self, trade_id):
        """
        Traite un trade dont la bougie d'entrée est fermée
        
        Args:
            trade_id: ID du trade à traiter
        """
        try:
            if trade_id not in self.pending_trades:
                return
            
            trade_info = self.pending_trades[trade_id]
            trade_result = trade_info['trade_result']
            
            print(f"\n🕐 TRAITEMENT TRADE RETARDÉ: {trade_id}")
            print(f"   Bougie d'entrée fermée, placement SL/TP...")
            
            # Récupérer le prix actuel
            current_price = self.trade_executor.get_current_price()
            if not current_price:
                print(f"❌ Impossible de récupérer le prix actuel pour {trade_id}")
                return
            
            print(f"📊 Prix actuel: {current_price}")
            print(f"📊 Prix d'entrée: {trade_result['entry_price']}")
            
            # Calculer les prix SL/TP avec offsets si nécessaire
            adjusted_sl_price = self._calculate_adjusted_sl_price(
                trade_info, current_price, trade_result
            )
            
            adjusted_tp_price = self._calculate_adjusted_tp_price(
                trade_info, current_price, trade_result
            )
            
            if not adjusted_sl_price or not adjusted_tp_price:
                print(f"❌ Impossible de calculer SL/TP ajustés pour {trade_id}")
                trading_logger.error_occurred("DELAYED_SLTP_CALC", f"Calcul SL/TP ajustés échoué pour {trade_id}")
                return
            
            # Placement des ordres
            success = self._place_delayed_orders(trade_id, trade_result, adjusted_sl_price, adjusted_tp_price)
            
            if success:
                trade_info['sl_tp_placed'] = True
                trade_info['final_sl_price'] = adjusted_sl_price
                trade_info['final_tp_price'] = adjusted_tp_price
                trade_info['placement_time'] = datetime.now()
                
                print(f"✅ SL/TP retardés placés pour {trade_id}")
                trading_logger.info(f"SL/TP retardés placés pour {trade_id} - SL: {adjusted_sl_price}, TP: {adjusted_tp_price}")
            else:
                print(f"❌ Échec placement SL/TP retardés pour {trade_id}")
                trading_logger.error_occurred("DELAYED_SLTP_PLACEMENT", f"Échec placement pour {trade_id}")
            
        except Exception as e:
            error_msg = f"Erreur traitement trade retardé {trade_id}: {str(e)}"
            print(f"❌ {error_msg}")
            trading_logger.error_occurred("DELAYED_SLTP_PROCESS", error_msg)
    
    def _calculate_adjusted_sl_price(self, trade_info, current_price, trade_result):
        """
        Calcule le prix SL ajusté avec offset si nécessaire
        
        Args:
            trade_info: Informations du trade
            current_price: Prix actuel du marché
            trade_result: Résultat du trade original
            
        Returns:
            Prix SL ajusté ou None si erreur
        """
        try:
            original_sl = float(trade_info['original_sl_price'])
            entry_price = float(trade_result['entry_price'])
            side = trade_result['side']
            
            print(f"🎯 Calcul SL ajusté:")
            print(f"   SL original: {original_sl}")
            print(f"   Prix entrée: {entry_price}")
            print(f"   Prix actuel: {current_price}")
            
            # Vérifier si le prix actuel a dépassé le SL original
            sl_breached = False
            
            if side == 'LONG':
                # Pour LONG: SL déclenché si prix actuel < SL original
                sl_breached = current_price < original_sl
            else:  # SHORT
                # Pour SHORT: SL déclenché si prix actuel > SL original
                sl_breached = current_price > original_sl
            
            if sl_breached:
                # Appliquer l'offset pour compenser le dépassement
                offset_amount = abs(current_price * self.offset_percent / 100)
                
                if side == 'LONG':
                    # Pour LONG: SL plus bas avec offset
                    adjusted_sl = current_price - offset_amount
                    print(f"   ⚠️ SL original dépassé! Nouveau SL: {current_price} - {self.offset_percent}% = {adjusted_sl}")
                else:  # SHORT
                    # Pour SHORT: SL plus haut avec offset
                    adjusted_sl = current_price + offset_amount
                    print(f"   ⚠️ SL original dépassé! Nouveau SL: {current_price} + {self.offset_percent}% = {adjusted_sl}")
                
                trading_logger.warning(f"SL original dépassé pour trade - Offset appliqué: {self.offset_percent}%")
                
            else:
                # Prix n'a pas dépassé le SL, garder l'original
                adjusted_sl = original_sl
                print(f"   ✅ SL original respecté: {adjusted_sl}")
            
            # Formater selon les règles du symbole
            formatted_sl = self.trade_executor.position_manager.format_price(adjusted_sl)
            print(f"   📐 SL formaté: {formatted_sl}")
            
            return formatted_sl
            
        except Exception as e:
            error_msg = f"Erreur calcul SL ajusté: {str(e)}"
            print(f"❌ {error_msg}")
            trading_logger.error_occurred("DELAYED_SL_CALC", error_msg)
            return None
    
    def _calculate_adjusted_tp_price(self, trade_info, current_price, trade_result):
        """
        Calcule le prix TP ajusté avec offset si nécessaire
        
        Args:
            trade_info: Informations du trade
            current_price: Prix actuel du marché
            trade_result: Résultat du trade original
            
        Returns:
            Prix TP ajusté ou None si erreur
        """
        try:
            original_tp = float(trade_info['original_tp_price'])
            entry_price = float(trade_result['entry_price'])
            side = trade_result['side']
            
            print(f"🎯 Calcul TP ajusté:")
            print(f"   TP original: {original_tp}")
            print(f"   Prix entrée: {entry_price}")
            print(f"   Prix actuel: {current_price}")
            
            # Vérifier si le prix actuel a dépassé le TP original
            tp_breached = False
            
            if side == 'LONG':
                # Pour LONG: TP atteint si prix actuel > TP original
                tp_breached = current_price > original_tp
            else:  # SHORT
                # Pour SHORT: TP atteint si prix actuel < TP original
                tp_breached = current_price < original_tp
            
            if tp_breached:
                # Appliquer l'offset pour optimiser le TP
                offset_amount = abs(current_price * self.offset_percent / 100)
                
                if side == 'LONG':
                    # Pour LONG: TP plus haut avec offset
                    adjusted_tp = current_price + offset_amount
                    print(f"   🚀 TP original dépassé! Nouveau TP: {current_price} + {self.offset_percent}% = {adjusted_tp}")
                else:  # SHORT
                    # Pour SHORT: TP plus bas avec offset
                    adjusted_tp = current_price - offset_amount
                    print(f"   🚀 TP original dépassé! Nouveau TP: {current_price} - {self.offset_percent}% = {adjusted_tp}")
                
                trading_logger.info(f"TP original dépassé pour trade - Offset appliqué: {self.offset_percent}%")
                
            else:
                # Prix n'a pas dépassé le TP, garder l'original
                adjusted_tp = original_tp
                print(f"   ✅ TP original respecté: {adjusted_tp}")
            
            # Formater selon les règles du symbole
            formatted_tp = self.trade_executor.position_manager.format_price(adjusted_tp)
            print(f"   📐 TP formaté: {formatted_tp}")
            
            return formatted_tp
            
        except Exception as e:
            error_msg = f"Erreur calcul TP ajusté: {str(e)}"
            print(f"❌ {error_msg}")
            trading_logger.error_occurred("DELAYED_TP_CALC", error_msg)
            return None
    
    def _place_delayed_orders(self, trade_id, trade_result, sl_price, tp_price):
        """
        Place les ordres SL/TP retardés
        
        Args:
            trade_id: ID du trade
            trade_result: Résultat du trade
            sl_price: Prix SL ajusté
            tp_price: Prix TP ajusté
            
        Returns:
            True si succès, False sinon
        """
        try:
            side = trade_result['side']
            quantity = trade_result['quantity']
            
            # Côtés des ordres (opposés à l'entrée)
            sl_order_side = 'SELL' if side == 'LONG' else 'BUY'
            tp_order_side = 'SELL' if side == 'LONG' else 'BUY'
            
            print(f"📋 Placement ordres retardés pour {trade_id}:")
            print(f"   Quantité: {quantity}")
            print(f"   SL: {sl_order_side} @ {sl_price}")
            print(f"   TP: {tp_order_side} @ {tp_price}")
            
            # Placer Stop Loss
            sl_order_id = self.trade_executor.place_stop_loss_order(
                sl_order_side,
                quantity,
                sl_price,
                trade_id
            )
            
            # Placer Take Profit
            tp_order_id = self.trade_executor.place_take_profit_order(
                tp_order_side,
                quantity,
                tp_price,
                trade_id
            )
            
            if sl_order_id and tp_order_id:
                print(f"✅ Ordres retardés placés:")
                print(f"   SL Order ID: {sl_order_id}")
                print(f"   TP Order ID: {tp_order_id}")
                
                # Log détaillé
                trading_logger.info(f"Ordres SL/TP retardés placés - Trade: {trade_id}, SL: {sl_order_id}, TP: {tp_order_id}")
                
                return True
            else:
                print(f"❌ Échec placement ordres retardés")
                if not sl_order_id:
                    print("   Stop Loss non placé")
                if not tp_order_id:
                    print("   Take Profit non placé")
                
                return False
                
        except Exception as e:
            error_msg = f"Erreur placement ordres retardés: {str(e)}"
            print(f"❌ {error_msg}")
            trading_logger.error_occurred("DELAYED_ORDERS_PLACEMENT", error_msg)
            return False
    
    def _cleanup_completed_trades(self):
        """Nettoie les trades terminés depuis plus de 24h"""
        try:
            current_time = datetime.now()
            cleanup_threshold = timedelta(hours=24)
            
            trades_to_remove = []
            
            for trade_id, trade_info in self.pending_trades.items():
                if trade_info['sl_tp_placed']:
                    placement_time = trade_info.get('placement_time', trade_info['registration_time'])
                    if current_time - placement_time > cleanup_threshold:
                        trades_to_remove.append(trade_id)
            
            for trade_id in trades_to_remove:
                del self.pending_trades[trade_id]
                print(f"🧹 Trade retardé nettoyé: {trade_id}")
                
        except Exception as e:
            error_msg = f"Erreur nettoyage trades retardés: {str(e)}"
            print(f"❌ {error_msg}")
            trading_logger.error_occurred("DELAYED_CLEANUP", error_msg)
    
    def get_pending_trades_status(self):
        """Retourne le statut des trades en attente"""
        status = {
            'total_pending': len(self.pending_trades),
            'waiting_for_candle_close': 0,
            'ready_for_processing': 0,
            'completed': 0,
            'trades': {}
        }
        
        current_time = datetime.now()
        
        for trade_id, trade_info in self.pending_trades.items():
            if trade_info['sl_tp_placed']:
                status['completed'] += 1
                trade_status = 'completed'
            elif current_time >= trade_info['end_of_candle_time']:
                status['ready_for_processing'] += 1
                trade_status = 'ready'
            else:
                status['waiting_for_candle_close'] += 1
                trade_status = 'waiting'
            
            status['trades'][trade_id] = {
                'status': trade_status,
                'end_of_candle_time': trade_info['end_of_candle_time'],
                'sl_tp_placed': trade_info['sl_tp_placed'],
                'side': trade_info['trade_result']['side']
            }
        
        return status
    
    def force_process_trade(self, trade_id):
        """Force le traitement d'un trade spécifique"""
        if trade_id not in self.pending_trades:
            print(f"❌ Trade {trade_id} non trouvé dans les trades en attente")
            return False
        
        print(f"🔄 Traitement forcé du trade {trade_id}")
        self._process_delayed_trade(trade_id)
        return True
    
    def cancel_delayed_trade(self, trade_id):
        """Annule la gestion retardée d'un trade"""
        if trade_id not in self.pending_trades:
            print(f"❌ Trade {trade_id} non trouvé dans les trades en attente")
            return False
        
        trade_info = self.pending_trades[trade_id]
        
        if trade_info['sl_tp_placed']:
            print(f"⚠️ Trade {trade_id} déjà traité, impossible d'annuler")
            return False
        
        del self.pending_trades[trade_id]
        print(f"🚫 Gestion retardée annulée pour trade {trade_id}")
        trading_logger.info(f"Gestion retardée annulée pour trade {trade_id}")
        return True
    
    def stop_monitoring(self):
        """Arrête le monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=10)
        print("🛑 Monitoring SL/TP retardé arrêté")
        trading_logger.info("Monitoring SL/TP retardé arrêté")

