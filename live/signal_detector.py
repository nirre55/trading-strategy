# signal_detector.py
"""
Détecteur de signaux de trading en temps réel
Réutilise la logique validée du backtest
"""
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Signal:
    """Structure d'un signal de trading"""
    timestamp: datetime
    direction: str  # 'LONG' ou 'SHORT'
    rsi_signal_time: datetime
    validation_time: datetime
    confidence: float
    indicators: Dict
    reasons: list

class LiveSignalDetector:
    """Détecteur de signaux temps réel basé sur la stratégie backtest"""
    
    def __init__(self, config: Dict, filters_config: Dict):
        self.config = config
        self.filters = filters_config
        
        # État des signaux pending
        self.pending_long = False
        self.pending_short = False
        self.rsi_signal_timestamp_long = None
        self.rsi_signal_timestamp_short = None
        
        # Callbacks
        self.on_signal_callbacks = []
        self.on_rsi_detection_callbacks = []
        
        # Historique
        self.signals_history = []
        
    def add_signal_callback(self, callback):
        """Ajoute un callback appelé lors d'un nouveau signal"""
        self.on_signal_callbacks.append(callback)
    
    def add_rsi_detection_callback(self, callback):
        """Ajoute un callback appelé lors de la détection RSI"""
        self.on_rsi_detection_callbacks.append(callback)
    
    def process_new_data(self, market_data: Dict) -> Optional[Signal]:
        """
        Traite de nouvelles données et détecte les signaux
        Reprend exactement la logique du backtest
        """
        if not market_data or 'indicators' not in market_data:
            return None
        
        indicators = market_data['indicators']
        current_time = market_data['timestamp']
        
        # Vérification RSI (détection de base)
        rsi_long_signal = self._check_rsi_condition(indicators, 'long')
        rsi_short_signal = self._check_rsi_condition(indicators, 'short')
        
        # Détection des nouveaux signaux RSI
        if rsi_long_signal and not self.pending_long:
            self.pending_long = True
            self.rsi_signal_timestamp_long = current_time
            logger.info(f"🎯 RSI LONG signal détecté à {current_time}")
            
            # Callback RSI détection
            for callback in self.on_rsi_detection_callbacks:
                try:
                    callback('LONG', current_time, indicators)
                except Exception as e:
                    logger.error(f"Erreur callback RSI: {e}")
        
        elif rsi_short_signal and not self.pending_short:
            self.pending_short = True
            self.rsi_signal_timestamp_short = current_time
            logger.info(f"🎯 RSI SHORT signal détecté à {current_time}")
            
            # Callback RSI détection
            for callback in self.on_rsi_detection_callbacks:
                try:
                    callback('SHORT', current_time, indicators)
                except Exception as e:
                    logger.error(f"Erreur callback RSI: {e}")
        
        # Vérification des conditions complètes pour LONG
        if self.pending_long:
            signal = self._check_complete_conditions(indicators, current_time, 'LONG')
            if signal:
                self.pending_long = False
                self.rsi_signal_timestamp_long = None
                self._trigger_signal(signal)
                return signal
        
        # Vérification des conditions complètes pour SHORT
        if self.pending_short:
            signal = self._check_complete_conditions(indicators, current_time, 'SHORT')
            if signal:
                self.pending_short = False
                self.rsi_signal_timestamp_short = None
                self._trigger_signal(signal)
                return signal
        
        return None
    
    def _check_rsi_condition(self, indicators: Dict, direction: str) -> bool:
        """Vérifie les conditions RSI (même logique que le backtest)"""
        try:
            rsi_5 = indicators.get('RSI_5', 50)
            rsi_14 = indicators.get('RSI_14', 50)
            rsi_21 = indicators.get('RSI_21', 50)
            
            if direction == 'long':
                return (rsi_5 < self.config['rsi_oversold'] and 
                       rsi_14 < self.config['rsi_oversold'] and 
                       rsi_21 < self.config['rsi_oversold'])
            elif direction == 'short':
                return (rsi_5 > self.config['rsi_overbought'] and 
                       rsi_14 > self.config['rsi_overbought'] and 
                       rsi_21 > self.config['rsi_overbought'])
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur vérification RSI: {e}")
            return False
    
    def _check_ha_confirmation(self, indicators: Dict, direction: str) -> bool:
        """Vérifie la confirmation Heikin Ashi"""
        try:
            ha_close = indicators.get('HA_close', 0)
            ha_open = indicators.get('HA_open', 0)
            
            if direction == 'LONG':
                return ha_close > ha_open  # Bougie verte
            elif direction == 'SHORT':
                return ha_close < ha_open  # Bougie rouge
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur vérification HA: {e}")
            return False
    
    def _check_trend_filter(self, indicators: Dict, direction: str) -> bool:
        """Vérifie le filtre de tendance EMA"""
        try:
            current_price = indicators.get('close', 0)
            ema = indicators.get('EMA', 0)
            ema_slope = indicators.get('EMA_slope', 0)
            
            if direction == 'LONG':
                return current_price > ema and ema_slope > 0
            elif direction == 'SHORT':
                return current_price < ema and ema_slope < 0
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur vérification trend: {e}")
            return False
    
    def _check_mtf_rsi_filter(self, indicators: Dict, direction: str) -> bool:
        """Vérifie le filtre RSI multi-timeframe"""
        try:
            rsi_mtf = indicators.get('RSI_mtf', 50)
            
            if direction == 'LONG':
                return rsi_mtf > 50
            elif direction == 'SHORT':
                return rsi_mtf < 50
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur vérification MTF RSI: {e}")
            return False
    
    def _check_complete_conditions(self, indicators: Dict, current_time: datetime, direction: str) -> Optional[Signal]:
        """Vérifie toutes les conditions pour valider un signal"""
        reasons = []
        confidence = 0.0
        
        # RSI déjà validé (pending = True)
        reasons.append(f"RSI {direction.lower()}")
        confidence += 0.4
        
        # Vérification des filtres activés
        filters_passed = 0
        total_filters = 0
        
        # Filtre Heikin Ashi
        if self.filters.get('filter_ha', False):
            total_filters += 1
            if self._check_ha_confirmation(indicators, direction):
                reasons.append("HA confirmation")
                confidence += 0.3
                filters_passed += 1
            else:
                return None  # Filtre obligatoire non passé
        
        # Filtre tendance
        if self.filters.get('filter_trend', False):
            total_filters += 1
            if self._check_trend_filter(indicators, direction):
                reasons.append("Trend EMA")
                confidence += 0.2
                filters_passed += 1
            else:
                return None  # Filtre obligatoire non passé
        
        # Filtre RSI MTF
        if self.filters.get('filter_mtf_rsi', False):
            total_filters += 1
            if self._check_mtf_rsi_filter(indicators, direction):
                reasons.append("RSI MTF")
                confidence += 0.1
                filters_passed += 1
            else:
                return None  # Filtre obligatoire non passé
        
        # Calcul de la confiance finale
        if total_filters > 0:
            filter_confidence = filters_passed / total_filters
            confidence = min(confidence + filter_confidence * 0.3, 1.0)
        
        # Récupération du timestamp RSI initial
        rsi_timestamp = (self.rsi_signal_timestamp_long if direction == 'LONG' 
                        else self.rsi_signal_timestamp_short)
        
        # Création du signal
        signal = Signal(
            timestamp=current_time,
            direction=direction,
            rsi_signal_time=rsi_timestamp,
            validation_time=current_time,
            confidence=round(confidence, 2),
            indicators=indicators.copy(),
            reasons=reasons
        )
        
        logger.info(f"✅ Signal {direction} validé - Confiance: {confidence:.1%}")
        return signal
    
    def _trigger_signal(self, signal: Signal):
        """Déclenche les callbacks pour un nouveau signal"""
        self.signals_history.append(signal)
        
        for callback in self.on_signal_callbacks:
            try:
                callback(signal)
            except Exception as e:
                logger.error(f"Erreur callback signal: {e}")
    
    def get_status(self) -> Dict:
        """Retourne le statut du détecteur"""
        return {
            'pending_long': self.pending_long,
            'pending_short': self.pending_short,
            'rsi_long_since': self.rsi_signal_timestamp_long,
            'rsi_short_since': self.rsi_signal_timestamp_short,
            'signals_today': len([s for s in self.signals_history 
                                if s.timestamp.date() == datetime.now().date()]),
            'total_signals': len(self.signals_history)
        }
    
    def reset_pending_signals(self):
        """Reset manuel des signaux pending (pour debugging)"""
        self.pending_long = False
        self.pending_short = False
        self.rsi_signal_timestamp_long = None
        self.rsi_signal_timestamp_short = None
        logger.info("🔄 Signaux pending réinitialisés")

# Fonction utilitaire pour formater un signal
def format_signal_message(signal: Signal) -> str:
    """Formate un signal pour affichage/notification"""
    wait_time = signal.validation_time - signal.rsi_signal_time
    wait_minutes = wait_time.total_seconds() / 60
    
    message = f"""
🚨 SIGNAL {signal.direction} 
📅 {signal.validation_time.strftime('%H:%M:%S')}
⏱️ Attente: {wait_minutes:.1f}min
📊 Confiance: {signal.confidence:.1%}
🔍 Filtres: {', '.join(signal.reasons)}

📈 Indicateurs:
• RSI 5/14/21: {signal.indicators.get('RSI_5', 0):.1f}/{signal.indicators.get('RSI_14', 0):.1f}/{signal.indicators.get('RSI_21', 0):.1f}
• RSI MTF: {signal.indicators.get('RSI_mtf', 0):.1f}
• HA: {'🟢' if signal.indicators.get('HA_close', 0) > signal.indicators.get('HA_open', 0) else '🔴'}
    """.strip()
    
    return message