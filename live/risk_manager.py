# risk_manager.py
"""
Gestionnaire de risque pour le trading live
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PositionSize:
    """Résultat du calcul de taille de position"""
    quantity: float
    usdt_value: float
    risk_amount: float
    risk_percentage: float
    entry_price: float
    stop_loss: float
    take_profit: float

@dataclass
class RiskMetrics:
    """Métriques de risque actuelles"""
    daily_pnl: float
    daily_trades: int
    consecutive_losses: int
    max_drawdown: float
    current_exposure: float
    risk_limit_used: float

class LiveRiskManager:
    """Gestionnaire de risque en temps réel"""
    
    def __init__(self, config: Dict, safety_limits: Dict):
        self.config = config
        self.limits = safety_limits
        
        # État du compte
        self.account_balance = 0.0
        self.initial_balance = 0.0
        
        # Métriques de risque
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.consecutive_losses = 0
        self.max_drawdown = 0.0
        self.peak_balance = 0.0
        
        # Historique des trades
        self.trades_today = []
        self.all_trades = []
        
        # État d'urgence
        self.emergency_stop = False
        self.stop_reason = None
        
    def update_balance(self, new_balance: float):
        """Met à jour le solde du compte"""
        if self.initial_balance == 0:
            self.initial_balance = new_balance
            self.peak_balance = new_balance
        
        self.account_balance = new_balance
        self.peak_balance = max(self.peak_balance, new_balance)
        
        # Calcul du drawdown
        current_drawdown = self.peak_balance - new_balance
        self.max_drawdown = max(self.max_drawdown, current_drawdown)
        
        # Vérification des limites d'urgence
        self._check_emergency_limits()
    
    def calculate_position_size(self, entry_price: float, stop_loss: float, 
                          direction: str) -> Optional[PositionSize]:
        """
        Calcule la taille de position optimale avec TP fixe ou ratio
        
        Args:
            entry_price: Prix d'entrée prévu
            stop_loss: Prix de stop loss
            direction: 'LONG' ou 'SHORT'
        
        Returns:
            PositionSize ou None si trop risqué
        """
        try:
            # Vérifications de sécurité
            if self.emergency_stop:
                logger.warning(f"❌ Position refusée - Mode urgence: {self.stop_reason}")
                return None
            
            if self._is_daily_limit_reached():
                logger.warning("❌ Position refusée - Limites journalières atteintes")
                return None
            
            # Calcul du risque par trade
            max_risk_usdt = self.account_balance * self.config['max_balance_risk']
            
            # Distance prix/stop loss
            if direction == 'LONG':
                price_distance = entry_price - stop_loss
            else:  # SHORT
                price_distance = stop_loss - entry_price
            
            if price_distance <= 0:
                logger.error("❌ Stop loss invalide")
                return None
            
            # Calcul de la quantité
            risk_per_unit = price_distance
            max_quantity = max_risk_usdt / risk_per_unit
            
            # Application des limites min/max
            usdt_value = max_quantity * entry_price
            
            if usdt_value < self.config['min_position_size']:
                logger.warning(f"❌ Position trop petite: {usdt_value:.2f} USDT")
                return None
            
            if usdt_value > self.config['max_position_size']:
                # Réduction à la taille max
                usdt_value = self.config['max_position_size']
                max_quantity = usdt_value / entry_price
                max_risk_usdt = max_quantity * risk_per_unit
            
            # 🆕 CALCUL DU TAKE PROFIT SELON LE MODE
            take_profit = self._calculate_take_profit(entry_price, stop_loss, direction)
            
            # Formatage selon les règles Binance
            quantity = self._format_quantity(max_quantity)
            
            position = PositionSize(
                quantity=quantity,
                usdt_value=round(quantity * entry_price, 2),
                risk_amount=round(max_risk_usdt, 2),
                risk_percentage=round((max_risk_usdt / self.account_balance) * 100, 2),
                entry_price=round(entry_price, 1),
                stop_loss=round(stop_loss, 1),
                take_profit=round(take_profit, 1)
            )
            
            # 🔍 LOGS DÉTAILLÉS SELON LE MODE
            tp_mode = self.config.get('tp_mode', 'ratio')
            logger.info(f"📊 Position calculée: {quantity} @ {entry_price:.1f} USDT")
            logger.info(f"   💰 Valeur: {position.usdt_value} USDT")
            logger.info(f"   ⚠️ Risque: {position.risk_amount} USDT ({position.risk_percentage:.1f}%)")
            logger.info(f"   🎯 Mode TP: {tp_mode}")
            
            if tp_mode == "fixed_percent":
                tp_percent = self.config.get('tp_fixed_percent', 1.0)
                logger.info(f"   📈 TP Fixe: {tp_percent}% du prix d'entrée")
            else:
                tp_ratio = self.config.get('tp_ratio', 1.0)
                logger.info(f"   📈 TP Ratio: {tp_ratio}x le risque SL")
            
            return position
            
        except Exception as e:
            logger.error(f"❌ Erreur calcul position: {e}")
            return None
    
    def _calculate_take_profit(self, entry_price: float, stop_loss: float, direction: str) -> float:
        """
        🆕 NOUVEAU: Calcule le Take Profit selon le mode configuré
        
        Args:
            entry_price: Prix d'entrée
            stop_loss: Prix de stop loss
            direction: 'LONG' ou 'SHORT'
        
        Returns:
            float: Prix de Take Profit
        """
        try:
            tp_mode = self.config.get('tp_mode', 'ratio')
            
            if tp_mode == "fixed_percent":
                # 🎯 MODE NOUVEAU: Pourcentage fixe du prix d'entrée
                tp_percent = self.config.get('tp_fixed_percent', 1.0)  # 1% par défaut
                
                if direction == 'LONG':
                    # LONG: TP au-dessus du prix d'entrée
                    take_profit = entry_price * (1 + tp_percent / 100)
                    logger.debug(f"🔍 TP LONG fixe: {entry_price:.1f} + {tp_percent}% = {take_profit:.1f}")
                else:  # SHORT
                    # SHORT: TP en-dessous du prix d'entrée
                    take_profit = entry_price * (1 - tp_percent / 100)
                    logger.debug(f"🔍 TP SHORT fixe: {entry_price:.1f} - {tp_percent}% = {take_profit:.1f}")
                
                # Calcul du ratio R/R pour information
                if direction == 'LONG':
                    sl_distance = entry_price - stop_loss
                    tp_distance = take_profit - entry_price
                else:  # SHORT
                    sl_distance = stop_loss - entry_price
                    tp_distance = entry_price - take_profit
                
                rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
                logger.info(f"📊 TP Fixe {tp_percent}% → Ratio R/R: {rr_ratio:.2f}")
                
            else:
                # 📊 MODE ANCIEN: Ratio du risque SL (comportement original)
                tp_ratio = self.config.get('tp_ratio', 1.0)
                
                if direction == 'LONG':
                    tp_distance = (entry_price - stop_loss) * tp_ratio
                    take_profit = entry_price + tp_distance
                    logger.debug(f"🔍 TP LONG ratio: {entry_price:.1f} + {tp_distance:.1f} = {take_profit:.1f}")
                else:  # SHORT
                    tp_distance = (stop_loss - entry_price) * tp_ratio
                    take_profit = entry_price - tp_distance
                    logger.debug(f"🔍 TP SHORT ratio: {entry_price:.1f} - {tp_distance:.1f} = {take_profit:.1f}")
                
                logger.info(f"📊 TP Ratio {tp_ratio}x du risque SL")
            
            return take_profit
            
        except Exception as e:
            logger.error(f"❌ Erreur calcul TP: {e}")
            # Fallback vers le mode ratio
            tp_distance = abs(entry_price - stop_loss) * self.config.get('tp_ratio', 1.0)
            if direction == 'LONG':
                return entry_price + tp_distance
            else:
                return entry_price - tp_distance
            
    def validate_trade(self, signal_confidence: float) -> Tuple[bool, str]:
        """
        Valide si un trade peut être exécuté
        
        Returns:
            (autorisé, raison)
        """
        # Vérifications de base
        if self.emergency_stop:
            return False, f"Mode urgence: {self.stop_reason}"
        
        if self._is_daily_limit_reached():
            return False, "Limites journalières atteintes"
        
        # Vérification de la confiance du signal
        min_confidence = 0.6  # 60% minimum
        if signal_confidence < min_confidence:
            return False, f"Confiance trop faible: {signal_confidence:.1%}"
        
        # Vérification du timing (éviter les heures creuses)
        # current_hour = datetime.now().hour
        # if current_hour in [22, 23, 0, 1, 2, 3, 4, 5]:  # Heures creuses
        #     return False, "Heures de trading restreintes"
        
        return True, "Trade autorisé"
    
    def record_trade(self, direction: str, entry_price: float, quantity: float, 
                    result: str, pnl: float):
        """Enregistre un trade terminé"""
        trade = {
            'timestamp': datetime.now(),
            'direction': direction,
            'entry_price': entry_price,
            'quantity': quantity,
            'result': result,
            'pnl': pnl
        }
        
        self.all_trades.append(trade)
        
        # Mise à jour des métriques journalières
        today = datetime.now().date()
        self.trades_today = [t for t in self.all_trades 
                           if t['timestamp'].date() == today]
        
        self.daily_trades = len(self.trades_today)
        self.daily_pnl = sum(t['pnl'] for t in self.trades_today)
        
        # Gestion des pertes consécutives
        if result == 'loss':
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        logger.info(f"📝 Trade enregistré: {result.upper()} - PnL: {pnl:+.2f} USDT")
        
        # Vérification des limites après trade
        self._check_emergency_limits()
    
    def _is_daily_limit_reached(self) -> bool:
        """Vérifie si les limites journalières sont atteintes"""
        # Limite nombre de trades
        if self.daily_trades >= self.limits['max_daily_trades']:
            return True
        
        # Limite pertes journalières
        if self.daily_pnl <= -self.limits['max_daily_loss']:
            return True
        
        # Limite pertes consécutives
        if self.consecutive_losses >= self.limits['max_consecutive_losses']:
            return True
        
        return False
    
    def _check_emergency_limits(self):
        """Vérifie les limites d'urgence et active l'arrêt si nécessaire"""
        # Perte totale d'urgence
        total_loss = self.initial_balance - self.account_balance
        if total_loss >= self.limits['emergency_stop_loss']:
            self._trigger_emergency_stop(f"Perte totale: {total_loss:.2f} USDT")
            return
        
        # Drawdown maximum
        if self.max_drawdown >= self.limits['emergency_stop_loss']:
            self._trigger_emergency_stop(f"Drawdown max: {self.max_drawdown:.2f} USDT")
            return
    
    def _trigger_emergency_stop(self, reason: str):
        """Active l'arrêt d'urgence"""
        if not self.emergency_stop:
            self.emergency_stop = True
            self.stop_reason = reason
            logger.critical(f"🚨 ARRÊT D'URGENCE: {reason}")
    
    def _format_quantity(self, quantity: float) -> float:
        """Formate la quantité selon les règles Binance"""
        # Pour BTCUSDT: 3 décimales
        return round(quantity, 3)
    
    def get_risk_metrics(self) -> RiskMetrics:
        """Retourne les métriques de risque actuelles"""
        return RiskMetrics(
            daily_pnl=round(self.daily_pnl, 2),
            daily_trades=self.daily_trades,
            consecutive_losses=self.consecutive_losses,
            max_drawdown=round(self.max_drawdown, 2),
            current_exposure=0.0,  # À implémenter avec positions ouvertes
            risk_limit_used=round((abs(self.daily_pnl) / self.limits['max_daily_loss']) * 100, 1)
        )
    
    def get_status_report(self) -> str:
        """Génère un rapport de statut du risque"""
        metrics = self.get_risk_metrics()
        
        status = "🟢 NORMAL"
        if self.emergency_stop:
            status = "🔴 ARRÊT D'URGENCE"
        elif self._is_daily_limit_reached():
            status = "🟡 LIMITES ATTEINTES"
        elif metrics.consecutive_losses >= 3:
            status = "🟠 ATTENTION"
        
        report = f"""
