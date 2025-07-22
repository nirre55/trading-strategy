# trade_simulator.py
"""
Module de simulation des trades
"""

def calculate_sl_tp_levels(row, entry_price, direction, config):
    """
    Calcule les niveaux Stop Loss et Take Profit
    
    Args:
        row: Ligne de données courante
        entry_price: Prix d'entrée
        direction: 'long' ou 'short'
        config: Configuration des paramètres
    
    Returns:
        tuple: (sl_price, tp_price)
    """
    if direction == 'long':
        sl = row['HA_low'] * (1 - config["sl_buffer_pct"])
        tp = entry_price + (entry_price - sl) * config["tp_ratio"]
    else:  # short
        sl = row['HA_high'] * (1 + config["sl_buffer_pct"])
        tp = entry_price - (sl - entry_price) * config["tp_ratio"]
    
    return sl, tp

def validate_sl_tp_levels(entry, sl, tp, direction):
    """
    Valide la cohérence des niveaux SL/TP par rapport au prix d'entrée
    
    Returns:
        bool: True si les niveaux sont cohérents
    """
    if direction == 'long':
        if sl >= entry:
            print(f"ERREUR LONG: SL ({sl:.2f}) >= Entry ({entry:.2f})")
            return False
        if tp <= entry:
            print(f"ERREUR LONG: TP ({tp:.2f}) <= Entry ({entry:.2f})")
            return False
    else:  # short
        if sl <= entry:
            print(f"ERREUR SHORT: SL ({sl:.2f}) <= Entry ({entry:.2f})")
            return False
        if tp >= entry:
            print(f"ERREUR SHORT: TP ({tp:.2f}) >= Entry ({entry:.2f})")
            return False
    
    return True

def simulate_trade(df, start_index, entry, sl, tp, direction='long'):
    """
    Simule l'exécution d'un trade à partir d'un index donné
    
    Args:
        df: DataFrame avec les données OHLC
        start_index: Index de départ de la simulation
        entry: Prix d'entrée
        sl: Niveau Stop Loss
        tp: Niveau Take Profit
        direction: 'long' ou 'short'
    
    Returns:
        tuple: (résultat, timestamp_close)
    """
    # Validation des niveaux
    if not validate_sl_tp_levels(entry, sl, tp, direction):
        return 'error', None
    
    # Simulation bougie par bougie
    for j in range(start_index + 1, len(df)):
        row = df.iloc[j]
        timestamp_close = df.index[j]
        o, h, l, c = row['open'], row['high'], row['low'], row['close']

        if direction == 'long':
            if l <= sl:
                return 'loss', timestamp_close
            elif h >= tp:
                return 'win', timestamp_close
        else:  # short
            if h >= sl:
                return 'loss', timestamp_close
            elif l <= tp:
                return 'win', timestamp_close

    return 'open', None

class TradeManager:
    """
    Gestionnaire de trades avec gestion de la taille des positions
    """
    
    def __init__(self, config):
        self.config = config
        self.reset()
    
    def reset(self):
        """Remet à zéro les compteurs"""
        self.capital = self.config["capital_initial"]
        self.current_size = self.config["risk_par_trade"]
        self.win_streak = 0
        self.loss_streak = 0
        self.max_drawdown = 0
        self.peak_capital = self.capital
    
    def calculate_position_size(self):
        """Calcule la taille de position selon la stratégie martingale"""
        return self.current_size
    
    def update_position_size(self, result):
        """Met à jour la taille de position après un trade"""
        if result == 'win':
            self.win_streak += 1
            self.loss_streak = 0
            
            if self.config["martingale_enabled"] and self.config["martingale_type"] == "reverse":
                if self.win_streak < self.config["win_streak_max"]:
                    self.current_size *= self.config["martingale_multiplier"]
                else:
                    self.current_size = self.config["risk_par_trade"]
            else:
                self.current_size = self.config["risk_par_trade"]
                
        else:  # loss
            self.win_streak = 0
            self.loss_streak += 1
            
            if self.config["martingale_enabled"] and self.config["martingale_type"] == "normal":
                self.current_size *= self.config["martingale_multiplier"]
            else:
                self.current_size = self.config["risk_par_trade"]
    
    def update_capital(self, result, position_size):
        """
        Met à jour le capital après un trade en tenant compte du tp_ratio
        """
        if result == 'win':
            # Gain = risque × tp_ratio
            pnl = position_size * self.config.get("tp_ratio", 1.0)
        else:
            # Perte = risque complet
            pnl = -position_size
        
        self.capital += pnl
        self.peak_capital = max(self.peak_capital, self.capital)
        self.max_drawdown = max(self.max_drawdown, self.peak_capital - self.capital)
        
        return pnl