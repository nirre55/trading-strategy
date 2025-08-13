"""
Module pour la gestion retardée des ordres Stop Loss et Take Profit
Attend la fermeture de la bougie d'entrée + applique des offsets dynamiques
"""
import time
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, TYPE_CHECKING
import pytz  # Ajouter cette ligne - installer avec: pip install pytz
import config
from trading_logger import trading_logger

if TYPE_CHECKING:
    from trade_executor import TradeExecutor
    from binance_client import BinanceClient


class DelayedSLTPManager:
    def __init__(self, trade_executor: 'TradeExecutor', binance_client: Optional['BinanceClient']):
        """
        Initialise le gestionnaire de SL/TP retardés
        CORRIGÉ: Ajout d'un lock pour thread safety
        
        Args:
            trade_executor: Instance de TradeExecutor
            binance_client: Instance de BinanceClient
        """
        import threading
        
        self.trade_executor = trade_executor
        self.binance_client = binance_client
        
        # Trades en attente de SL/TP
        self.pending_trades: Dict[str, Dict] = {}
        
        # NOUVEAU: Lock pour éviter les race conditions
        self.processing_lock = threading.Lock()
        
        # Thread de monitoring
        self.monitoring_active = False
        self.monitoring_thread = None
        
        # Configuration depuis config
        self.offset_percent = config.DELAYED_SLTP_CONFIG.get('PRICE_OFFSET_PERCENT', 0.01)
        self.check_interval = config.DELAYED_SLTP_CONFIG.get('CHECK_INTERVAL_SECONDS', 10)
        
        print("✅ DelayedSLTPManager initialisé avec protection thread-safe")
        trading_logger.info("DelayedSLTPManager initialisé avec thread lock")
    
    def register_trade_for_delayed_sltp(self, trade_result, entry_candle_time, original_sl_price, original_tp_price):
        """
        Enregistre un trade pour placement retardé des SL/TP
        CORRIGÉ: Gestion appropriée des timezones UTC/Local avec config
        
        Args:
            trade_result: Résultat du trade
            entry_candle_time: Timestamp de la bougie d'entrée (depuis Binance en UTC)
            original_sl_price: Prix SL calculé original
            original_tp_price: Prix TP calculé original
        """
        try:
            from datetime import timezone
            import pytz
            
            trade_id = trade_result['trade_id']
            
            # Obtenir les timezones depuis config
            binance_tz_str = config.TIMEZONE_CONFIG.get('BINANCE_TIMEZONE', 'UTC')
            local_tz_str = config.TIMEZONE_CONFIG.get('LOCAL_TIMEZONE', 'America/Toronto')
            
            # Créer les objets timezone
            binance_tz = pytz.UTC if binance_tz_str == 'UTC' else pytz.timezone(binance_tz_str)
            local_tz = pytz.timezone(local_tz_str)
            
            # 1. Gérer le timestamp d'entrée correctement (toujours en UTC depuis Binance)
            if entry_candle_time is None:
                # Si pas de timestamp fourni, utiliser maintenant en UTC
                entry_utc = datetime.now(binance_tz)
            elif isinstance(entry_candle_time, datetime):
                # Si c'est un datetime, s'assurer qu'il est en UTC
                if entry_candle_time.tzinfo is None:
                    # Pas de timezone, assumer que c'est en timezone Binance
                    entry_utc = binance_tz.localize(entry_candle_time)
                else:
                    # Convertir en UTC si nécessaire
                    entry_utc = entry_candle_time.astimezone(binance_tz)
            elif hasattr(entry_candle_time, 'timestamp'):
                # Si c'est un pandas Timestamp
                entry_utc = datetime.fromtimestamp(entry_candle_time.timestamp(), tz=binance_tz)
            else:
                # Essayer de traiter comme un timestamp unix
                try:
                    entry_utc = datetime.fromtimestamp(float(entry_candle_time), tz=binance_tz)
                except:
                    # Fallback sur maintenant
                    entry_utc = datetime.now(binance_tz)
                    print(f"⚠️ Impossible de parser entry_candle_time, utilisation de maintenant ({binance_tz_str})")
            
            # 2. Calculer la fin de la bougie en UTC
            timeframe = config.ASSET_CONFIG['TIMEFRAME']
            candle_duration = self._get_candle_duration_seconds(timeframe)
            end_of_candle_utc = entry_utc + timedelta(seconds=candle_duration)
            
            # 3. Obtenir l'heure actuelle en UTC pour comparaison
            now_utc = datetime.now(binance_tz)
            
            # 4. Calculer le temps d'attente réel
            time_to_wait = (end_of_candle_utc - now_utc).total_seconds()
            
            # 5. Pour l'affichage, convertir en heure locale
            try:
                entry_local = entry_utc.astimezone(local_tz)
                end_of_candle_local = end_of_candle_utc.astimezone(local_tz)
                now_local = now_utc.astimezone(local_tz)
            except Exception as tz_error:
                # Fallback sur UTC si problème avec timezone local
                print(f"⚠️ Erreur conversion timezone local: {tz_error}")
                local_tz = binance_tz
                entry_local = entry_utc
                end_of_candle_local = end_of_candle_utc
                now_local = now_utc
            
            print(f"📅 Enregistrement trade {trade_id} pour SL/TP retardé:")
            print(f"   Timezone Binance: {binance_tz_str}")
            print(f"   Timezone Local: {local_tz_str}")
            print(f"   Timestamp entrée {binance_tz_str}: {entry_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print(f"   Timestamp entrée Local: {entry_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print(f"   Fin bougie {binance_tz_str}: {end_of_candle_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print(f"   Fin bougie Local: {end_of_candle_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print(f"   Maintenant Local: {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print(f"   Timeframe: {timeframe} ({candle_duration}s)")
            print(f"   Temps d'attente: {time_to_wait:.0f}s")
            
            # Vérification de cohérence
            if time_to_wait < 0:
                print(f"⚠️ La bougie est déjà fermée (attente: {time_to_wait:.0f}s)")
                # Traiter immédiatement ou attendre la prochaine bougie
                if abs(time_to_wait) > candle_duration:
                    # Trop en retard, abandonner
                    print(f"❌ Bougie trop ancienne, abandon du SL/TP retardé")
                    return False
                else:
                    # Juste un peu en retard, traiter immédiatement
                    end_of_candle_utc = now_utc + timedelta(seconds=5)  # Délai minimal
                    print(f"🔄 Traitement dans 5 secondes")
            
            # 6. Stocker les informations avec timestamps UTC
            self.pending_trades[trade_id] = {
                'trade_result': trade_result,
                'entry_candle_time_utc': entry_utc,
                'end_of_candle_time_utc': end_of_candle_utc,
                'original_sl_price': original_sl_price,
                'original_tp_price': original_tp_price,
                'sl_tp_placed': False,
                'processing_started': None,
                'registration_time_utc': now_utc,
                'timeframe': timeframe,
                'candle_duration': candle_duration
            }
            
            print(f"✅ Trade {trade_id} enregistré avec succès")
            trading_logger.info(f"Trade {trade_id} SL/TP retardé jusqu'à {end_of_candle_local.strftime('%H:%M:%S %Z')}")
            
            # 7. Démarrer le monitoring si nécessaire
            if not self.monitoring_active:
                self.start_monitoring()
            
            return True
            
        except Exception as e:
            error_msg = f"Erreur enregistrement trade retardé: {str(e)}"
            print(f"❌ {error_msg}")
            trading_logger.error_occurred("DELAYED_SLTP_REGISTER", error_msg)
            import traceback
            traceback.print_exc()
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
        """
        Boucle principale de monitoring
        CORRIGÉ: Réduit les messages répétitifs
        """
        from datetime import timezone
        print("🔄 Boucle monitoring SL/TP retardé active")
        
        last_cleanup_log = {}  # Pour éviter spam des logs
        
        while self.monitoring_active:
            try:
                current_time_utc = datetime.now(timezone.utc)
                trades_to_process = []
                
                # Identifier les trades prêts à être traités
                for trade_id, trade_info in self.pending_trades.items():
                    if not trade_info['sl_tp_placed']:
                        end_time_utc = trade_info['end_of_candle_time_utc']
                        
                        if end_time_utc.tzinfo is None:
                            end_time_utc = end_time_utc.replace(tzinfo=timezone.utc)
                        
                        if current_time_utc >= end_time_utc:
                            time_elapsed = (current_time_utc - end_time_utc).total_seconds()
                            print(f"⏰ Trade {trade_id} prêt (retard: {time_elapsed:.0f}s)")
                            trades_to_process.append(trade_id)
                
                # Traiter les trades prêts
                for trade_id in trades_to_process:
                    print(f"🔄 Traitement du trade {trade_id}")
                    self._process_delayed_trade(trade_id)
                
                # Nettoyer avec limitation de logs
                self._cleanup_completed_trades_quiet()
                
                # Log périodique (1 fois par minute au lieu de toutes les 10s)
                if len(self.pending_trades) > 0 and int(time.time()) % 60 == 0:
                    active_count = sum(1 for t in self.pending_trades.values() 
                                    if not t.get('position_closed', False))
                    if active_count > 0:
                        print(f"📊 Monitoring: {active_count} trades actifs")
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                error_msg = f"Erreur boucle monitoring SL/TP: {str(e)}"
                print(f"❌ {error_msg}")
                trading_logger.error_occurred("DELAYED_SLTP_MONITORING", error_msg)
                time.sleep(30)
        
        print("🛑 Monitoring SL/TP retardé arrêté")

    def _cleanup_completed_trades_quiet(self):
        """
        Version silencieuse du cleanup (sans spam de logs)
        """
        try:
            from datetime import timezone
            
            current_time_utc = datetime.now(timezone.utc)
            cleanup_hours = config.DELAYED_SLTP_CONFIG.get('AUTO_CLEANUP_HOURS', 24)
            cleanup_threshold = timedelta(hours=cleanup_hours)
            
            trades_to_remove = []
            
            for trade_id, trade_info in self.pending_trades.items():
                # Ne nettoyer que les trades confirmés fermés
                if not trade_info.get('position_closed', False):
                    continue
                
                if not trade_info.get('sl_tp_placed', False):
                    continue
                
                time_to_check = trade_info.get('placement_time') or trade_info.get('registration_time_utc')
                
                if time_to_check:
                    if time_to_check.tzinfo is None:
                        time_to_check = time_to_check.replace(tzinfo=timezone.utc)
                    
                    time_elapsed = current_time_utc - time_to_check
                    
                    if time_elapsed > cleanup_threshold:
                        trades_to_remove.append(trade_id)
            
            # Supprimer silencieusement
            for trade_id in trades_to_remove:
                del self.pending_trades[trade_id]
                # Log seulement dans le fichier, pas dans la console
                trading_logger.info(f"Trade retardé {trade_id} nettoyé (position fermée)")
                
        except Exception:
            pass  # Silencieux en cas d'erreur
    
    
    def _process_delayed_trade(self, trade_id):
        """
        Traite un trade dont la bougie d'entrée est fermée
        CORRIGÉ: Protection thread-safe contre double exécution
        
        Args:
            trade_id: ID du trade à traiter
        """
        import threading
        from datetime import timezone
        
        # Phase 1: Vérifications et marquage sous lock
        with self.processing_lock:
            # Vérifier existence du trade
            if trade_id not in self.pending_trades:
                print(f"⚠️ Trade {trade_id} non trouvé")
                return
            
            trade_info = self.pending_trades[trade_id]
            
            # Vérifier si déjà traité
            if trade_info.get('sl_tp_placed', False):
                print(f"⚠️ Trade {trade_id} déjà traité - Skip")
                return
            
            # Vérifier si en cours de traitement
            if trade_info.get('processing_started'):
                processing_time = trade_info['processing_started']
                # S'assurer que processing_time a un timezone
                if processing_time.tzinfo is None:
                    processing_time = processing_time.replace(tzinfo=timezone.utc)
                
                now_utc = datetime.now(timezone.utc)
                elapsed = (now_utc - processing_time).total_seconds()
                
                if elapsed < 30:  # Moins de 30 secondes
                    print(f"⚠️ Trade {trade_id} en cours de traitement depuis {elapsed:.0f}s - Skip")
                    return
                else:
                    # Traitement bloqué depuis trop longtemps
                    print(f"⚠️ Trade {trade_id} bloqué depuis {elapsed:.0f}s - Reset et retry")
                    trade_info.pop('processing_started', None)
                    # Ne pas continuer cette fois-ci, laisser le prochain cycle le prendre
                    return
            
            # Marquer comme en cours de traitement
            trade_info['processing_started'] = datetime.now(timezone.utc)
            print(f"🔒 Trade {trade_id} verrouillé pour traitement")
            
            # Copier les infos nécessaires pour traitement hors lock
            trade_result = trade_info['trade_result'].copy()
            original_sl_price = trade_info['original_sl_price']
            original_tp_price = trade_info['original_tp_price']
        
        # Phase 2: Traitement (hors du lock pour ne pas bloquer)
        success = False
        adjusted_sl_price = None
        adjusted_tp_price = None
        error_occurred = False
        error_message = "Erreur inconnue"  # Variable pour stocker le message d'erreur
        
        try:
            print(f"\n🕐 TRAITEMENT TRADE RETARDÉ: {trade_id}")
            print(f"   Bougie d'entrée fermée, placement SL/TP...")
            
            # Récupérer le prix actuel
            current_price = self.trade_executor.get_current_price()
            if not current_price:
                raise ValueError(f"Impossible de récupérer le prix actuel")
            
            print(f"📊 Prix actuel: {current_price}")
            print(f"📊 Prix d'entrée: {trade_result['entry_price']}")
            
            # Calculer les prix SL/TP avec offsets si nécessaire
            # (utiliser trade_info temporaire pour les calculs)
            temp_trade_info = {
                'original_sl_price': original_sl_price,
                'original_tp_price': original_tp_price
            }
            
            adjusted_sl_price = self._calculate_adjusted_sl_price(
                temp_trade_info, current_price, trade_result
            )
            
            adjusted_tp_price = self._calculate_adjusted_tp_price(
                temp_trade_info, current_price, trade_result
            )
            
            if not adjusted_sl_price or not adjusted_tp_price:
                raise ValueError(f"Impossible de calculer SL/TP ajustés")
            
            # Placement des ordres
            success = self._place_delayed_orders(
                trade_id, trade_result, adjusted_sl_price, adjusted_tp_price
            )
            
            if success:
                print(f"✅ SL/TP retardés placés avec succès pour {trade_id}")
                trading_logger.info(f"SL/TP retardés placés pour {trade_id} - SL: {adjusted_sl_price}, TP: {adjusted_tp_price}")
            else:
                raise ValueError(f"Échec placement ordres SL/TP")
                
        except Exception as e:
            error_occurred = True
            error_message = str(e)  # Capturer le message d'erreur
            error_msg = f"Erreur traitement trade retardé {trade_id}: {error_message}"
            print(f"❌ {error_msg}")
            trading_logger.error_occurred("DELAYED_SLTP_PROCESS", error_msg)
            import traceback
            traceback.print_exc()
        
        # Phase 3: Mise à jour finale sous lock
        with self.processing_lock:
            if trade_id not in self.pending_trades:
                print(f"⚠️ Trade {trade_id} disparu pendant le traitement")
                return
            
            trade_info = self.pending_trades[trade_id]
            
            if success:
                # Marquer comme terminé
                trade_info['sl_tp_placed'] = True
                trade_info['final_sl_price'] = adjusted_sl_price
                trade_info['final_tp_price'] = adjusted_tp_price
                trade_info['placement_time'] = datetime.now(timezone.utc)
                trade_info.pop('processing_started', None)  # Retirer le flag de traitement
                print(f"🔓 Trade {trade_id} déverrouillé - Traitement réussi")
                
            elif error_occurred:
                # Rollback en cas d'erreur
                trade_info.pop('processing_started', None)
                trade_info['sl_tp_placed'] = False
                trade_info['last_error'] = error_message  # Utiliser la variable capturée
                trade_info['last_error_time'] = datetime.now(timezone.utc)
                print(f"🔓 Trade {trade_id} déverrouillé - Erreur: {error_message}")
                print(f"   Le trade sera retenté au prochain cycle")
            else:
                # Cas imprévu
                trade_info.pop('processing_started', None)
                print(f"🔓 Trade {trade_id} déverrouillé - État indéterminé")
    
    def _calculate_adjusted_sl_price(self, trade_info, current_price, trade_result):
        """
        Calcule le prix SL ajusté avec offset si nécessaire
        CORRIGÉ: Protection contre SL qui déclencherait immédiatement
        
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
                sl_breached = current_price <= original_sl
            else:  # SHORT
                # Pour SHORT: SL déclenché si prix actuel > SL original
                sl_breached = current_price >= original_sl
            
            if sl_breached:
                # Appliquer l'offset pour compenser le dépassement
                offset_percent = self.offset_percent
                
                # PROTECTION: Augmenter l'offset si trop proche
                min_distance_percent = 0.05  # Distance minimale 0.05%
                
                if side == 'LONG':
                    # Pour LONG: SL plus bas avec offset
                    base_offset = current_price * offset_percent / 100
                    min_distance = current_price * min_distance_percent / 100
                    
                    # Utiliser le plus grand entre offset configuré et distance minimale
                    actual_offset = max(base_offset, min_distance)
                    
                    adjusted_sl = current_price - actual_offset
                    print(f"   ⚠️ SL original dépassé!")
                    print(f"   Prix actuel: {current_price}")
                    print(f"   Offset appliqué: {actual_offset:.6f} ({actual_offset/current_price*100:.3f}%)")
                    print(f"   Nouveau SL: {adjusted_sl}")
                    
                else:  # SHORT
                    # Pour SHORT: SL plus haut avec offset
                    base_offset = current_price * offset_percent / 100
                    min_distance = current_price * min_distance_percent / 100
                    
                    # Utiliser le plus grand entre offset configuré et distance minimale
                    actual_offset = max(base_offset, min_distance)
                    
                    adjusted_sl = current_price + actual_offset
                    print(f"   ⚠️ SL original dépassé!")
                    print(f"   Prix actuel: {current_price}")
                    print(f"   Offset appliqué: {actual_offset:.6f} ({actual_offset/current_price*100:.3f}%)")
                    print(f"   Nouveau SL: {adjusted_sl}")
                
                trading_logger.warning(f"SL original dépassé pour trade - Offset appliqué: {actual_offset/current_price*100:.3f}%")
                
            else:
                # Prix n'a pas dépassé le SL, vérifier quand même la distance
                if side == 'LONG':
                    distance = current_price - original_sl
                    min_distance = current_price * 0.03 / 100  # 0.03% minimum
                    
                    if distance < min_distance:
                        # Trop proche, ajuster
                        adjusted_sl = current_price - min_distance
                        print(f"   ⚠️ SL trop proche du prix actuel")
                        print(f"   Distance: {distance:.6f} < minimum: {min_distance:.6f}")
                        print(f"   SL ajusté: {adjusted_sl}")
                    else:
                        adjusted_sl = original_sl
                        print(f"   ✅ SL original respecté: {adjusted_sl}")
                        
                else:  # SHORT
                    distance = original_sl - current_price
                    min_distance = current_price * 0.03 / 100  # 0.03% minimum
                    
                    if distance < min_distance:
                        # Trop proche, ajuster
                        adjusted_sl = current_price + min_distance
                        print(f"   ⚠️ SL trop proche du prix actuel")
                        print(f"   Distance: {distance:.6f} < minimum: {min_distance:.6f}")
                        print(f"   SL ajusté: {adjusted_sl}")
                    else:
                        adjusted_sl = original_sl
                        print(f"   ✅ SL original respecté: {adjusted_sl}")
            
            # Formater selon les règles du symbole
            formatted_sl = self.trade_executor.position_manager.format_price(adjusted_sl)
            print(f"   📐 SL final formaté: {formatted_sl}")
            
            # Validation finale
            if side == 'LONG':
                if formatted_sl >= current_price:
                    print(f"   ❌ ERREUR: SL LONG {formatted_sl} >= prix actuel {current_price}")
                    # Forcer un SL valide
                    formatted_sl = self.trade_executor.position_manager.format_price(current_price * 0.995)
                    print(f"   🔧 SL forcé à: {formatted_sl}")
            else:  # SHORT
                if formatted_sl <= current_price:
                    print(f"   ❌ ERREUR: SL SHORT {formatted_sl} <= prix actuel {current_price}")
                    # Forcer un SL valide
                    formatted_sl = self.trade_executor.position_manager.format_price(current_price * 1.005)
                    print(f"   🔧 SL forcé à: {formatted_sl}")
            
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
        """
        Nettoie UNIQUEMENT les trades sans position active
        CORRIGÉ: Ne nettoie jamais un trade avec position ouverte
        """
        try:
            from datetime import timezone
            
            current_time_utc = datetime.now(timezone.utc)
            cleanup_hours = config.DELAYED_SLTP_CONFIG.get('AUTO_CLEANUP_HOURS', 24)
            cleanup_threshold = timedelta(hours=cleanup_hours)
            
            trades_to_remove = []
            
            for trade_id, trade_info in self.pending_trades.items():
                # IMPORTANT: Ne nettoyer que si SL/TP placés ET position fermée
                if not trade_info.get('sl_tp_placed', False):
                    # SL/TP pas encore placés, ne pas nettoyer
                    continue
                
                # NOUVEAU: Vérifier si le trade est toujours actif
                if self._is_trade_still_active(trade_id, trade_info):
                    if config.DELAYED_SLTP_CONFIG.get('LOG_DETAILED_CALCULATIONS', False):
                        print(f"⚠️ Trade {trade_id} a toujours une position active - skip cleanup")
                    continue
                
                # Vérifier l'âge du trade
                time_to_check = trade_info.get('placement_time')
                
                if time_to_check is None:
                    time_to_check = trade_info.get('registration_time_utc')
                
                if time_to_check is None:
                    print(f"⚠️ Trade {trade_id} sans timestamp - skip cleanup")
                    continue
                
                # S'assurer que le timestamp a un timezone
                if time_to_check.tzinfo is None:
                    time_to_check = time_to_check.replace(tzinfo=timezone.utc)
                
                # Calculer le temps écoulé
                time_elapsed = current_time_utc - time_to_check
                
                if time_elapsed > cleanup_threshold:
                    # Double vérification avant suppression
                    if self._verify_safe_to_cleanup(trade_id, trade_info):
                        trades_to_remove.append(trade_id)
                        if config.DELAYED_SLTP_CONFIG.get('LOG_DETAILED_CALCULATIONS', False):
                            print(f"🧹 Trade {trade_id} marqué pour nettoyage (âge: {time_elapsed.total_seconds()/3600:.1f}h)")
                    else:
                        print(f"⚠️ Trade {trade_id} ne peut pas être nettoyé - position potentiellement active")
            
            # Supprimer les trades marqués
            for trade_id in trades_to_remove:
                del self.pending_trades[trade_id]
                print(f"🧹 Trade retardé nettoyé: {trade_id}")
                trading_logger.info(f"Trade retardé {trade_id} nettoyé après expiration (position fermée)")
                
        except Exception as e:
            error_msg = f"Erreur nettoyage trades retardés: {str(e)}"
            print(f"❌ {error_msg}")
            trading_logger.error_occurred("DELAYED_CLEANUP", error_msg)
            import traceback
            if config.DELAYED_SLTP_CONFIG.get('LOG_DETAILED_CALCULATIONS', False):
                traceback.print_exc()

    def _is_trade_still_active(self, trade_id, trade_info):
        """
        Vérifie si un trade a toujours une position ouverte
        CORRIGÉ: Évite les vérifications répétitives
        """
        try:
            # Si déjà marqué comme fermé, retourner False
            if trade_info.get('position_closed', False):
                return False
            
            # Si on a une raison de fermeture, c'est fermé
            if trade_info.get('close_reason'):
                return False
            
            # Vérifier dans les trades actifs du TradeExecutor
            if hasattr(self.trade_executor, 'active_trades'):
                if trade_id in self.trade_executor.active_trades:
                    executor_trade = self.trade_executor.active_trades[trade_id]
                    # Si le trade est marqué comme fermé
                    if executor_trade.get('status') == 'CLOSED':
                        # Marquer aussi dans notre registre
                        trade_info['position_closed'] = True
                        return False
                    return True
                else:
                    # Trade n'existe plus dans active_trades = fermé
                    trade_info['position_closed'] = True
                    return False
            
            # Si on a des IDs d'ordres mais pas de confirmation de fermeture
            if trade_info.get('stop_loss_order_id') or trade_info.get('take_profit_order_id'):
                # Considérer comme potentiellement actif seulement si récent
                from datetime import timezone
                placement_time = trade_info.get('placement_time')
                if placement_time:
                    if placement_time.tzinfo is None:
                        placement_time = placement_time.replace(tzinfo=timezone.utc)
                    
                    now_utc = datetime.now(timezone.utc)
                    age_hours = (now_utc - placement_time).total_seconds() / 3600
                    
                    # Si plus de 4h et pas de confirmation, considérer comme fermé
                    if age_hours > 4:
                        trade_info['position_closed'] = True
                        return False
                
                return True
            
            return False
            
        except Exception as e:
            print(f"⚠️ Erreur vérification trade actif {trade_id}: {e}")
            # En cas d'erreur, considérer comme fermé pour permettre cleanup
            return False

    def _verify_safe_to_cleanup(self, trade_id, trade_info):
        """
        Double vérification avant nettoyage
        """
        try:
            # Ne jamais nettoyer si pas de confirmation de fermeture
            if not trade_info.get('position_closed', False):
                # Si le champ n'existe pas, le trade pourrait être actif
                return False
            
            # Si on a une confirmation explicite de fermeture
            if trade_info.get('close_reason'):
                return True
            
            # Par défaut, ne pas nettoyer
            return False
            
        except Exception:
            return False
    
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
        """
        Force le traitement d'un trade spécifique
        CORRIGÉ: Utilise le lock pour éviter les race conditions
        """
        import threading
        from datetime import timezone
        
        with self.processing_lock:
            if trade_id not in self.pending_trades:
                print(f"❌ Trade {trade_id} non trouvé dans les trades en attente")
                return False
            
            trade_info = self.pending_trades[trade_id]
            
            # Vérifier si déjà traité
            if trade_info.get('sl_tp_placed', False):
                print(f"✅ Trade {trade_id} déjà traité - SL/TP déjà placés")
                return True
            
            # Vérifier si en cours de traitement
            if trade_info.get('processing_started'):
                processing_time = trade_info['processing_started']
                if processing_time.tzinfo is None:
                    processing_time = processing_time.replace(tzinfo=timezone.utc)
                
                now_utc = datetime.now(timezone.utc)
                elapsed = (now_utc - processing_time).total_seconds()
                
                if elapsed < 30:  # Moins de 30 secondes
                    print(f"⚠️ Trade {trade_id} en cours de traitement depuis {elapsed:.0f}s")
                    return False
                else:
                    print(f"⚠️ Trade {trade_id} bloqué depuis {elapsed:.0f}s - Force reset")
                    # Reset pour débloquer
                    trade_info.pop('processing_started', None)
                    trade_info.pop('last_error', None)
                    trade_info.pop('last_error_time', None)
        
        # Traiter hors du lock
        print(f"🔄 Traitement forcé du trade {trade_id}")
        self._process_delayed_trade(trade_id)
        
        # Vérifier le résultat
        with self.processing_lock:
            if trade_id in self.pending_trades:
                return self.pending_trades[trade_id].get('sl_tp_placed', False)
        
        return False
    
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