📊 RAPPORT RISQUE - {status}
💰 Solde: {self.account_balance:.2f} USDT
📈 PnL Jour: {metrics.daily_pnl:+.2f} USDT
📋 Trades Jour: {metrics.daily_trades}/{self.limits['max_daily_trades']}
💥 Pertes Consécutives: {metrics.consecutive_losses}/{self.limits['max_consecutive_losses']}
📉 Drawdown Max: {metrics.max_drawdown:.2f} USDT
⚠️ Limite Utilisée: {metrics.risk_limit_used:.1f}%
        """.strip()
        
        if self.emergency_stop:
            report += f"\n🚨 Raison arrêt: {self.stop_reason}"
        
        return report
    
    def reset_daily_limits(self):
        """Remet à zéro les limites journalières (à appeler à minuit)"""
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.trades_today = []
        logger.info("🔄 Limites journalières réinitialisées")
    
    def override_emergency_stop(self, reason: str):
        """Override manuel de l'arrêt d'urgence (avec raison)"""
        if self.emergency_stop:
            self.emergency_stop = False
            self.stop_reason = None
            logger.warning(f"⚠️ Arrêt d'urgence désactivé manuellement: {reason}")
    
    def simulate_trade_impact(self, position_size: PositionSize, result: str) -> Dict:
        """Simule l'impact d'un trade sur les métriques de risque"""
        if result == 'win':
            pnl = position_size.risk_amount * self.config['tp_ratio']
        else:
            pnl = -position_size.risk_amount
        
        simulated_balance = self.account_balance + pnl
        simulated_daily_pnl = self.daily_pnl + pnl
        simulated_consecutive_losses = self.consecutive_losses + (1 if result == 'loss' else 0)
        
        return {
            'new_balance': simulated_balance,
            'new_daily_pnl': simulated_daily_pnl,
            'new_consecutive_losses': simulated_consecutive_losses,
            'would_trigger_emergency': simulated_balance <= (self.initial_balance - self.limits['emergency_stop_loss']),
            'would_hit_daily_limit': simulated_daily_pnl <= -self.limits['max_daily_loss']
        }