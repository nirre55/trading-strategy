# order_manager.py
"""
Gestionnaire d'ordres pour le trading live
Gère l'exécution, le suivi et la fermeture des trades
"""
import logging
import time
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
    """Gestionnaire d'ordres pour trading live"""
    
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
        
    def add_trade_opened_callback(self, callback):
        """Ajoute un callback appelé quand un trade s'ouvre"""
        self.on_trade_opened_callbacks.append(callback)
    
    def add_trade_closed_callback(self, callback):
        """Ajoute un callback appelé quand un trade se ferme"""
        self.on_trade_closed_callbacks.append(callback)
    
    def add_order_filled_callback(self, callback):
        """Ajoute un callback appelé quand un ordre est exécuté"""
        self.on_order_filled_callbacks.append(callback)
    
    def create_trade(self, symbol: str, direction: str, position_size: PositionSize) -> Optional[str]:
        """
        Crée et exécute un nouveau trade
        
        Returns:
            trade_id si succès, None si échec
        """
        try:
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
        """Exécute l'ordre d'entrée au marché"""
        try:
            # Détermination du côté
            side = "BUY" if trade.direction == "LONG" else "SELL"
            
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
            
            # Création de l'objet Order
            trade.entry_order = Order(
                order_id=result['orderId'],
                symbol=trade.symbol,
                side=side,
                type="MARKET",
                quantity=trade.quantity,
                price=None,
                status=OrderStatus.FILLED,
                timestamp=datetime.now(),
                filled_qty=float(result.get('executedQty', trade.quantity)),
                avg_price=float(result.get('avgPrice', trade.entry_price))
            )
            
            # Mise à jour du prix d'entrée réel
            if trade.entry_order.avg_price > 0:
                trade.entry_price = trade.entry_order.avg_price
            
            logger.info(f"✅ Ordre d'entrée exécuté: {trade.entry_order.avg_price}")
            
            # Placement des ordres SL et TP
            self._place_sl_tp_orders(trade)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur exécution ordre d'entrée: {e}")
            trade.status = TradeStatus.FAILED
            return False
    
    def _place_sl_tp_orders(self, trade: Trade):
        """Place les ordres Stop Loss et Take Profit"""
        try:
            # Côté opposé pour fermeture
            close_side = "SELL" if trade.direction == "LONG" else "BUY"
            
            # Placement Stop Loss
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
        """Ferme un trade et annule les ordres en cours"""
        try:
            logger.info(f"🔄 Fermeture trade {trade.trade_id}: {reason}")
            trade.status = TradeStatus.CLOSING
            
            # Annulation des ordres SL/TP en cours
            if trade.sl_order and trade.sl_order.status == OrderStatus.PENDING:
                self.client.cancel_order(trade.symbol, trade.sl_order.order_id)
            
            if trade.tp_order and trade.tp_order.status == OrderStatus.PENDING:
                self.client.cancel_order(trade.symbol, trade.tp_order.order_id)
            
            # Fermeture de la position au marché
            close_side = "SELL" if trade.direction == "LONG" else "BUY"
            result, error = self.client.place_market_order(
                symbol=trade.symbol,
                side=close_side,
                quantity=trade.quantity
            )
            
            if error:
                logger.error(f"❌ Erreur fermeture position: {error}")
                return False
            
            # Calcul du PnL
            exit_price = float(result.get('avgPrice', 0))
            trade.exit_price = exit_price
            trade.exit_reason = reason
            trade.closed_at = datetime.now()
            
            if trade.direction == "LONG":
                trade.pnl = (exit_price - trade.entry_price) * trade.quantity
            else:  # SHORT
                trade.pnl = (trade.entry_price - exit_price) * trade.quantity
            
            trade.status = TradeStatus.CLOSED
            
            logger.info(f"✅ Trade fermé: PnL = {trade.pnl:+.2f} USDT")
            
            # Déplacement vers les trades terminés
            self.completed_trades.append(trade)
            del self.active_trades[trade.trade_id]
            
            # Callback trade fermé
            for callback in self.on_trade_closed_callbacks:
                try:
                    callback(trade)
                except Exception as e:
                    logger.error(f"❌ Erreur callback trade fermé: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur fermeture trade: {e}")
            return False
    
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
        """Vérifie le statut d'un trade et de ses ordres"""
        try:
            # Vérification de l'ordre SL
            if trade.sl_order and trade.sl_order.status == OrderStatus.PENDING:
                orders, error = self.client.get_open_orders(trade.symbol)
                if not error:
                    sl_found = any(o['orderId'] == trade.sl_order.order_id for o in orders)
                    if not sl_found:
                        # SL exécuté
                        trade.sl_order.status = OrderStatus.FILLED
                        self._close_trade(trade, "Stop Loss")
                        return
            
            # Vérification de l'ordre TP
            if trade.tp_order and trade.tp_order.status == OrderStatus.PENDING:
                orders, error = self.client.get_open_orders(trade.symbol)
                if not error:
                    tp_found = any(o['orderId'] == trade.tp_order.order_id for o in orders)
                    if not tp_found:
                        # TP exécuté
                        trade.tp_order.status = OrderStatus.FILLED
                        self._close_trade(trade, "Take Profit")
                        return
            
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
            # Calcul PnL flottant
            current_price, _ = self.client.get_current_price(trade.symbol)
            if current_price:
                if trade.direction == "LONG":
                    floating_pnl = (current_price - trade.entry_price) * trade.quantity
                else:
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