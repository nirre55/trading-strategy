# live_engine.py
"""
Moteur principal de trading live
Orchestre tous les composants du système
"""
import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional
import signal
import sys

from config_live import (
    API_CONFIG, TRADING_CONFIG, FILTERS_CONFIG, 
    MONITORING_CONFIG, SAFETY_LIMITS, ENVIRONMENT
)
from binance_client import BinanceFuturesClient
from data_manager import RealTimeDataManager
from signal_detector import LiveSignalDetector
from risk_manager import LiveRiskManager
from order_manager import LiveOrderManager
from monitoring import LiveMonitoring, PerformanceTracker

logger = logging.getLogger(__name__)

class LiveTradingEngine:
    """Moteur principal de trading live"""
    
    def __init__(self):
        self.running = False
        self.initialized = False
        
        # Composants principaux
        self.binance_client = None
        self.data_manager = None
        self.signal_detector = None
        self.risk_manager = None
        self.order_manager = None
        self.monitoring = None
        self.performance_tracker = None
        
        # État du système
        self.last_signal = None
        self.system_health = {}
        self.emergency_stop = False
        
        # Threading
        self.main_thread = None
        self.health_check_thread = None
        
        # Configuration du signal handler pour arrêt propre
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def initialize(self) -> bool:
        """Initialise tous les composants du système"""
        try:
            logger.info("🚀 Initialisation du moteur de trading live...")
            
            # 1. Client Binance
            logger.info("📡 Connexion à Binance...")
            self.binance_client = BinanceFuturesClient(
                api_key=API_CONFIG["api_key"],
                api_secret=API_CONFIG["api_secret"],
                testnet=API_CONFIG["testnet"]
            )
            
            if not self.binance_client.connect():
                logger.error("❌ Échec connexion Binance")
                return False
            
            # 2. Gestionnaire de données temps réel
            logger.info("📊 Initialisation données temps réel...")
            self.data_manager = RealTimeDataManager(
                binance_client=self.binance_client,
                symbol=TRADING_CONFIG["symbol"],
                timeframe=TRADING_CONFIG["timeframe"]
            )
            
            if not self.data_manager.initialize_data():
                logger.error("❌ Échec initialisation données")
                return False
            
            # 3. Détecteur de signaux
            logger.info("🎯 Initialisation détecteur de signaux...")
            self.signal_detector = LiveSignalDetector(
                config=TRADING_CONFIG,
                filters_config=FILTERS_CONFIG
            )
            
            # 4. Gestionnaire de risque
            logger.info("⚠️ Initialisation gestionnaire de risque...")
            self.risk_manager = LiveRiskManager(
                config=TRADING_CONFIG,
                safety_limits=SAFETY_LIMITS
            )
            
            # Mise à jour du solde initial pour USDC
            balance, error = self.binance_client.get_account_balance("USDC")
            if not error:
                self.risk_manager.update_balance(balance)
                logger.info(f"💰 Solde USDC détecté: {balance:.2f} USDC")
            else:
                logger.warning(f"⚠️ Impossible de récupérer le solde USDC: {error}")
                # Fallback vers USDT
                balance_usdt, error_usdt = self.binance_client.get_account_balance("USDT")
                if not error_usdt:
                    self.risk_manager.update_balance(balance_usdt)
                    logger.info(f"💰 Solde USDT détecté: {balance_usdt:.2f} USDT")
                else:
                    logger.warning(f"⚠️ Impossible de récupérer le solde: {error_usdt}")
            
            # 5. Gestionnaire d'ordres
            logger.info("📋 Initialisation gestionnaire d'ordres...")
            self.order_manager = LiveOrderManager(
                binance_client=self.binance_client,
                config=TRADING_CONFIG
            )
            
            # 6. Système de surveillance
            logger.info("🔍 Initialisation surveillance...")
            self.monitoring = LiveMonitoring(MONITORING_CONFIG)
            self.performance_tracker = PerformanceTracker()
            
            # 7. Configuration des callbacks
            self._setup_callbacks()
            
            self.initialized = True
            logger.info("✅ Moteur initialisé avec succès")
            
            # Test des notifications
            self.monitoring.test_all_notifications()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur initialisation: {e}")
            return False
    
    def _setup_callbacks(self):
        """Configure tous les callbacks entre composants"""
        # Data Manager -> Signal Detector
        self.data_manager.add_candle_closed_callback(
            self.signal_detector.process_new_data
        )
        
        # Signal Detector -> Trade Execution
        self.signal_detector.add_signal_callback(self._on_signal_detected)
        self.signal_detector.add_rsi_detection_callback(self._on_rsi_detected)
        
        # Order Manager -> Monitoring
        self.order_manager.add_trade_opened_callback(self._on_trade_opened)
        self.order_manager.add_trade_closed_callback(self._on_trade_closed)
        
        # Health Monitoring
        self.monitoring.add_health_callback(self._get_health_data)
    
    def start(self) -> bool:
        """Démarre le moteur de trading"""
        if not self.initialized:
            logger.error("❌ Moteur non initialisé")
            return False
        
        if self.running:
            logger.warning("⚠️ Moteur déjà en cours d'exécution")
            return True
        
        try:
            logger.info("🚀 Démarrage du moteur de trading...")
            
            # Mode surveillance ou trading auto
            mode = "AUTO TRADING" if ENVIRONMENT["auto_trade"] else "SURVEILLANCE SEULEMENT"
            logger.info(f"📋 Mode: {mode}")
            
            self.running = True
            
            # Démarrage des composants
            self.data_manager.start_websocket()
            self.monitoring.start_monitoring()
            
            # Démarrage du thread principal
            self.main_thread = threading.Thread(target=self._main_loop)
            self.main_thread.daemon = True
            self.main_thread.start()
            
            # Démarrage du health check
            self.health_check_thread = threading.Thread(target=self._health_check_loop)
            self.health_check_thread.daemon = True
            self.health_check_thread.start()
            
            # Notification de démarrage
            self.monitoring.send_notification(
                f"🚀 Moteur de trading démarré en mode {mode}",
                "SUCCESS"
            )
            
            logger.info("✅ Moteur de trading actif")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur démarrage: {e}")
            self.running = False
            return False
    
    def stop(self, reason: str = "Arrêt manuel"):
        """Arrête le moteur de trading"""
        if not self.running:
            return
        
        logger.info(f"🛑 Arrêt du moteur: {reason}")
        
        try:
            self.running = False
            
            # Fermeture de tous les trades actifs
            if self.order_manager:
                active_count = self.order_manager.close_all_trades(reason)
                if active_count > 0:
                    logger.info(f"🔄 {active_count} trades fermés")
            
            # Arrêt des composants
            if self.data_manager:
                self.data_manager.stop_websocket()
            
            if self.monitoring:
                self.monitoring.stop_monitoring()
            
            # Attendre les threads
            if self.main_thread and self.main_thread.is_alive():
                self.main_thread.join(timeout=10)
            
            if self.health_check_thread and self.health_check_thread.is_alive():
                self.health_check_thread.join(timeout=5)
            
            # Notification d'arrêt
            if self.monitoring:
                self.monitoring.send_notification(
                    f"🛑 Moteur arrêté: {reason}",
                    "WARNING"
                )
            
            logger.info("✅ Moteur arrêté proprement")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'arrêt: {e}")
    
    def _main_loop(self):
        """Boucle principale du moteur"""
        logger.info("🔄 Boucle principale démarrée")
        
        # Gestion du timeout de test
        start_time = time.time()
        max_duration = ENVIRONMENT.get("max_test_duration", 0)
        
        while self.running:
            try:
                # Vérification timeout de test
                if max_duration > 0:
                    elapsed = time.time() - start_time
                    if elapsed > max_duration:
                        logger.info(f"⏰ Durée de test maximale atteinte: {max_duration/3600:.1f}h")
                        self.stop("Timeout de test atteint")
                        break
                
                # Vérification de l'état d'urgence
                if self.emergency_stop:
                    logger.critical("🚨 Mode d'urgence actif")
                    time.sleep(10)
                    continue
                
                # Mise à jour du solde
                self._update_balance()
                
                # Vérifications de sécurité
                self._safety_checks()
                
                time.sleep(1)  # Éviter la surcharge CPU
                
            except Exception as e:
                logger.error(f"❌ Erreur boucle principale: {e}")
                time.sleep(5)
        
        logger.info("🔄 Boucle principale arrêtée")
    
    def _health_check_loop(self):
        """Boucle de vérification de santé système"""
        while self.running:
            try:
                # Vérification des connexions
                api_status = self.binance_client.get_connection_status()
                data_status = self.data_manager.get_connection_status()
                
                # Mise à jour de la santé système
                self.system_health.update({
                    'api_connected': api_status['connected'],
                    'api_latency_ms': api_status.get('latency_ms', 0),
                    'websocket_connected': data_status['websocket_connected'],
                    'data_healthy': self.data_manager.is_healthy(),
                    'last_update': data_status.get('last_update'),
                    'active_trades': len(self.order_manager.active_trades) if self.order_manager else 0
                })
                
                # Vérification d'urgence
                if not api_status['connected']:
                    self._trigger_emergency("Perte connexion API")
                elif not data_status['websocket_connected']:
                    logger.warning("⚠️ WebSocket déconnecté")
                
                time.sleep(30)  # Check toutes les 30 secondes
                
            except Exception as e:
                logger.error(f"❌ Erreur health check: {e}")
                time.sleep(30)
    
    def _on_signal_detected(self, signal):
        """Callback appelé lors de la détection d'un signal"""
        try:
            logger.info(f"🎯 Signal {signal.direction} détecté")
            
            self.last_signal = signal
            
            # Notification
            self.monitoring.notify_signal_detected(signal)
            
            # Si mode auto trading, exécuter le trade
            if ENVIRONMENT["auto_trade"]:
                self._execute_signal(signal)
            else:
                logger.info("📋 Mode surveillance - Signal non exécuté")
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement signal: {e}")
    
    def _on_rsi_detected(self, direction: str, timestamp: datetime, indicators: Dict):
        """Callback appelé lors de la détection RSI"""
        logger.info(f"📊 RSI {direction} détecté - En attente de confirmation")
    
    def _execute_signal(self, signal):
        """Exécute un signal de trading avec SL/TP corrigés et formatés"""
        try:
            # 🆕 VÉRIFICATION CRITIQUE: Pas de nouveau trade si un trade est déjà actif
            active_trades_count = len(self.order_manager.active_trades)
            if active_trades_count > 0:
                logger.warning(f"❌ Signal {signal.direction} ignoré - {active_trades_count} trade(s) déjà actif(s)")
                active_trade_ids = list(self.order_manager.active_trades.keys())
                logger.info(f"   Trades actifs: {active_trade_ids}")
                return
            
            # Validation du risque
            can_trade, reason = self.risk_manager.validate_trade(signal.confidence)
            if not can_trade:
                logger.warning(f"❌ Trade refusé: {reason}")
                return
            
            # 🔍 DIAGNOSTIC COMPLET SL - LONG ET SHORT
            current_price = signal.indicators.get('close', 0)
            
            logger.info(f"🔍 === DIAGNOSTIC SL {signal.direction} ===")
            logger.info(f"🔍 signal.indicators keys: {list(signal.indicators.keys())}")
            logger.info(f"🔍 current_price (close): {current_price}")
            logger.info(f"🔍 HA_high raw: {signal.indicators.get('HA_high')}")
            logger.info(f"🔍 HA_low raw: {signal.indicators.get('HA_low')}")
            logger.info(f"🔍 high raw: {signal.indicators.get('high')}")
            logger.info(f"🔍 low raw: {signal.indicators.get('low')}")
            
            # 🔧 CALCUL SL CORRIGÉ avec buffer ET formatage
            if signal.direction == "LONG":
                # DIAGNOSTIC LONG
                ha_low_value = signal.indicators.get('HA_low')
                fallback_value = current_price * 0.99
                
                logger.info(f"🔍 LONG - HA_low exists: {ha_low_value is not None}")
                logger.info(f"🔍 LONG - HA_low value: {ha_low_value}")
                logger.info(f"🔍 LONG - Fallback value: {fallback_value}")
                
                # Calcul avec buffer
                ha_low = signal.indicators.get('HA_low', fallback_value)
                stop_loss_raw = ha_low * (1 - TRADING_CONFIG.get('sl_buffer_pct', 0.001))
                
                # 🆕 FORMATAGE BINANCE
                stop_loss = self.binance_client.format_price(stop_loss_raw, TRADING_CONFIG["symbol"])
                
                logger.info(f"🔍 LONG - SL avant buffer: {ha_low}")
                logger.info(f"🔍 LONG - SL avec buffer: {stop_loss_raw}")
                logger.info(f"🔍 LONG - SL formaté final: {stop_loss}")
                
            else:  # SHORT
                # DIAGNOSTIC SHORT
                ha_high_value = signal.indicators.get('HA_high')
                fallback_value = current_price * 1.01
                
                logger.info(f"🔍 SHORT - HA_high exists: {ha_high_value is not None}")
                logger.info(f"🔍 SHORT - HA_high value: {ha_high_value}")
                logger.info(f"🔍 SHORT - Fallback value: {fallback_value}")
                
                # Calcul avec buffer
                ha_high = signal.indicators.get('HA_high', fallback_value)
                stop_loss_raw = ha_high * (1 + TRADING_CONFIG.get('sl_buffer_pct', 0.001))
                
                # 🆕 FORMATAGE BINANCE
                stop_loss = self.binance_client.format_price(stop_loss_raw, TRADING_CONFIG["symbol"])
                
                logger.info(f"🔍 SHORT - SL avant buffer: {ha_high}")
                logger.info(f"🔍 SHORT - SL avec buffer: {stop_loss_raw}")
                logger.info(f"🔍 SHORT - SL formaté final: {stop_loss}")
            
            logger.info(f"🔍 === FIN DIAGNOSTIC SL ===")
            
            # Calcul de la taille de position avec SL corrigé
            position_size = self.risk_manager.calculate_position_size(
                entry_price=current_price,
                stop_loss=stop_loss,
                direction=signal.direction
            )
            
            if not position_size:
                logger.warning("❌ Impossible de calculer la taille de position")
                return
            
            # 🔍 DIAGNOSTIC POSITION SIZE
            logger.info(f"🔍 === DIAGNOSTIC POSITION ===")
            logger.info(f"🔍 Entry price utilisé: {current_price}")
            logger.info(f"🔍 Stop loss utilisé: {stop_loss}")
            logger.info(f"🔍 Direction: {signal.direction}")
            logger.info(f"🔍 Position calculée - SL: {position_size.stop_loss}")
            logger.info(f"🔍 Position calculée - TP: {position_size.take_profit}")
            logger.info(f"🔍 Distance SL: {abs(current_price - stop_loss):.1f} USDT")
            logger.info(f"🔍 === FIN DIAGNOSTIC POSITION ===")
            
            # Création du trade
            trade_id = self.order_manager.create_trade(
                symbol=TRADING_CONFIG["symbol"],
                direction=signal.direction,
                position_size=position_size
            )
            
            if trade_id:
                logger.info(f"✅ Trade créé: {trade_id}")
                # 🆕 RESET du signal detector après création réussie
                self.signal_detector.reset_pending_signals()
            else:
                logger.error("❌ Échec création trade")
            
        except Exception as e:
            logger.error(f"❌ Erreur exécution signal: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    def _on_trade_opened(self, trade):
        """Callback appelé quand un trade s'ouvre"""
        logger.info(f"🚀 Trade ouvert: {trade.trade_id}")
        self.monitoring.notify_trade_opened(trade)
        self.performance_tracker.record_trade({
            'direction': trade.direction,
            'entry_price': trade.entry_price,
            'quantity': trade.quantity
        })
    
    def _on_trade_closed(self, trade):
        """Callback appelé quand un trade se ferme"""
        logger.info(f"🏁 Trade fermé: {trade.trade_id} - PnL: {trade.pnl:+.2f}")
        
        # Mise à jour du risk manager
        self.risk_manager.record_trade(
            direction=trade.direction,
            entry_price=trade.entry_price,
            quantity=trade.quantity,
            result="win" if trade.pnl > 0 else "loss",
            pnl=trade.pnl
        )
        
        # Notification
        self.monitoring.notify_trade_closed(trade)
        
        # Tracking performance
        self.performance_tracker.record_trade({
            'direction': trade.direction,
            'entry_price': trade.entry_price,
            'exit_price': trade.exit_price,
            'quantity': trade.quantity,
            'pnl': trade.pnl,
            'result': "win" if trade.pnl > 0 else "loss"
        })
    
    def _update_balance(self):
        """Met à jour le solde du compte"""
        try:
            # Récupération du solde USDC pour BTCUSDC
            balance, error = self.binance_client.get_account_balance("USDC")
            if not error:
                self.risk_manager.update_balance(balance)
                self.system_health['balance'] = balance
                self.system_health['currency'] = 'USDC'
            else:
                # Fallback vers USDT si USDC échoue
                balance_usdt, error_usdt = self.binance_client.get_account_balance("USDT")
                if not error_usdt:
                    self.risk_manager.update_balance(balance_usdt)
                    self.system_health['balance'] = balance_usdt
                    self.system_health['currency'] = 'USDT'
            
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour solde: {e}")
    
    def _safety_checks(self):
        """Vérifications de sécurité périodiques"""
        # Vérification des limites du risk manager
        if self.risk_manager.emergency_stop and not self.emergency_stop:
            self._trigger_emergency(self.risk_manager.stop_reason)
    
    def _trigger_emergency(self, reason: str):
        """Déclenche l'arrêt d'urgence"""
        if self.emergency_stop:
            return
        
        self.emergency_stop = True
        logger.critical(f"🚨 ARRÊT D'URGENCE: {reason}")
        
        # Fermeture de tous les trades
        if self.order_manager:
            self.order_manager.close_all_trades(f"Emergency: {reason}")
        
        # Notification
        if self.monitoring:
            self.monitoring.notify_emergency_stop(reason)
    
    def _get_health_data(self) -> Dict:
        """Retourne les données de santé avec détection des trades multiples"""
        active_trades_count = len(self.order_manager.active_trades) if self.order_manager else 0
        
        health_data = {
            **self.system_health,
            'engine_running': self.running,
            'emergency_stop': self.emergency_stop,
            'active_trades_count': active_trades_count,
            'last_signal': self.last_signal.timestamp if self.last_signal else None,
            **self.performance_tracker.get_daily_stats(),
            **self.performance_tracker.get_system_stats()
        }
        
        # 🚨 ALERTE si plusieurs trades actifs
        if active_trades_count > 1:
            logger.critical(f"🚨 PROBLÈME DÉTECTÉ: {active_trades_count} trades actifs simultanément !")
            active_trade_ids = list(self.order_manager.active_trades.keys())
            logger.critical(f"🚨 Trades actifs: {active_trade_ids}")
            
            # Notification d'urgence
            if self.monitoring:
                self.monitoring.send_notification(
                    f"🚨 ALERTE: {active_trades_count} trades actifs simultanément !",
                    "CRITICAL"
                )
        
        return health_data
    
    def _signal_handler(self, signum, frame):
        """Gestionnaire de signaux pour arrêt propre"""
        logger.info(f"📧 Signal reçu: {signum}")
        self.stop("Signal système")
        sys.exit(0)
    
    def get_status_report(self) -> str:
        """Génère un rapport de statut complet"""
        status = "🟢 ACTIF" if self.running else "🔴 ARRÊTÉ"
        if self.emergency_stop:
            status = "🚨 URGENCE"
        
        # Stats de performance
        daily_stats = self.performance_tracker.get_daily_stats()
        system_stats = self.performance_tracker.get_system_stats()
        
        # État des trades
        trades_summary = self.order_manager.get_active_trades_summary() if self.order_manager else {}
        
        currency = self.system_health.get('currency', 'USDT')
        
        report = f"""
🤖 TRADING BOT - {status}
⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

💰 FINANCIAL:
• Balance: {self.system_health.get('balance', 0):.2f} {currency}
• PnL Jour: {daily_stats.get('daily_pnl', 0):+.2f} {currency}
• Trades Jour: {daily_stats.get('daily_trades', 0)}
• Trades Actifs: {trades_summary.get('total_active', 0)}

🔧 SYSTÈME:
• Uptime: {system_stats.get('uptime', 'N/A')}
• API: {"✅" if self.system_health.get('api_connected', False) else "❌"}
• WebSocket: {"✅" if self.system_health.get('websocket_connected', False) else "❌"}
• Latence: {self.system_health.get('api_latency_ms', 0)}ms

📊 PERFORMANCE:
• Winrate: {daily_stats.get('winrate', 0):.1f}%
• Wins/Losses: {daily_stats.get('wins', 0)}/{daily_stats.get('losses', 0)}
• Erreurs API: {system_stats.get('errors_count', 0)}
        """.strip()
        
        return report
    
    def manual_override_emergency(self, reason: str) -> bool:
        """Override manuel de l'arrêt d'urgence"""
        if not self.emergency_stop:
            return False
        
        try:
            self.emergency_stop = False
            
            # Reset du risk manager
            if self.risk_manager:
                self.risk_manager.override_emergency_stop(reason)
            
            logger.warning(f"⚠️ Override d'urgence: {reason}")
            
            if self.monitoring:
                self.monitoring.send_notification(
                    f"⚠️ Override d'urgence manuel: {reason}",
                    "WARNING"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur override: {e}")
            return False
    
    def manual_close_trade(self, trade_id: str) -> bool:
        """Fermeture manuelle d'un trade"""
        if not self.order_manager:
            return False
        
        return self.order_manager.close_trade_manually(trade_id, "Manuel")
    
    def manual_signal_reset(self):
        """Reset manuel des signaux pending"""
        if self.signal_detector:
            self.signal_detector.reset_pending_signals()
            logger.info("🔄 Signaux pending réinitialisés manuellement")

# Fonction utilitaire pour démarrage simplifié
def create_and_run_engine():
    """Crée et démarre le moteur de trading"""
    engine = LiveTradingEngine()
    
    if not engine.initialize():
        logger.error("❌ Échec d'initialisation")
        return None
    
    if not engine.start():
        logger.error("❌ Échec de démarrage")
        return None
    
    return engine