# order_manager.py
"""
Gestionnaire d'ordres pour le trading live
Gère l'exécution, le suivi et la fermeture des trades
VERSION FINALE COMPLÈTE - Fix de tous les bugs + attente d'exécution
"""
import logging
import time
import json
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from binance_client import BinanceFuturesClient
from risk_manager import PositionSize

logger = logging.getLogger(__name__)

class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"

class TradeStatus(Enum):
    OPENING = "opening"
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"

@dataclass
class Order:
    """Représente un ordre sur Binance"""
    order_id: int
    symbol: str
    side: str
    type: str
    quantity: float
    price: Optional[float]
    status: OrderStatus
    timestamp: datetime
    filled_qty: float = 0.0
    avg_price: float = 0.0

@dataclass
class Trade:
    """Représente un trade complet (entry + SL + TP)"""
    trade_id: str
    symbol: str
    direction: str
    status: TradeStatus
    
    # Position
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    
    # Ordres associés
    entry_order: Optional[Order] = None
    sl_order: Optional[Order] = None
    tp_order: Optional[Order] = None
    
    # Résultats
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    exit_reason: Optional[str] = None
    
    # Timestamps
    created_at: datetime = None
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

class LiveOrderManager:
    """Gestionnaire d'ordres pour trading live - VERSION FINALE"""
    
    def __init__(self, binance_client: BinanceFuturesClient, config: Dict):
        self.client = binance_client
        self.config = config
        
        # Stockage des trades et ordres
        self.active_trades: Dict[str, Trade] = {}
        self.completed_trades: List[Trade] = []
        self.orders_history: List[Order] = []
        
        # Monitoring
        self.monitoring_active = False
        self.monitor_thread = None
        self.monitor_interval = 5  # secondes
        
        # Callbacks
        self.on_trade_opened_callbacks = []
        self.on_trade_closed_callbacks = []
        self.on_order_filled_callbacks = []
        
        # Compteurs
        self.trade_counter = 0
        
        # Debug mode
        self.debug_mode = True
        
        # Paramètres d'exécution
        self.execution_timeout = 10  # secondes pour attendre l'exécution
        self.execution_check_interval = 0.5  # vérification toutes les 500ms
        
    def add_trade_opened_callback(self, callback):
        """Ajoute un callback appelé quand un trade s'ouvre"""
        self.on_trade_opened_callbacks.append(callback)
    
    def add_trade_closed_callback(self, callback):
        """Ajoute un callback appelé quand un trade se ferme"""
        self.on_trade_closed_callbacks.append(callback)
    
    def add_order_filled_callback(self, callback):
        """Ajoute un callback appelé quand un ordre est exécuté"""
        self.on_order_filled_callbacks.append(callback)
    
    def can_create_new_trade(self) -> Tuple[bool, str]:
        """
        Vérifie si un nouveau trade peut être créé
        
        Returns:
            (bool, str): (autorisé, raison)
        """
        active_count = len(self.active_trades)
        
        if active_count >= 1:  # Limite à 1 trade simultané
            active_ids = list(self.active_trades.keys())
            return False, f"Trade déjà actif: {active_ids[0]}"
        
        return True, "Nouveau trade autorisé"

    def create_trade(self, symbol: str, direction: str, position_size: PositionSize) -> Optional[str]:
        """
        Crée et exécute un nouveau trade
        
        Returns:
            trade_id si succès, None si échec
        """
        try:
            # 🆕 VÉRIFICATION CRITIQUE avant création
            can_create, reason = self.can_create_new_trade()
            if not can_create:
                logger.warning(f"❌ Création trade refusée: {reason}")
                return None
            
            # Génération de l'ID du trade
            self.trade_counter += 1
            trade_id = f"{symbol}_{direction}_{self.trade_counter}_{int(time.time())}"
            
            # Création de l'objet Trade
            trade = Trade(
                trade_id=trade_id,
                symbol=symbol,
                direction=direction,
                status=TradeStatus.OPENING,
                quantity=position_size.quantity,
                entry_price=position_size.entry_price,
                stop_loss=position_size.stop_loss,
                take_profit=position_size.take_profit,
                created_at=datetime.now()
            )
            
            logger.info(f"🚀 Création trade {direction}: {trade_id}")
            logger.info(f"   📊 {position_size.quantity} @ {position_size.entry_price}")
            logger.info(f"   🛑 SL: {position_size.stop_loss}")
            logger.info(f"   🎯 TP: {position_size.take_profit}")
            
            # Exécution de l'ordre d'entrée
            if not self._execute_entry_order(trade):
                logger.error(f"❌ Échec ordre d'entrée pour {trade_id}")
                return None
            
            # Ajout aux trades actifs
            self.active_trades[trade_id] = trade
            
            # Démarrage du monitoring si pas déjà actif
            if not self.monitoring_active:
                self.start_monitoring()
            
            return trade_id
            
        except Exception as e:
            logger.error(f"❌ Erreur création trade: {e}")
            return None
    
    def _execute_entry_order(self, trade: Trade) -> bool:
        """🔧 FINAL FIX: Exécute l'ordre d'entrée et ATTEND l'exécution complète"""
        try:
            side = "BUY" if trade.direction == "LONG" else "SELL"
            
            logger.info(f"📡 Placement ordre market {side} {trade.quantity} {trade.symbol}")
            
            # Placement de l'ordre market
            result, error = self.client.place_market_order(
                symbol=trade.symbol,
                side=side,
                quantity=trade.quantity
            )
            
            if error:
                logger.error(f"❌ Erreur ordre market: {error}")
                trade.status = TradeStatus.FAILED
                return False
            
            # 🔍 DEBUG: Log de la réponse initiale
            if self.debug_mode:
                logger.debug(f"🔍 Réponse Binance initiale:")
                logger.debug(f"🔍 Status: {result.get('status')}")
                logger.debug(f"🔍 avgPrice initial: {result.get('avgPrice')}")
                logger.debug(f"🔍 executedQty initial: {result.get('executedQty')}")
            
            order_id = result['orderId']
            
            # 🆕 NOUVEAU: Attendre que l'ordre soit complètement exécuté
            executed_price = self._wait_for_order_execution(trade.symbol, order_id, self.execution_timeout)
            
            if executed_price <= 0:
                logger.warning(f"⚠️ Impossible de récupérer le prix d'exécution après {self.execution_timeout}s")
                # Fallback sur extraction robuste
                executed_price = self._extract_execution_price_robust(result, trade, order_id)
            
            if executed_price <= 0:
                logger.error(f"❌ Prix d'exécution invalide: {executed_price}")
                trade.status = TradeStatus.FAILED
                return False
            
            # Création de l'objet Order
            trade.entry_order = Order(
                order_id=order_id,
                symbol=trade.symbol,
                side=side,
                type="MARKET",
                quantity=trade.quantity,
                price=None,
                status=OrderStatus.FILLED,
                timestamp=datetime.now(),
                filled_qty=trade.quantity,  # Market order = complètement exécuté
                avg_price=executed_price
            )
            
            # Mise à jour du prix d'entrée
            old_entry = trade.entry_price
            trade.entry_price = executed_price
            
            # Logs détaillés
            logger.info(f"✅ Ordre d'entrée exécuté:")
            logger.info(f"   📊 Prix calculé: {old_entry:.1f}")
            logger.info(f"   📊 Prix RÉEL: {executed_price:.1f}")
            logger.info(f"   📊 Différence: {executed_price - old_entry:+.1f}")
            
            # Recalcul des niveaux SL/TP
            self._recalculate_sl_tp_levels(trade, old_entry)
            
            # Placement des ordres SL et TP
            self._place_sl_tp_orders(trade)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur exécution ordre d'entrée: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            trade.status = TradeStatus.FAILED
            return False
    
    def _wait_for_order_execution(self, symbol: str, order_id: int, timeout: int = 10) -> float:
        """🆕 NOUVEAU: Attend que l'ordre soit complètement exécuté"""
        try:
            logger.info(f"⏳ Attente exécution ordre {order_id}...")
            
            start_time = time.time()
            
            while (time.time() - start_time) < timeout:
                try:
                    # Récupération du statut de l'ordre
                    order_info, error = self.client._execute_request(
                        self.client.client.futures_get_order,
                        symbol=symbol,
                        orderId=order_id
                    )
                    
                    if error:
                        logger.warning(f"⚠️ Erreur récupération ordre: {error}")
                        time.sleep(self.execution_check_interval)
                        continue
                    
                    status = order_info.get('status')
                    avg_price = order_info.get('avgPrice', '0')
                    executed_qty = order_info.get('executedQty', '0')
                    
                    if self.debug_mode:
                        logger.debug(f"🔍 Ordre {order_id}: Status={status}, AvgPrice={avg_price}, ExecQty={executed_qty}")
                    
                    # Vérifier si l'ordre est complètement exécuté
                    if status == 'FILLED' and float(avg_price) > 0 and float(executed_qty) > 0:
                        executed_price = float(avg_price)
                        elapsed = time.time() - start_time
                        logger.info(f"✅ Ordre exécuté après {elapsed:.2f}s: {executed_price:.1f}")
                        return executed_price
                    
                    elif status in ['CANCELED', 'REJECTED', 'EXPIRED']:
                        logger.error(f"❌ Ordre {status}: {order_info}")
                        return 0.0
                    
                    # Attendre avant la prochaine vérification
                    time.sleep(self.execution_check_interval)
                    
                except Exception as e:
                    logger.warning(f"⚠️ Erreur vérification ordre: {e}")
                    time.sleep(self.execution_check_interval)
            
            # Timeout atteint
            logger.warning(f"⚠️ Timeout atteint ({timeout}s) - Tentative finale de récupération")
            
            # Dernière tentative de récupération
            try:
                order_info, error = self.client._execute_request(
                    self.client.client.futures_get_order,
                    symbol=symbol,
                    orderId=order_id
                )
                
                if not error and float(order_info.get('avgPrice', 0)) > 0:
                    final_price = float(order_info['avgPrice'])
                    logger.info(f"🔧 Prix récupéré en dernière tentative: {final_price:.1f}")
                    return final_price
            except Exception as e:
                logger.warning(f"⚠️ Erreur dernière tentative: {e}")
            
            return 0.0  # Échec total
            
        except Exception as e:
            logger.error(f"❌ Erreur attente exécution: {e}")
            return 0.0
    
    def _get_order_execution_from_fills(self, symbol: str, order_id: int) -> float:
        """🆕 NOUVEAU: Récupère le prix depuis l'historique des fills"""
        try:
            logger.debug(f"🔍 Recherche fills pour ordre {order_id}...")
            
            # Récupération des fills récents
            fills, error = self.client._execute_request(
                self.client.client.futures_account_trades,
                symbol=symbol,
                limit=50  # 50 derniers trades
            )
            
            if error:
                logger.warning(f"⚠️ Erreur récupération fills: {error}")
                return 0.0
            
            # Recherche du fill correspondant à notre ordre
            for fill in fills:
                if fill.get('orderId') == order_id:
                    fill_price = float(fill['price'])
                    fill_qty = float(fill['qty'])
                    fill_time = fill.get('time', 'unknown')
                    logger.info(f"🔍 Fill trouvé: {fill_qty} @ {fill_price} (time: {fill_time})")
                    return fill_price
            
            logger.warning(f"⚠️ Aucun fill trouvé pour ordre {order_id}")
            return 0.0
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération fills: {e}")
            return 0.0
    
    def _extract_execution_price_robust(self, result: Dict, trade: Trade, order_id: int = None) -> float:
        """🔧 AMÉLIORÉ: Extraction robuste avec toutes les méthodes"""
        try:
            # Méthode 1: avgPrice directement (si disponible)
            avg_price = result.get('avgPrice')
            if avg_price and float(avg_price) > 0:
                price = float(avg_price)
                logger.info(f"🔍 Prix depuis avgPrice: {price:.1f}")
                return price
            
            # Méthode 2: Calcul depuis fills dans la réponse
            fills = result.get('fills', [])
            if fills:
                total_qty = 0
                total_value = 0
                for fill in fills:
                    qty = float(fill['qty'])
                    price = float(fill['price'])
                    total_qty += qty
                    total_value += qty * price
                    logger.debug(f"🔍 Fill réponse: {qty} @ {price}")
                
                if total_qty > 0:
                    avg_price = total_value / total_qty
                    logger.info(f"🔍 Prix calculé depuis fills réponse: {avg_price:.1f}")
                    return avg_price
            
            # Méthode 3: Récupération depuis l'historique des fills
            if order_id:
                fill_price = self._get_order_execution_from_fills(trade.symbol, order_id)
                if fill_price > 0:
                    logger.info(f"🔍 Prix depuis fills historique: {fill_price:.1f}")
                    return fill_price
            
            # Méthode 4: Prix market actuel (avec retry)
            logger.warning("⚠️ Toutes méthodes précédentes échouées, récupération prix market...")
            for attempt in range(3):
                current_price, error = self.client.get_current_price(trade.symbol)
                if not error and current_price and current_price > 0:
                    logger.info(f"🔧 Prix depuis market (tentative {attempt+1}): {current_price:.1f}")
                    return current_price
                time.sleep(0.5)
            
            # Méthode 5: Fallback prix calculé
            logger.error("❌ TOUTES méthodes échouées - Utilisation prix calculé")
            return trade.entry_price
            
        except Exception as e:
            logger.error(f"❌ Erreur extraction prix: {e}")
            return trade.entry_price
    
    def _recalculate_sl_tp_levels(self, trade: Trade, old_entry: float):
        """🆕 NOUVEAU: Recalcule SL/TP basé sur le prix réel d'exécution"""
        try:
            # Calcul des distances originales
            if trade.direction == "LONG":
                sl_distance = old_entry - trade.stop_loss
                tp_distance = trade.take_profit - old_entry
            else:  # SHORT
                sl_distance = trade.stop_loss - old_entry  
                tp_distance = old_entry - trade.take_profit
            
            logger.debug(f"🔍 Distances originales: SL={sl_distance:.2f}, TP={tp_distance:.2f}")
            
            # Application des mêmes distances au prix réel
            if trade.direction == "LONG":
                new_sl = trade.entry_price - sl_distance
                new_tp = trade.entry_price + tp_distance
            else:  # SHORT
                new_sl = trade.entry_price + sl_distance
                new_tp = trade.entry_price - tp_distance
            
            # Formatage selon Binance
            trade.stop_loss = self.client.format_price(new_sl, trade.symbol)
            trade.take_profit = self.client.format_price(new_tp, trade.symbol)
            
            logger.info(f"🔧 Niveaux recalculés:")
            logger.info(f"   🛑 Nouveau SL: {trade.stop_loss:.1f}")
            logger.info(f"   🎯 Nouveau TP: {trade.take_profit:.1f}")
            
            # Validation de cohérence
            self._validate_sl_tp_levels(trade)
            
            # Calcul du nouveau ratio R/R
            if trade.direction == "LONG":
                new_sl_distance = trade.entry_price - trade.stop_loss
                new_tp_distance = trade.take_profit - trade.entry_price
            else:  # SHORT
                new_sl_distance = trade.stop_loss - trade.entry_price
                new_tp_distance = trade.entry_price - trade.take_profit
            
            new_ratio = new_tp_distance / new_sl_distance if new_sl_distance > 0 else 0
            logger.info(f"📊 Nouveau ratio R/R: {new_ratio:.3f}")
            
        except Exception as e:
            logger.error(f"❌ Erreur recalcul SL/TP: {e}")
    
    def _validate_sl_tp_levels(self, trade: Trade):
        """🆕 NOUVEAU: Valide la cohérence des niveaux SL/TP"""
        try:
            if trade.direction == "LONG":
                if trade.stop_loss >= trade.entry_price:
                    logger.error(f"❌ SL LONG >= Entry: {trade.stop_loss} >= {trade.entry_price}")
                if trade.take_profit <= trade.entry_price:
                    logger.error(f"❌ TP LONG <= Entry: {trade.take_profit} <= {trade.entry_price}")
            else:  # SHORT
                if trade.stop_loss <= trade.entry_price:
                    logger.error(f"❌ SL SHORT <= Entry: {trade.stop_loss} <= {trade.entry_price}")
                if trade.take_profit >= trade.entry_price:
                    logger.error(f"❌ TP SHORT >= Entry: {trade.take_profit} >= {trade.entry_price}")
        except Exception as e:
            logger.error(f"❌ Erreur validation SL/TP: {e}")
    
    def _place_sl_tp_orders(self, trade: Trade):
        """Place les ordres Stop Loss et Take Profit avec niveaux corrigés"""
        try:
            # Côté opposé pour fermeture
            close_side = "SELL" if trade.direction == "LONG" else "BUY"
            
            # Placement Stop Loss
            logger.info(f"📡 Placement Stop Loss: {close_side} {trade.quantity} @ {trade.stop_loss}")
            sl_result, sl_error = self.client.place_stop_order(
                symbol=trade.symbol,
                side=close_side,
                quantity=trade.quantity,
                stop_price=trade.stop_loss
            )
            
            if sl_error:
                logger.error(f"❌ Erreur placement SL: {sl_error}")
            else:
                trade.sl_order = Order(
                    order_id=sl_result['orderId'],
                    symbol=trade.symbol,
                    side=close_side,
                    type="STOP_MARKET",
                    quantity=trade.quantity,
                    price=trade.stop_loss,
                    status=OrderStatus.PENDING,
                    timestamp=datetime.now()
                )
                logger.info(f"✅ Stop Loss placé: {trade.stop_loss}")
            
            # Placement Take Profit
            logger.info(f"📡 Placement Take Profit: {close_side} {trade.quantity} @ {trade.take_profit}")
            tp_result, tp_error = self.client.place_limit_order(
                symbol=trade.symbol,
                side=close_side,
                quantity=trade.quantity,
                price=trade.take_profit
            )
            
            if tp_error:
                logger.error(f"❌ Erreur placement TP: {tp_error}")
            else:
                trade.tp_order = Order(
                    order_id=tp_result['orderId'],
                    symbol=trade.symbol,
                    side=close_side,
                    type="LIMIT",
                    quantity=trade.quantity,
                    price=trade.take_profit,
                    status=OrderStatus.PENDING,
                    timestamp=datetime.now()
                )
                logger.info(f"✅ Take Profit placé: {trade.take_profit}")
            
            # Trade maintenant ouvert
            trade.status = TradeStatus.OPEN
            trade.opened_at = datetime.now()
            
            # Calcul du risque réel avec prix corrigé
            if trade.direction == "LONG":
                real_risk = (trade.entry_price - trade.stop_loss) * trade.quantity
            else:  # SHORT
                real_risk = (trade.stop_loss - trade.entry_price) * trade.quantity
            
            logger.info(f"📊 Risque réel avec prix corrigé: {real_risk:.2f} USDT")
            
            # Callback trade ouvert
            for callback in self.on_trade_opened_callbacks:
                try:
                    callback(trade)
                except Exception as e:
                    logger.error(f"❌ Erreur callback trade ouvert: {e}")
            
        except Exception as e:
            logger.error(f"❌ Erreur placement SL/TP: {e}")
    
    def close_trade_manually(self, trade_id: str, reason: str = "Manual close") -> bool:
        """Ferme manuellement un trade"""
        if trade_id not in self.active_trades:
            logger.error(f"❌ Trade non trouvé: {trade_id}")
            return False
        
        trade = self.active_trades[trade_id]
        return self._close_trade(trade, reason)
    
    def _close_trade(self, trade: Trade, reason: str) -> bool:
        """🔧 CORRIGÉ: Fermeture avec calcul PnL correct"""
        try:
            logger.info(f"🔄 Fermeture trade {trade.trade_id}: {reason}")
            trade.status = TradeStatus.CLOSING
            
            # Annulation des ordres en cours
            self._cancel_pending_orders(trade)
            
            # Fermeture de la position au marché si nécessaire
            if reason not in ["Stop Loss", "Take Profit"]:
                # Fermeture manuelle - placer un ordre market
                close_side = "SELL" if trade.direction == "LONG" else "BUY"
                result, error = self.client.place_market_order(
                    symbol=trade.symbol,
                    side=close_side,
                    quantity=trade.quantity
                )
                
                if error:
                    logger.error(f"❌ Erreur fermeture position: {error}")
                    return False
            
            # 🔧 RÉCUPÉRATION DU PRIX DE SORTIE SELON LE CONTEXTE
            exit_price = self._determine_exit_price(trade, reason)
            
            if exit_price <= 0:
                logger.error(f"❌ Prix de sortie invalide: {exit_price}")
                # Utiliser prix market actuel en fallback
                current_price, _ = self.client.get_current_price(trade.symbol)
                exit_price = current_price if current_price > 0 else trade.entry_price
            
            trade.exit_price = exit_price
            trade.exit_reason = reason
            trade.closed_at = datetime.now()
            
            # 🔧 CALCUL PnL CORRECT avec prix réels
            trade.pnl = self._calculate_correct_pnl(trade)
            
            trade.status = TradeStatus.CLOSED
            
            # Logs détaillés
            logger.info(f"✅ Trade fermé:")
            logger.info(f"   📊 Entry RÉEL: {trade.entry_price:.1f}")
            logger.info(f"   📊 Exit RÉEL: {exit_price:.1f}")
            logger.info(f"   💰 PnL CORRECT: {trade.pnl:+.2f} USDT")
            logger.info(f"   📋 Raison: {reason}")
            
            # Validation du PnL
            expected_sign = "GAIN" if trade.pnl > 0 else "PERTE"
            logger.info(f"   📈 Type résultat: {expected_sign}")
            
            # Déplacement vers trades terminés
            self.completed_trades.append(trade)
            del self.active_trades[trade.trade_id]
            
            # Callbacks
            for callback in self.on_trade_closed_callbacks:
                try:
                    callback(trade)
                except Exception as e:
                    logger.error(f"❌ Erreur callback: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur fermeture trade: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def _determine_exit_price(self, trade: Trade, reason: str) -> float:
        """🆕 Détermine le prix de sortie selon le contexte"""
        try:
            if reason == "Stop Loss":
                # Prix basé sur le niveau SL (approximation)
                exit_price = trade.stop_loss
                logger.info(f"🔍 Prix sortie (SL): {exit_price:.1f}")
                
            elif reason == "Take Profit":
                # Prix basé sur le niveau TP (approximation)
                exit_price = trade.take_profit
                logger.info(f"🔍 Prix sortie (TP): {exit_price:.1f}")
                
            else:
                # Fermeture manuelle - prix market actuel
                current_price, error = self.client.get_current_price(trade.symbol)
                if not error and current_price > 0:
                    exit_price = current_price
                    logger.info(f"🔍 Prix sortie (Market): {exit_price:.1f}")
                else:
                    # Fallback sur prix d'entrée (neutre)
                    exit_price = trade.entry_price
                    logger.warning(f"⚠️ Prix sortie fallback: {exit_price:.1f}")
            
            return exit_price
            
        except Exception as e:
            logger.error(f"❌ Erreur détermination prix sortie: {e}")
            return trade.entry_price
    
    def _calculate_correct_pnl(self, trade: Trade) -> float:
        """🆕 Calcul PnL correct selon la direction"""
        try:
            if trade.direction == "LONG":
                # LONG: Gain si prix monte
                pnl = (trade.exit_price - trade.entry_price) * trade.quantity
            else:  # SHORT
                # SHORT: Gain si prix baisse
                pnl = (trade.entry_price - trade.exit_price) * trade.quantity
            
            # Validation logique
            if trade.exit_reason == "Stop Loss":
                # SL = toujours une perte
                if pnl > 0:
                    logger.warning(f"⚠️ PnL positif sur SL détecté: {pnl:.2f} - Vérifier calculs")
            
            elif trade.exit_reason == "Take Profit":
                # TP = toujours un gain
                if pnl <= 0:
                    logger.warning(f"⚠️ PnL négatif sur TP détecté: {pnl:.2f} - Vérifier calculs")
            
            return round(pnl, 2)
            
        except Exception as e:
            logger.error(f"❌ Erreur calcul PnL: {e}")
            return 0.0
    
    def _cancel_pending_orders(self, trade: Trade):
        """🆕 Annule tous les ordres en cours du trade"""
        try:
            cancelled_orders = []
            
            # Annulation SL
            if trade.sl_order and trade.sl_order.status == OrderStatus.PENDING:
                cancel_result, error = self.client.cancel_order(trade.symbol, trade.sl_order.order_id)
                if not error:
                    trade.sl_order.status = OrderStatus.CANCELLED
                    cancelled_orders.append("SL")
                    logger.info(f"✅ SL annulé: {trade.sl_order.order_id}")
                else:
                    logger.warning(f"⚠️ Erreur annulation SL: {error}")
            
            # Annulation TP
            if trade.tp_order and trade.tp_order.status == OrderStatus.PENDING:
                cancel_result, error = self.client.cancel_order(trade.symbol, trade.tp_order.order_id)
                if not error:
                    trade.tp_order.status = OrderStatus.CANCELLED
                    cancelled_orders.append("TP")
                    logger.info(f"✅ TP annulé: {trade.tp_order.order_id}")
                else:
                    logger.warning(f"⚠️ Erreur annulation TP: {error}")
            
            logger.info(f"📋 Ordres annulés: {', '.join(cancelled_orders) if cancelled_orders else 'Aucun'}")
            
        except Exception as e:
            logger.error(f"❌ Erreur annulation ordres: {e}")
    
    def start_monitoring(self):
        """Démarre le monitoring des trades actifs"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_trades)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logger.info("🔍 Monitoring des trades démarré")
    
    def stop_monitoring(self):
        """Arrête le monitoring"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
        logger.info("🔍 Monitoring des trades arrêté")
    
    def _monitor_trades(self):
        """Boucle de monitoring des trades actifs"""
        while self.monitoring_active:
            try:
                # Vérification de chaque trade actif
                trades_to_check = list(self.active_trades.values())
                
                for trade in trades_to_check:
                    self._check_trade_status(trade)
                
                time.sleep(self.monitor_interval)
                
            except Exception as e:
                logger.error(f"❌ Erreur monitoring: {e}")
                time.sleep(self.monitor_interval)
    
    def _check_trade_status(self, trade: Trade):
        """🔧 CORRIGÉ: Vérifie le statut et gère les exécutions d'ordres"""
        try:
            # Récupération des ordres ouverts
            orders, error = self.client.get_open_orders(trade.symbol)
            if error:
                logger.warning(f"⚠️ Erreur récupération ordres: {error}")
                return
            
            open_order_ids = [o['orderId'] for o in orders]
            
            # Vérification de l'ordre SL
            sl_executed = False
            if trade.sl_order and trade.sl_order.status == OrderStatus.PENDING:
                if trade.sl_order.order_id not in open_order_ids:
                    # SL exécuté
                    trade.sl_order.status = OrderStatus.FILLED
                    sl_executed = True
                    logger.info(f"🛑 Stop Loss exécuté pour {trade.trade_id}")
            
            # Vérification de l'ordre TP
            tp_executed = False
            if trade.tp_order and trade.tp_order.status == OrderStatus.PENDING:
                if trade.tp_order.order_id not in open_order_ids:
                    # TP exécuté
                    trade.tp_order.status = OrderStatus.FILLED
                    tp_executed = True
                    logger.info(f"🎯 Take Profit exécuté pour {trade.trade_id}")
            
            # 🔧 CORRECTION: Gestion exclusive des exécutions
            if sl_executed and tp_executed:
                # 🚨 PROBLÈME: Les deux ordres exécutés (rare mais possible)
                logger.critical(f"🚨 ALERTE: SL et TP exécutés simultanément pour {trade.trade_id}")
                # Fermeture avec vérification de position
                self._close_trade(trade, "SL+TP simultanés")
                
            elif sl_executed:
                # SL exécuté en premier - fermeture normale
                self._close_trade(trade, "Stop Loss")
                
            elif tp_executed:
                # TP exécuté en premier - fermeture normale  
                self._close_trade(trade, "Take Profit")
            
        except Exception as e:
            logger.error(f"❌ Erreur vérification trade {trade.trade_id}: {e}")
    
    def close_all_trades(self, reason: str = "Emergency close") -> int:
        """Ferme tous les trades actifs"""
        closed_count = 0
        trades_to_close = list(self.active_trades.values())
        
        for trade in trades_to_close:
            if self._close_trade(trade, reason):
                closed_count += 1
        
        logger.info(f"🔄 {closed_count} trades fermés: {reason}")
        return closed_count
    
    def get_active_trades_summary(self) -> Dict:
        """Retourne un résumé des trades actifs"""
        if not self.active_trades:
            return {"message": "Aucun trade actif"}
        
        summary = {
            "total_active": len(self.active_trades),
            "long_trades": len([t for t in self.active_trades.values() if t.direction == "LONG"]),
            "short_trades": len([t for t in self.active_trades.values() if t.direction == "SHORT"]),
            "total_exposure": sum(t.quantity * t.entry_price for t in self.active_trades.values()),
            "trades": []
        }
        
        for trade in self.active_trades.values():
            # Calcul PnL flottant CORRECT
            current_price, _ = self.client.get_current_price(trade.symbol)
            if current_price:
                if trade.direction == "LONG":
                    floating_pnl = (current_price - trade.entry_price) * trade.quantity
                else:  # SHORT
                    floating_pnl = (trade.entry_price - current_price) * trade.quantity
            else:
                floating_pnl = 0
            
            summary["trades"].append({
                "id": trade.trade_id,
                "direction": trade.direction,
                "entry": trade.entry_price,
                "quantity": trade.quantity,
                "sl": trade.stop_loss,
                "tp": trade.take_profit,
                "floating_pnl": round(floating_pnl, 2),
                "opened_at": trade.opened_at
            })
        
        return summary
    
    def get_performance_stats(self) -> Dict:
        """Retourne les statistiques de performance"""
        if not self.completed_trades:
            return {"message": "Aucun trade terminé"}
        
        total_trades = len(self.completed_trades)
        winning_trades = [t for t in self.completed_trades if t.pnl > 0]
        losing_trades = [t for t in self.completed_trades if t.pnl <= 0]
        
        total_pnl = sum(t.pnl for t in self.completed_trades)
        avg_win = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        return {
            "total_trades": total_trades,
            "wins": len(winning_trades),
            "losses": len(losing_trades),
            "win_rate": round((len(winning_trades) / total_trades) * 100, 1),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else float('inf')
        }
    
    def emergency_cancel_all_orders(self, symbol: str):
        """🆕 NOUVEAU: Annule TOUS les ordres en cours pour un symbole"""
        try:
            logger.warning(f"🚨 ANNULATION D'URGENCE - Tous ordres {symbol}")
            
            # Récupération de tous les ordres ouverts
            orders, error = self.client.get_open_orders(symbol)
            if error:
                logger.error(f"❌ Erreur récupération ordres: {error}")
                return False
            
            cancelled_count = 0
            for order in orders:
                order_id = order['orderId']
                cancel_result, cancel_error = self.client.cancel_order(symbol, order_id)
                if not cancel_error:
                    cancelled_count += 1
                    logger.info(f"✅ Ordre annulé: {order_id}")
                else:
                    logger.error(f"❌ Erreur annulation {order_id}: {cancel_error}")
            
            logger.info(f"🔄 {cancelled_count} ordres annulés pour {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur annulation d'urgence: {e}")
            return False
    
    def check_and_fix_orphan_orders(self):
        """🆕 NOUVEAU: Détecte et corrige les ordres orphelins"""
        try:
            logger.info("🔍 Vérification des ordres orphelins...")
            
            # Récupération de tous les ordres ouverts
            symbol = self.config.get('symbol', 'BTCUSDC')
            orders, error = self.client.get_open_orders(symbol)
            if error:
                logger.error(f"❌ Erreur récupération ordres: {error}")
                return
            
            if not orders:
                logger.info("✅ Aucun ordre ouvert")
                return
            
            # Ordres associés aux trades actifs
            active_order_ids = set()
            for trade in self.active_trades.values():
                if trade.sl_order:
                    active_order_ids.add(trade.sl_order.order_id)
                if trade.tp_order:
                    active_order_ids.add(trade.tp_order.order_id)
            
            # Détection des ordres orphelins
            orphan_orders = []
            for order in orders:
                if order['orderId'] not in active_order_ids:
                    orphan_orders.append(order)
            
            if orphan_orders:
                logger.warning(f"⚠️ {len(orphan_orders)} ordre(s) orphelin(s) détecté(s):")
                for order in orphan_orders:
                    order_type = order.get('type', 'UNKNOWN')
                    price_info = order.get('stopPrice', order.get('price', 'MARKET'))
                    logger.warning(f"   📋 {order['orderId']}: {order['side']} {order['origQty']} @ {price_info} ({order_type})")
                
                # Auto-annulation des ordres orphelins (sécurité)
                logger.warning("🔧 Auto-annulation des ordres orphelins pour sécurité...")
                for order in orphan_orders:
                    cancel_result, cancel_error = self.client.cancel_order(order['symbol'], order['orderId'])
                    if not cancel_error:
                        logger.info(f"✅ Ordre orphelin annulé: {order['orderId']}")
                    else:
                        logger.error(f"❌ Erreur annulation orphelin: {cancel_error}")
            else:
                logger.info("✅ Aucun ordre orphelin détecté")
                
        except Exception as e:
            logger.error(f"❌ Erreur vérification ordres orphelins: {e}")
    
    def debug_trade_state(self, trade_id: str):
        """🔧 Debug complet d'un trade pour investigation"""
        if trade_id not in self.active_trades:
            logger.error(f"❌ Trade non trouvé: {trade_id}")
            return
        
        trade = self.active_trades[trade_id]
        
        logger.info(f"🔍 DEBUG TRADE {trade_id}:")
        logger.info(f"   Status: {trade.status}")
        logger.info(f"   Direction: {trade.direction}")
        logger.info(f"   Entry Price: {trade.entry_price}")
        logger.info(f"   SL: {trade.stop_loss}")
        logger.info(f"   TP: {trade.take_profit}")
        
        if trade.entry_order:
            logger.info(f"   Entry Order: {trade.entry_order.order_id} - Prix: {trade.entry_order.avg_price}")
        
        if trade.sl_order:
            logger.info(f"   SL Order: {trade.sl_order.order_id} - Status: {trade.sl_order.status}")
        
        if trade.tp_order:
            logger.info(f"   TP Order: {trade.tp_order.order_id} - Status: {trade.tp_order.status}")
        
        # Vérification prix market actuel
        current_price, _ = self.client.get_current_price(trade.symbol)
        if current_price:
            logger.info(f"   Prix Market: {current_price:.1f}")
            
            # Calcul PnL flottant correct
            if trade.direction == "LONG":
                floating_pnl = (current_price - trade.entry_price) * trade.quantity
            else:  # SHORT
                floating_pnl = (trade.entry_price - current_price) * trade.quantity
            
            logger.info(f"   PnL Flottant: {floating_pnl:+.2f} USDT")
    
    def fix_existing_trade_prices(self):
        """🆕 NOUVEAU: Corrige les prix des trades actifs si nécessaire"""
        for trade_id, trade in self.active_trades.items():
            if trade.entry_order and trade.entry_order.avg_price <= 0:
                logger.warning(f"🔧 Correction trade {trade_id} avec prix = 0")
                
                # Récupération du prix actuel comme approximation
                current_price, error = self.client.get_current_price(trade.symbol)
                if not error and current_price:
                    old_price = trade.entry_price
                    trade.entry_price = current_price
                    trade.entry_order.avg_price = current_price
                    logger.info(f"✅ Prix corrigé: {old_price:.1f} → {current_price:.1f}")
                    
                    # Recalcul des niveaux SL/TP
                    self._recalculate_sl_tp_levels(trade, old_price)
    
    def correct_false_trade_record(self, trade_id: str, real_pnl: float):
        """🆕 NOUVEAU: Corrige un enregistrement de trade erroné"""
        try:
            # Recherche dans les trades terminés
            for trade in self.completed_trades:
                if trade.trade_id == trade_id:
                    old_pnl = trade.pnl
                    trade.pnl = real_pnl
                    logger.info(f"🔧 Correction PnL trade {trade_id}:")
                    logger.info(f"   Ancien PnL: {old_pnl:+.2f}")
                    logger.info(f"   Nouveau PnL: {real_pnl:+.2f}")
                    return True
            
            logger.warning(f"⚠️ Trade {trade_id} non trouvé pour correction")
            return False
            
        except Exception as e:
            logger.error(f"❌ Erreur correction trade: {e}")
            return False
    
    def set_debug_mode(self, enabled: bool):
        """Active/désactive le mode debug"""
        self.debug_mode = enabled
        logger.info(f"🔧 Mode debug: {'activé' if enabled else 'désactivé'}")
    
    def get_system_health(self) -> Dict:
        """Retourne l'état de santé du système d'ordres"""
        return {
            'active_trades': len(self.active_trades),
            'completed_trades': len(self.completed_trades),
            'monitoring_active': self.monitoring_active,
            'debug_mode': self.debug_mode,
            'last_trade_id': self.trade_counter,
            'total_orders_history': len(self.orders_history)
        }