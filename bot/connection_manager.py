"""
Gestionnaire central des connexions et synchronisation d'état
"""
import time
import threading
from datetime import datetime
import config
from trading_logger import trading_logger

class ConnectionManager:
    def __init__(self, bot_instance):
        """Initialise le gestionnaire de connexions"""
        self.bot = bot_instance
        self.websocket_connected = False
        self.last_websocket_data = None
        self.reconnection_active = False
        self.reconnection_thread = None
        self.reconnection_count = 0
        self.last_reconnection_attempt = 0
        self.safe_mode_until = 0
        
        # Configuration depuis config
        self.retry_enabled = config.CONNECTION_CONFIG.get('WEBSOCKET_RETRY_ENABLED', True)
        self.retry_interval = config.CONNECTION_CONFIG.get('WEBSOCKET_RETRY_INTERVAL', 30)
        self.max_retries = config.CONNECTION_CONFIG.get('WEBSOCKET_MAX_RETRIES', 0)  # 0 = infini
        self.backoff_max = config.CONNECTION_CONFIG.get('WEBSOCKET_BACKOFF_MAX', 300)
        self.health_check_interval = config.CONNECTION_CONFIG.get('WEBSOCKET_HEALTH_CHECK', 60)
        
        print(f"✅ ConnectionManager initialisé (retry: {self.retry_enabled}, interval: {self.retry_interval}s)")
        trading_logger.system_status("ConnectionManager initialisé")
    
    def websocket_connected_callback(self):
        """Appelé quand WebSocket se connecte"""
        self.websocket_connected = True
        self.last_websocket_data = time.time()
        
        if self.reconnection_count > 0:
            print(f"🎉 RECONNEXION WEBSOCKET RÉUSSIE après {self.reconnection_count} tentatives")
            trading_logger.system_status(f"Reconnexion WebSocket réussie après {self.reconnection_count} tentatives")
            
            # Synchronisation obligatoire après reconnexion
            if config.CONNECTION_CONFIG.get('SYNC_AFTER_RECONNECTION', True):
                self.sync_state_after_reconnection()
            
            # Reset compteur
            self.reconnection_count = 0
            
        self.reconnection_active = False
    
    def websocket_disconnected_callback(self):
        """Appelé quand WebSocket se déconnecte"""
        self.websocket_connected = False
        
        if not self.reconnection_active and self.retry_enabled:
            print("💥 PERTE CONNEXION WEBSOCKET - Démarrage reconnexion automatique")
            trading_logger.error_occurred("WEBSOCKET_DISCONNECT", "Perte connexion WebSocket")
            self.start_reconnection_process()
    
    def websocket_data_received_callback(self):
        """Appelé à chaque réception de données WebSocket"""
        self.last_websocket_data = time.time()
    
    def start_reconnection_process(self):
        """Démarre le processus de reconnexion automatique"""
        if self.reconnection_active:
            return
        
        self.reconnection_active = True
        self.reconnection_thread = threading.Thread(
            target=self._reconnection_loop,
            daemon=True
        )
        self.reconnection_thread.start()
    
    def _reconnection_loop(self):
        """Boucle de reconnexion avec backoff exponentiel"""
        print("🔄 Démarrage boucle de reconnexion automatique")
        
        while self.reconnection_active and not self.websocket_connected:
            try:
                self.reconnection_count += 1
                
                # Vérifier limite max si configurée
                if self.max_retries > 0 and self.reconnection_count > self.max_retries:
                    print(f"❌ Limite de reconnexions atteinte ({self.max_retries})")
                    trading_logger.error_occurred("WEBSOCKET_RECONNECT", f"Limite reconnexions atteinte: {self.max_retries}")
                    break
                
                # Calculer délai avec backoff exponentiel
                base_delay = self.retry_interval
                backoff_delay = min(base_delay * (2 ** (self.reconnection_count - 1)), self.backoff_max)
                
                print(f"🔄 Tentative reconnexion #{self.reconnection_count} dans {backoff_delay}s...")
                trading_logger.info(f"Tentative reconnexion WebSocket #{self.reconnection_count}")
                
                # Attendre avant nouvelle tentative
                time.sleep(backoff_delay)
                
                if not self.reconnection_active:
                    break
                
                # Tentative de reconnexion
                print(f"🔗 Reconnexion WebSocket en cours...")
                self.last_reconnection_attempt = time.time()
                
                # Arrêter ancien WebSocket s'il existe
                if self.bot.ws_handler:
                    self.bot.ws_handler.stop()
                    time.sleep(1)  # Laisser temps pour fermeture propre
                
                # Créer nouveau WebSocket
                from websocket_handler import BinanceWebSocketHandler
                self.bot.ws_handler = BinanceWebSocketHandler(
                    config.SYMBOL,
                    config.TIMEFRAME,
                    self.bot.on_kline_update
                )
                
                # Attacher callbacks de connexion
                self.bot.ws_handler.connection_manager = self
                
                # Démarrer nouvelle connexion
                self.bot.ws_handler.start()
                
                # Attendre résultat de connexion
                connection_timeout = 15
                start_wait = time.time()
                
                while (time.time() - start_wait) < connection_timeout:
                    if self.websocket_connected:
                        break
                    time.sleep(0.5)
                
                if self.websocket_connected:
                    print("✅ Reconnexion WebSocket réussie!")
                    break
                else:
                    print(f"❌ Échec reconnexion #{self.reconnection_count}")
                
            except Exception as e:
                print(f"❌ Erreur lors reconnexion #{self.reconnection_count}: {e}")
                trading_logger.error_occurred("WEBSOCKET_RECONNECT", f"Erreur reconnexion: {str(e)}")
        
        if not self.websocket_connected and self.max_retries > 0:
            print("❌ ÉCHEC RECONNEXION - Arrêt des tentatives")
            trading_logger.error_occurred("WEBSOCKET_RECONNECT", "Échec final reconnexion WebSocket")
        
        self.reconnection_active = False
    
    def sync_state_after_reconnection(self):
        """Synchronise l'état local avec Binance après reconnexion"""
        try:
            print("🔄 SYNCHRONISATION POST-RECONNEXION...")
            trading_logger.system_status("Début synchronisation post-reconnexion")
            
            # Activer mode sécurisé temporaire
            self.enter_safe_mode()
            
            # Vérifier positions réelles sur Binance
            if self.bot.position_manager is None:
                print("⚠️ Position Manager non disponible - Skip synchronisation")
                return
            
            real_positions = self.bot.position_manager.get_current_positions()
            symbol_positions = [p for p in real_positions if p['symbol'] == config.ASSET_CONFIG['SYMBOL']]
            
            # Vérifier trades locaux
            local_trades = {}
            if self.bot.trade_executor is not None:
                local_trades = self.bot.trade_executor.get_active_trades()
            
            print(f"📊 ÉTAT DÉTECTÉ:")
            print(f"   Positions Binance: {len(symbol_positions)}")
            print(f"   Trades locaux: {len(local_trades)}")
            
            # Log détaillé
            trading_logger.info(f"Sync détecté - Positions Binance: {len(symbol_positions)}, Trades locaux: {len(local_trades)}")
            
            # Gestion selon état détecté
            if len(symbol_positions) > 0:
                self.handle_existing_positions(symbol_positions)
            
            if len(local_trades) > 0 and len(symbol_positions) == 0:
                self.cleanup_ghost_trades(local_trades)
            
            if len(symbol_positions) == 0 and len(local_trades) == 0:
                print("✅ Aucune position détectée - État clean")
                trading_logger.info("Synchronisation: État clean détecté")
            
            print("✅ SYNCHRONISATION TERMINÉE")
            trading_logger.system_status("Synchronisation post-reconnexion terminée")
            
        except Exception as e:
            error_msg = f"Erreur lors synchronisation: {str(e)}"
            print(f"❌ {error_msg}")
            trading_logger.error_occurred("SYNC_ERROR", error_msg)
    
    def handle_existing_positions(self, positions):
        """Gère les positions existantes détectées"""
        try:
            for position in positions:
                print(f"⚠️ POSITION ACTIVE DÉTECTÉE:")
                print(f"   {position['side']}: {position['size']} @ {position['entry_price']}")
                print(f"   PnL: {position['pnl']:.2f}")
                
                trading_logger.info(f"Position active détectée: {position['side']} {position['size']} @ {position['entry_price']}")
            
            # Vérifier limite MAX_POSITIONS
            max_positions = config.TRADING_CONFIG.get('MAX_POSITIONS', 1)
            if len(positions) >= max_positions:
                print(f"🚫 MAX_POSITIONS ({max_positions}) atteinte - Nouveaux trades BLOQUÉS")
                trading_logger.warning(f"MAX_POSITIONS atteinte: {len(positions)}/{max_positions}")
                
                # Marquer pour bloquer nouveaux trades
                if hasattr(self.bot, 'trading_blocked_by_position'):
                    self.bot.trading_blocked_by_position = True
            
            # Tentative de reconstruction du monitoring si possible
            self.attempt_monitoring_reconstruction(positions)
            
        except Exception as e:
            error_msg = f"Erreur gestion positions existantes: {str(e)}"
            print(f"❌ {error_msg}")
            trading_logger.error_occurred("POSITION_HANDLING", error_msg)
    
    def cleanup_ghost_trades(self, ghost_trades):
        """Nettoie les trades fantômes locaux"""
        try:
            print(f"🧹 NETTOYAGE {len(ghost_trades)} TRADES FANTÔMES...")
            
            for trade_id, trade_info in ghost_trades.items():
                print(f"🧹 Nettoyage trade fantôme: {trade_id}")
                trading_logger.info(f"Nettoyage trade fantôme: {trade_id}")
                
                # Essayer d'annuler ordres SL/TP s'ils existent
                if self.bot.trade_executor is not None:
                    try:
                        if trade_info.get('stop_loss_order_id'):
                            self.bot.trade_executor.cancel_order(trade_info['stop_loss_order_id'])
                            print(f"   🚫 SL annulé: {trade_info['stop_loss_order_id']}")
                        
                        if trade_info.get('take_profit_order_id'):
                            self.bot.trade_executor.cancel_order(trade_info['take_profit_order_id'])
                            print(f"   🚫 TP annulé: {trade_info['take_profit_order_id']}")
                        
                    except Exception as e:
                        print(f"   ⚠️ Erreur annulation ordres: {e}")
                
                # Supprimer du tracking local
                if self.bot.trade_executor is not None and trade_id in self.bot.trade_executor.active_trades:
                    del self.bot.trade_executor.active_trades[trade_id]
                    print(f"   ✅ Trade retiré du tracking local")
            
            print("✅ Nettoyage trades fantômes terminé")
            trading_logger.info("Nettoyage trades fantômes terminé")
            
        except Exception as e:
            error_msg = f"Erreur nettoyage trades fantômes: {str(e)}"
            print(f"❌ {error_msg}")
            trading_logger.error_occurred("GHOST_CLEANUP", error_msg)
    
    def attempt_monitoring_reconstruction(self, positions):
        """Tente de reconstruire le monitoring pour positions existantes"""
        try:
            print("🔧 Tentative reconstruction monitoring...")
            
            # Pour l'instant, juste un log - implémentation complexe
            # Future amélioration: essayer de retrouver ordres SL/TP
            print("⚠️ Reconstruction monitoring non implémentée")
            print("👁️ Surveillance manuelle recommandée pour positions existantes")
            
            trading_logger.warning("Reconstruction monitoring non disponible - Surveillance manuelle requise")
            
        except Exception as e:
            error_msg = f"Erreur reconstruction monitoring: {str(e)}"
            print(f"❌ {error_msg}")
            trading_logger.error_occurred("MONITORING_RECONSTRUCTION", error_msg)
    
    def enter_safe_mode(self, duration=300):
        """Active le mode sécurisé temporaire"""
        self.safe_mode_until = time.time() + duration
        print(f"🛡️ MODE SÉCURISÉ activé pendant {duration//60} minutes")
        trading_logger.system_status(f"Mode sécurisé activé pendant {duration}s")
    
    def is_safe_mode_active(self):
        """Vérifie si le mode sécurisé est actif"""
        return time.time() < self.safe_mode_until
    
    def validate_trade_conditions_post_sync(self):
        """Validation renforcée des conditions de trade après sync"""
        try:
            # Vérification positions en temps réel
            if self.bot.position_manager is None:
                trading_logger.error_occurred("POST_SYNC_VALIDATION", "PositionManager indisponible")
                return False
            
            current_positions = self.bot.position_manager.get_current_positions()
            symbol_positions = [p for p in current_positions if p['symbol'] == config.ASSET_CONFIG['SYMBOL']]
            
            max_positions = config.TRADING_CONFIG.get('MAX_POSITIONS', 1)
            
            if len(symbol_positions) >= max_positions:
                if self.is_safe_mode_active():
                    print(f"🛡️ SAFE MODE: Trade bloqué - Position détectée ({len(symbol_positions)}/{max_positions})")
                else:
                    print(f"🚫 TRADE BLOQUÉ: MAX_POSITIONS atteinte ({len(symbol_positions)}/{max_positions})")
                
                trading_logger.warning(f"Trade bloqué - MAX_POSITIONS: {len(symbol_positions)}/{max_positions}")
                return False
            
            # Mode sécurisé actif
            if self.is_safe_mode_active():
                remaining_time = int(self.safe_mode_until - time.time())
                print(f"🛡️ MODE SÉCURISÉ: Validation renforcée (reste {remaining_time//60}m {remaining_time%60}s)")
                
                # Double vérification en mode sécurisé
                time.sleep(1)
                current_positions_double_check = self.bot.position_manager.get_current_positions()
                symbol_positions_double_check = [p for p in current_positions_double_check if p['symbol'] == config.ASSET_CONFIG['SYMBOL']]
                
                if len(symbol_positions_double_check) != len(symbol_positions):
                    print("⚠️ SAFE MODE: État positions incohérent entre vérifications")
                    trading_logger.warning("Safe mode: État positions incohérent")
                    return False
            
            return True
            
        except Exception as e:
            error_msg = f"Erreur validation post-sync: {str(e)}"
            print(f"❌ {error_msg}")
            trading_logger.error_occurred("POST_SYNC_VALIDATION", error_msg)
            return False
    
    def get_connection_status(self):
        """Retourne le statut des connexions"""
        return {
            'websocket_connected': self.websocket_connected,
            'reconnection_active': self.reconnection_active,
            'reconnection_count': self.reconnection_count,
            'last_data_received': self.last_websocket_data,
            'safe_mode_active': self.is_safe_mode_active(),
            'safe_mode_until': self.safe_mode_until
        }
    
    def force_reconnection(self):
        """Force une reconnexion manuelle"""
        print("🔄 RECONNEXION FORCÉE...")
        self.websocket_connected = False
        self.websocket_disconnected_callback()
    
    def stop_reconnection(self):
        """Arrête le processus de reconnexion"""
        self.reconnection_active = False
        if self.reconnection_thread and self.reconnection_thread.is_alive():
            self.reconnection_thread.join(timeout=5)
        print("🛑 Processus de reconnexion arrêté")