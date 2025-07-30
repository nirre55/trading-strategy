"""
Module pour la génération des signaux de trading
"""
import numpy as np
import config

class TradingSignals:
    def __init__(self):
        self.last_signal = None
        self.signal_count = {'LONG': 0, 'SHORT': 0}
        
        # Charger les paramètres depuis config
        self.rsi_oversold = config.SIGNAL_SETTINGS['RSI_OVERSOLD_THRESHOLD']
        self.rsi_overbought = config.SIGNAL_SETTINGS['RSI_OVERBOUGHT_THRESHOLD']
        self.required_periods = config.SIGNAL_SETTINGS['REQUIRED_RSI_PERIODS']
        
    def check_long_signal(self, rsi_values, ha_open, ha_close):
        """
        Vérifie les conditions pour un signal LONG
        Conditions configurables dans config.py
        """
        # Vérifier que tous les RSI sont disponibles
        rsi_conditions = []
        
        for period in self.required_periods:
            rsi_key = f'RSI_{period}'
            if rsi_key in rsi_values and not np.isnan(rsi_values[rsi_key]):
                rsi_conditions.append(rsi_values[rsi_key] < self.rsi_oversold)
            else:
                return False, f"RSI_{period} non disponible"
        
        # Tous les RSI doivent être < seuil de survente
        all_rsi_oversold = all(rsi_conditions)
        
        # Bougie Heikin Ashi verte (close > open)
        ha_green = ha_close > ha_open
        
        # Signal LONG si toutes les conditions sont réunies
        signal_valid = all_rsi_oversold and ha_green
        
        if signal_valid:
            reason = config.SIGNAL_SETTINGS['LONG_CONDITIONS']['description']
        else:
            reason = self._get_long_rejection_reason(rsi_values, ha_green)
        
        return signal_valid, reason
    
    def check_short_signal(self, rsi_values, ha_open, ha_close):
        """
        Vérifie les conditions pour un signal SHORT
        Conditions configurables dans config.py
        """
        # Vérifier que tous les RSI sont disponibles
        rsi_conditions = []
        
        for period in self.required_periods:
            rsi_key = f'RSI_{period}'
            if rsi_key in rsi_values and not np.isnan(rsi_values[rsi_key]):
                rsi_conditions.append(rsi_values[rsi_key] > self.rsi_overbought)
            else:
                return False, f"RSI_{period} non disponible"
        
        # Tous les RSI doivent être > seuil de surachat
        all_rsi_overbought = all(rsi_conditions)
        
        # Bougie Heikin Ashi rouge (close < open)
        ha_red = ha_close < ha_open
        
        # Signal SHORT si toutes les conditions sont réunies
        signal_valid = all_rsi_overbought and ha_red
        
        if signal_valid:
            reason = config.SIGNAL_SETTINGS['SHORT_CONDITIONS']['description']
        else:
            reason = self._get_short_rejection_reason(rsi_values, ha_red)
        
        return signal_valid, reason
    
    def _get_long_rejection_reason(self, rsi_values, ha_green):
        """Détermine pourquoi le signal LONG a été rejeté"""
        if not config.SIGNAL_SETTINGS['SHOW_REJECTION_REASONS']:
            return "Conditions non remplies"
            
        reasons = []
        
        for period in self.required_periods:
            rsi_key = f'RSI_{period}'
            if rsi_key in rsi_values:
                rsi_val = rsi_values[rsi_key]
                if rsi_val >= self.rsi_oversold:
                    reasons.append(f"RSI_{period}({rsi_val:.1f}) >= {self.rsi_oversold}")
        
        if not ha_green:
            reasons.append("HA Rouge/Doji")
        
        return " | ".join(reasons) if reasons else "Conditions non remplies"
    
    def _get_short_rejection_reason(self, rsi_values, ha_red):
        """Détermine pourquoi le signal SHORT a été rejeté"""
        if not config.SIGNAL_SETTINGS['SHOW_REJECTION_REASONS']:
            return "Conditions non remplies"
            
        reasons = []
        
        for period in self.required_periods:
            rsi_key = f'RSI_{period}'
            if rsi_key in rsi_values:
                rsi_val = rsi_values[rsi_key]
                if rsi_val <= self.rsi_overbought:
                    reasons.append(f"RSI_{period}({rsi_val:.1f}) <= {self.rsi_overbought}")
        
        if not ha_red:
            reasons.append("HA Verte/Doji")
        
        return " | ".join(reasons) if reasons else "Conditions non remplies"
    
    def analyze_signals(self, rsi_values, ha_open, ha_close):
        """
        Analyse complète des signaux
        Retourne le type de signal, sa validité et les détails
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
            'count': self.signal_count.copy()
        }
    
    def get_signal_emoji(self, signal_type):
        """Retourne l'emoji correspondant au signal depuis config"""
        if signal_type == 'LONG':
            return config.DISPLAY_SYMBOLS['LONG_SIGNAL']
        elif signal_type == 'SHORT':
            return config.DISPLAY_SYMBOLS['SHORT_SIGNAL']
        else:
            return config.DISPLAY_SYMBOLS['NEUTRAL_SIGNAL']
    
    def reset_counters(self):
        """Remet à zéro les compteurs de signaux"""
        self.signal_count = {'LONG': 0, 'SHORT': 0}
        self.last_signal = None