"""
Module pour la génération des signaux de trading - VERSION CORRIGÉE
"""
import numpy as np
import config

class TradingSignals:
    def __init__(self):
        self.last_signal = None
        self.signal_count = {'LONG': 0, 'SHORT': 0}
        
        # État des signaux en attente
        self.pending_long = False   # RSI ont été en survente, attente bougie verte
        self.pending_short = False  # RSI ont été en surachat, attente bougie rouge
        self.pending_since_candle = None  # Depuis quelle bougie on attend
        
        # Charger les paramètres depuis config
        self.rsi_oversold = config.SIGNAL_SETTINGS['RSI_OVERSOLD_THRESHOLD']
        self.rsi_overbought = config.SIGNAL_SETTINGS['RSI_OVERBOUGHT_THRESHOLD']
        self.required_periods = config.SIGNAL_SETTINGS['REQUIRED_RSI_PERIODS']
        self.signal_mode = config.SIGNAL_SETTINGS['SIGNAL_MODE']
        
    def check_rsi_conditions(self, rsi_values):
        """Vérifie les conditions RSI seulement"""
        # Vérifier que tous les RSI sont disponibles
        rsi_values_list = []
        
        for period in self.required_periods:
            rsi_key = f'RSI_{period}'
            if rsi_key in rsi_values and not np.isnan(rsi_values[rsi_key]):
                rsi_values_list.append(rsi_values[rsi_key])
            else:
                return None, None, f"RSI_{period} non disponible"
        
        # Vérifier conditions de survente (LONG)
        all_oversold = all(rsi <= self.rsi_oversold for rsi in rsi_values_list)
        
        # Vérifier conditions de surachat (SHORT)
        all_overbought = all(rsi >= self.rsi_overbought for rsi in rsi_values_list)
        
        return all_oversold, all_overbought, "OK"
    
    def check_long_signal(self, rsi_values, ha_open, ha_close):
        """
        Vérifie les conditions pour un signal LONG
        Mode DELAYED: Une fois RSI en survente détecté, on attend seulement la couleur HA
        """
        all_oversold, all_overbought, rsi_status = self.check_rsi_conditions(rsi_values)
        
        if rsi_status != "OK":
            return False, rsi_status
        
        ha_green = ha_close > ha_open
        
        if self.signal_mode == 'IMMEDIATE':
            # Mode classique : toutes les conditions en même temps
            signal_valid = all_oversold and ha_green
            if signal_valid:
                reason = "RSI(5,14,21) < 30 + HA Verte (IMMEDIATE)"
            else:
                reason = self._get_rejection_reason(all_oversold, ha_green, "LONG")
        else:
            # Mode DELAYED : RSI d'abord, puis attendre couleur HA (SANS annulation)
            if all_oversold and not self.pending_long:
                # Nouveau état d'attente LONG
                self.pending_long = True
                self.pending_short = False  # Annuler attente SHORT si active
                reason = "🔄 ATTENTE LONG: RSI < 30 détecté, attente bougie HA verte"
                return False, reason
            elif self.pending_long and ha_green:
                # Signal LONG déclenché ! (peu importe l'état actuel des RSI)
                signal_valid = True
                self.pending_long = False
                reason = "✅ SIGNAL LONG: Attente satisfaite avec HA Verte (DELAYED)"
                return signal_valid, reason
            elif self.pending_long and not ha_green:
                # Toujours en attente (on ne vérifie PLUS les RSI)
                reason = f"🔄 ATTENTE LONG: En attente bougie HA verte"
                return False, reason
            elif all_oversold and not self.pending_long:
                # RSI en survente mais pas encore en attente (cas edge)
                self.pending_long = True
                self.pending_short = False
                reason = "🔄 ATTENTE LONG: RSI < 30 détecté, attente bougie HA verte"
                return False, reason
            else:
                # Pas de conditions
                signal_valid = False
                reason = self._get_rejection_reason(all_oversold, ha_green, "LONG")
        
        return signal_valid, reason
    
    def check_short_signal(self, rsi_values, ha_open, ha_close):
        """
        Vérifie les conditions pour un signal SHORT
        Mode DELAYED: Une fois RSI en surachat détecté, on attend seulement la couleur HA
        """
        all_oversold, all_overbought, rsi_status = self.check_rsi_conditions(rsi_values)
        
        if rsi_status != "OK":
            return False, rsi_status
        
        ha_red = ha_close < ha_open
        
        if self.signal_mode == 'IMMEDIATE':
            # Mode classique : toutes les conditions en même temps
            signal_valid = all_overbought and ha_red
            if signal_valid:
                reason = "RSI(5,14,21) > 70 + HA Rouge (IMMEDIATE)"
            else:
                reason = self._get_rejection_reason(all_overbought, ha_red, "SHORT")
        else:
            # Mode DELAYED : RSI d'abord, puis attendre couleur HA (SANS annulation)
            if all_overbought and not self.pending_short:
                # Nouveau état d'attente SHORT
                self.pending_short = True
                self.pending_long = False  # Annuler attente LONG si active
                reason = "🔄 ATTENTE SHORT: RSI > 70 détecté, attente bougie HA rouge"
                return False, reason
            elif self.pending_short and ha_red:
                # Signal SHORT déclenché ! (peu importe l'état actuel des RSI)
                signal_valid = True
                self.pending_short = False
                reason = "✅ SIGNAL SHORT: Attente satisfaite avec HA Rouge (DELAYED)"
                return signal_valid, reason
            elif self.pending_short and not ha_red:
                # Toujours en attente (on ne vérifie PLUS les RSI)
                reason = f"🔄 ATTENTE SHORT: En attente bougie HA rouge"
                return False, reason
            elif all_overbought and not self.pending_short:
                # RSI en surachat mais pas encore en attente (cas edge)
                self.pending_short = True
                self.pending_long = False
                reason = "🔄 ATTENTE SHORT: RSI > 70 détecté, attente bougie HA rouge"
                return False, reason
            else:
                # Pas de conditions
                signal_valid = False
                reason = self._get_rejection_reason(all_overbought, ha_red, "SHORT")
        
        return signal_valid, reason
    
    def _get_rejection_reason(self, rsi_condition, ha_condition, signal_type):
        """Génère la raison du rejet du signal"""
        if not config.SIGNAL_SETTINGS['SHOW_REJECTION_REASONS']:
            return "Conditions non remplies"
        
        reasons = []
        
        if signal_type == "LONG":
            if not rsi_condition:
                reasons.append(f"RSI pas tous < {self.rsi_oversold}")
            if not ha_condition:
                reasons.append("HA pas verte")
        else:  # SHORT
            if not rsi_condition:
                reasons.append(f"RSI pas tous > {self.rsi_overbought}")
            if not ha_condition:
                reasons.append("HA pas rouge")
        
        return " | ".join(reasons) if reasons else "Conditions non remplies"
    
    def analyze_signals(self, rsi_values, ha_open, ha_close):
        """
        Analyse complète des signaux avec mode DELAYED corrigé
        """
        # Vérifier signal LONG
        long_valid, long_reason = self.check_long_signal(rsi_values, ha_open, ha_close)
        
        # Vérifier signal SHORT
        short_valid, short_reason = self.check_short_signal(rsi_values, ha_open, ha_close)
        
        # Déterminer le signal principal
        if long_valid:
            signal_type = "LONG"
            signal_valid = True
            self.signal_count['LONG'] += 1
            self.last_signal = "LONG"
        elif short_valid:
            signal_type = "SHORT"
            signal_valid = True
            self.signal_count['SHORT'] += 1
            self.last_signal = "SHORT"
        else:
            signal_type = "NEUTRAL"
            signal_valid = False
        
        return {
            'type': signal_type,
            'valid': signal_valid,
            'long': {
                'valid': long_valid,
                'reason': long_reason
            },
            'short': {
                'valid': short_valid,
                'reason': short_reason
            },
            'count': self.signal_count.copy(),
            'pending': {
                'long': self.pending_long,
                'short': self.pending_short
            }
        }
    
    def get_signal_emoji(self, signal_type):
        """Retourne l'emoji correspondant au signal depuis config"""
        if signal_type == 'LONG':
            return config.DISPLAY_SYMBOLS['LONG_SIGNAL']
        elif signal_type == 'SHORT':
            return config.DISPLAY_SYMBOLS['SHORT_SIGNAL']
        else:
            return config.DISPLAY_SYMBOLS['NEUTRAL_SIGNAL']
    
    def get_pending_status(self):
        """Retourne l'état des signaux en attente"""
        if self.pending_long:
            return "🔄 LONG EN ATTENTE"
        elif self.pending_short:
            return "🔄 SHORT EN ATTENTE"
        else:
            return None
    
    def reset_counters(self):
        """Remet à zéro les compteurs de signaux"""
        self.signal_count = {'LONG': 0, 'SHORT': 0}
        self.last_signal = None
        self.pending_long = False
        self.pending_short = False
    
    def force_reset_pending(self):
        """Force la remise à zéro des états d'attente"""
        self.pending_long = False
        self.pending_short = False