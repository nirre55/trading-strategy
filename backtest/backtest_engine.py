# backtest_engine.py
"""
Moteur principal de backtest
"""
from signals import check_signal_conditions
from trade_simulator import simulate_trade, calculate_sl_tp_levels, TradeManager

class BacktestEngine:
    """
    Moteur principal de backtest
    """
    
    def __init__(self, config, filters_config):
        self.config = config
        self.filters_config = filters_config
        self.trade_manager = TradeManager(config)
        self.reset()
    
    def reset(self):
        """Remet à zéro l'état du backtest"""
        self.trades = []
        self.logs = []
        self.pending_long = False
        self.pending_short = False
        self.trade_manager.reset()
        # Timestamps pour traçage des signaux
        self.rsi_signal_timestamp_long = None
        self.rsi_signal_timestamp_short = None
    
    def run_backtest(self, df):
        """
        STRATÉGIE EXACTEMENT COMME L'ORIGINAL :
        1. RSI surVENTE/surACHAT -> pending signal
        2. Attente PERSISTANTE (même si RSI change)
        3. Confirmation HA -> exécution + reset pending
        4. Filtres optionnels pour améliorer winrate
        """
        self.reset()
        
        for i in range(1, len(df) - 1):
            row = df.iloc[i]
            next_row = df.iloc[i + 1]
            timestamp = df.index[i + 1]
            current_timestamp = df.index[i]

            # DÉTECTION DES SIGNAUX RSI (base de la stratégie) - LOGIQUE ORIGINALE
            from signals import rsi_condition, ha_confirmation, trend_filter, multi_tf_rsi_filter
            
            if rsi_condition(row, 'long'):
                self.pending_long = True
                self.rsi_signal_timestamp_long = current_timestamp
                # Pas d'affichage console - seulement sauvegarde du timestamp
            elif rsi_condition(row, 'short'):
                self.pending_short = True
                self.rsi_signal_timestamp_short = current_timestamp
                # Pas d'affichage console - seulement sauvegarde du timestamp

            # EXÉCUTION LONG - LOGIQUE ORIGINALE EXACTE
            if (
                self.pending_long
                and (not self.filters_config.get("filter_ha", False) or ha_confirmation(row, 'long'))
                and (not self.filters_config.get("filter_trend", False) or trend_filter(row, 'long'))
                and (not self.filters_config.get("filter_mtf_rsi", False) or multi_tf_rsi_filter(row, 'long'))
            ):
                # Pas d'affichage console - données sauvegardées dans les logs
                self._execute_trade(row, next_row, timestamp, df, i, 'long')
                self.pending_long = False
                if hasattr(self, 'rsi_signal_timestamp_long'):
                    delattr(self, 'rsi_signal_timestamp_long')

            # EXÉCUTION SHORT - LOGIQUE ORIGINALE EXACTE
            if (
                self.pending_short
                and (not self.filters_config.get("filter_ha", False) or ha_confirmation(row, 'short'))
                and (not self.filters_config.get("filter_trend", False) or trend_filter(row, 'short'))
                and (not self.filters_config.get("filter_mtf_rsi", False) or multi_tf_rsi_filter(row, 'short'))
            ):
                # Pas d'affichage console - données sauvegardées dans les logs
                self._execute_trade(row, next_row, timestamp, df, i, 'short')
                self.pending_short = False
                if hasattr(self, 'rsi_signal_timestamp_short'):
                    delattr(self, 'rsi_signal_timestamp_short')
        
        return self.trades, self.logs, self.trade_manager.max_drawdown
    
    def _update_pending_signals(self, row):
        """Met à jour les signaux en attente"""
        # Détection de nouveaux signaux (comme dans le script original)
        if check_signal_conditions(row, 'long', {'filter_ha': False, 'filter_trend': False, 'filter_mtf_rsi': False}):
            self.pending_long = True
        elif check_signal_conditions(row, 'short', {'filter_ha': False, 'filter_trend': False, 'filter_mtf_rsi': False}):
            self.pending_short = True
    
    def _check_and_execute_long(self, row, next_row, timestamp, df, i):
        """Vérifie et exécute un trade long si conditions remplies"""
        if not self.pending_long:
            return
        
        # Vérification de toutes les conditions (RSI + filtres)
        if not check_signal_conditions(row, 'long', self.filters_config):
            return
        
        # Exécution du trade
        self._execute_trade(row, next_row, timestamp, df, i, 'long')
        self.pending_long = False
    
    def _check_and_execute_short(self, row, next_row, timestamp, df, i):
        """Vérifie et exécute un trade short si conditions remplies"""
        if not self.pending_short:
            return
        
        # Vérification de toutes les conditions (RSI + filtres)
        if not check_signal_conditions(row, 'short', self.filters_config):
            return
        
        # Exécution du trade
        self._execute_trade(row, next_row, timestamp, df, i, 'short')
        self.pending_short = False
    
    def _execute_trade(self, row, next_row, timestamp, df, i, direction):
        """Exécute un trade dans la direction spécifiée"""
        entry = next_row['open']
        sl, tp = calculate_sl_tp_levels(row, entry, direction, self.config)
        
        # Simulation du trade
        result, timestamp_close = simulate_trade(df, i + 1, entry, sl, tp, direction)
        
        if result == 'error':
            return
        
        # Gestion de la position et du capital
        position_size = self.trade_manager.calculate_position_size()
        pnl = self.trade_manager.update_capital(result, position_size)
        self.trade_manager.update_position_size(result)
        
        # Récupération du timestamp du signal RSI initial
        rsi_timestamp = None
        if direction == 'long' and hasattr(self, 'rsi_signal_timestamp_long'):
            rsi_timestamp = self.rsi_signal_timestamp_long
        elif direction == 'short' and hasattr(self, 'rsi_signal_timestamp_short'):
            rsi_timestamp = self.rsi_signal_timestamp_short
        
        # Enregistrement du trade avec timestamps détaillés pour le CSV
        self.trades.append(result)
        
        # Calcul du temps d'attente en minutes pour faciliter l'analyse
        wait_time_minutes = None
        if rsi_timestamp:
            wait_time_timedelta = df.index[i] - rsi_timestamp
            wait_time_minutes = wait_time_timedelta.total_seconds() / 60  # En minutes
        
        self.logs.append({
            "timestamp": timestamp,
            "rsi_signal_timestamp": rsi_timestamp,
            "validation_timestamp": df.index[i],
            "wait_time_minutes": round(wait_time_minutes, 1) if wait_time_minutes else None,
            "direction": direction.upper(),
            "entry_price": round(entry, 2),
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "result": result,
            "timestamp_close": timestamp_close,
            "position_size": round(position_size, 2),
            "pnl": round(pnl, 2),
            "capital": round(self.trade_manager.capital, 2),
            # Ajout des valeurs des indicateurs au moment de la validation
            "rsi_5": round(row.get('RSI_5', 0), 2),
            "rsi_14": round(row.get('RSI_14', 0), 2),
            "rsi_21": round(row.get('RSI_21', 0), 2),
            "rsi_mtf": round(row.get('RSI_mtf', 0), 2),
            "ha_close": round(row.get('HA_close', 0), 2),
            "ha_open": round(row.get('HA_open', 0), 2),
            "ha_direction": "GREEN" if row.get('HA_close', 0) > row.get('HA_open', 0) else "RED"
        })
        
        # Pas d'affichage console - console reste propre

def run_backtest(df, config, filters_config):
    """
    Fonction utilitaire pour lancer un backtest
    
    Args:
        df: DataFrame avec les données
        config: Configuration du backtest
        filters_config: Configuration des filtres
    
    Returns:
        tuple: (trades, logs, max_drawdown)
    """
    engine = BacktestEngine(config, filters_config)
    return engine.run_backtest(df)