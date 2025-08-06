"""
Bot principal pour le trading avec Heikin Ashi et RSI - Avec Double Heikin Ashi
"""
import pandas as pd
import numpy as np
from datetime import datetime
import time
import signal
import sys

import config
from binance_client import BinanceClient
from websocket_handler import BinanceWebSocketHandler
from indicators import (compute_heikin_ashi, compute_double_heikin_ashi, 
                       calculate_multiple_rsi, get_ha_candle_color,
                       get_active_ha_data, get_rsi_source_data)
from signals import TradingSignals

class HeikinAshiRSIBot:
    def __init__(self):
        self.binance_client = BinanceClient()
        self.df = pd.DataFrame()
        self.ha_df = pd.DataFrame()
        self.ws_handler = None
        self.running = True
        self.trading_signals = TradingSignals()
        
        # Configuration du gestionnaire de signal pour arrêt propre
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Afficher la configuration du filtre Double HA au démarrage
        self._display_double_ha_config()
    
    def _display_double_ha_config(self):
        """Affiche la configuration du filtre Double Heikin Ashi"""
        filter_config = config.DOUBLE_HEIKIN_ASHI_FILTER
        
        if filter_config['ENABLED']:
            print(f"{config.COLORS['yellow']}{config.DISPLAY_SYMBOLS['DOUBLE_HA_SYMBOL']} Filtre Double Heikin Ashi ACTIVÉ{config.COLORS['reset']}")
            print(f"  - Signaux basés sur: {'HA2' if filter_config['USE_FOR_SIGNALS'] else 'HA1'}")
            print(f"  - RSI calculés sur: {'HA2' if filter_config['USE_FOR_RSI'] else 'HA1'}")
            print(f"  - Affichage: {'HA1 + HA2' if filter_config['SHOW_BOTH_IN_DISPLAY'] else 'Actif seulement'}")
        else:
            print(f"{config.COLORS['white']}Filtre Double Heikin Ashi désactivé (HA simple){config.COLORS['reset']}")
    
    def signal_handler(self, signum, frame):
        """Gestionnaire pour arrêt propre du bot"""
        print(f"\n{config.COLORS['yellow']}Arrêt du bot en cours...{config.COLORS['reset']}")
        self.running = False
        if self.ws_handler:
            self.ws_handler.stop()
        sys.exit(0)
    
    def initialize_historical_data(self):
        """Initialise avec les données historiques"""
        print(f"Récupération des données historiques pour {config.SYMBOL} {config.TIMEFRAME}...")
        
        historical_data = self.binance_client.get_historical_klines(
            config.SYMBOL, 
            config.TIMEFRAME, 
            config.INITIAL_KLINES_LIMIT
        )
        
        if historical_data is None or historical_data.empty:
            print("Impossible de récupérer les données historiques")
            return False
        
        self.df = historical_data
        
        # Calculer Heikin Ashi selon la configuration
        if config.DOUBLE_HEIKIN_ASHI_FILTER['ENABLED']:
            self.ha_df = compute_double_heikin_ashi(self.df)
        else:
            self.ha_df = compute_heikin_ashi(self.df)
        
        print(f"Données historiques chargées: {len(self.df)} bougies")
        return True
    
    def update_dataframe(self, kline_data):
        """Met à jour le DataFrame avec une nouvelle bougie"""
        if self.df is None:
            print("DataFrame non initialisé")
            return False
            
        formatted_data = self.binance_client.format_kline_data(kline_data)
        
        if not formatted_data['is_closed']:
            if config.LOG_SETTINGS['SHOW_DATAFRAME_UPDATES']:
                print(f"Bougie en cours - pas de mise à jour des calculs")
            return False
        
        new_row_data = {
            'open_time': formatted_data['open_time'],
            'close_time': formatted_data['close_time'],
            'open': formatted_data['open'],
            'high': formatted_data['high'],
            'low': formatted_data['low'],
            'close': formatted_data['close'],
            'volume': formatted_data['volume']
        }
        
        if self.df.empty:
            self.df = pd.DataFrame([new_row_data])
        else:
            last_open_time = self.df.iloc[-1]['open_time']
            if formatted_data['open_time'] > last_open_time:
                new_index = len(self.df)
                for col, value in new_row_data.items():
                    self.df.loc[new_index, col] = value
                
                if len(self.df) > config.INITIAL_KLINES_LIMIT:
                    self.df = self.df.tail(config.INITIAL_KLINES_LIMIT).reset_index(drop=True)
                
                if config.LOG_SETTINGS['SHOW_DATAFRAME_UPDATES']:
                    print(f"Nouvelle bougie ajoutée: {formatted_data['open_time']}")
            else:
                last_index = self.df.index[-1]
                for col, value in new_row_data.items():
                    self.df.loc[last_index, col] = value
                
                if config.LOG_SETTINGS['SHOW_DATAFRAME_UPDATES']:
                    print(f"Bougie mise à jour: {formatted_data['open_time']}")
        
        return True
    
    def calculate_and_display_indicators(self):
        """Calcule et affiche les indicateurs"""
        if self.df is None or len(self.df) < max(config.RSI_PERIODS) + 1:
            return
        
        # Calculer Heikin Ashi selon la configuration
        if config.DOUBLE_HEIKIN_ASHI_FILTER['ENABLED']:
            self.ha_df = compute_double_heikin_ashi(self.df)
        else:
            self.ha_df = compute_heikin_ashi(self.df)
        
        # Obtenir la source de données pour les RSI
        rsi_source_series, rsi_source_name = get_rsi_source_data(self.ha_df)
        
        # Calculer les RSI sur la source appropriée
        rsi_values = calculate_multiple_rsi(rsi_source_series, config.RSI_PERIODS)
        last_rsi = {key: values.iloc[-1] for key, values in rsi_values.items()}
        
        # Obtenir les données HA actives pour les signaux
        ha_open, ha_close, ha_high, ha_low, ha_source_name = get_active_ha_data(self.ha_df)
        
        # Données pour l'affichage
        display_data = {
            'ha_open': ha_open,
            'ha_close': ha_close, 
            'ha_high': ha_high,
            'ha_low': ha_low,
            'ha_source': ha_source_name,
            'rsi_source': rsi_source_name
        }
        
        # Déterminer la couleur de la bougie HA active
        candle_color = get_ha_candle_color(ha_open, ha_close)
        
        # Analyser les signaux de trading
        signals_analysis = self.trading_signals.analyze_signals(
            last_rsi, 
            ha_open, 
            ha_close,
            ha_source_name  # Passer la source HA pour les messages
        )
        
        # Décider si on doit afficher selon la configuration
        should_display = self.should_display_results(signals_analysis)
        
        if should_display == "minimal":
            self.display_minimal_info(display_data, last_rsi, candle_color, signals_analysis)
        elif should_display:
            self.display_results(display_data, last_rsi, candle_color, signals_analysis)
        elif signals_analysis['pending']['long'] or signals_analysis['pending']['short']:
            if config.SIGNAL_SETTINGS['SHOW_MINIMAL_INFO']:
                self.display_minimal_info(display_data, last_rsi, candle_color, signals_analysis)
            else:
                timestamp = datetime.now().strftime("%H:%M:%S")
                pending_status = self.trading_signals.get_pending_status()
                print(f"[{timestamp}] {config.SYMBOL} - {pending_status}")
        elif config.LOG_SETTINGS['SHOW_SIGNAL_ANALYSIS']:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {config.SYMBOL} - Aucun signal | LONG: {signals_analysis['count']['LONG']} | SHORT: {signals_analysis['count']['SHORT']}")
    
    def display_minimal_info(self, display_data, rsi_data, candle_color, signals_analysis):
        """Affichage minimal : couleur HA + RSI seulement"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Couleur pour la bougie HA
        if candle_color == 'green':
            ha_color = config.COLORS['green']
            ha_symbol = "🟢"
        elif candle_color == 'red':
            ha_color = config.COLORS['red']
            ha_symbol = "🔴"
        else:
            ha_color = config.COLORS['yellow']
            ha_symbol = "🟡"
        
        # Construire la ligne des RSI
        rsi_info = []
        for rsi_name, rsi_value in rsi_data.items():
            if not np.isnan(rsi_value):
                oversold_threshold = config.SIGNAL_SETTINGS['RSI_OVERSOLD_THRESHOLD']
                overbought_threshold = config.SIGNAL_SETTINGS['RSI_OVERBOUGHT_THRESHOLD']
                
                if rsi_value <= oversold_threshold:
                    rsi_color = config.COLORS['green']
                elif rsi_value >= overbought_threshold:
                    rsi_color = config.COLORS['red']
                else:
                    rsi_color = config.COLORS['white']
                
                rounded_rsi = round(rsi_value, 1)
                if rounded_rsi == int(rounded_rsi):
                    rsi_str = f"{int(rounded_rsi)}.0"
                else:
                    rsi_str = f"{rounded_rsi}"
                
                period = rsi_name.split('_')[1]
                rsi_info.append(f"{rsi_color}{period}:{rsi_str}{config.COLORS['reset']}")
            else:
                period = rsi_name.split('_')[1]
                rsi_info.append(f"{config.COLORS['white']}{period}:N/A{config.COLORS['reset']}")
        
        # Indication de signal si présent ou en attente
        signal_indicator = ""
        if signals_analysis['valid']:
            if signals_analysis['type'] == 'LONG':
                signal_indicator = f" {config.COLORS['green']}{config.COLORS['bold']}📈 LONG{config.COLORS['reset']}"
            else:
                signal_indicator = f" {config.COLORS['red']}{config.COLORS['bold']}📉 SHORT{config.COLORS['reset']}"
        elif signals_analysis['pending']['long']:
            signal_indicator = f" {config.COLORS['yellow']}🔄 LONG EN ATTENTE{config.COLORS['reset']}"
        elif signals_analysis['pending']['short']:
            signal_indicator = f" {config.COLORS['yellow']}🔄 SHORT EN ATTENTE{config.COLORS['reset']}"
        
        # Indicateur de source (HA1 ou HA2)
        source_indicator = ""
        if config.DOUBLE_HEIKIN_ASHI_FILTER['ENABLED']:
            source_indicator = f" {config.COLORS['cyan']}[{display_data['ha_source']}]{config.COLORS['reset']}"
        
        rsi_line = " | ".join(rsi_info)
        print(f"[{timestamp}] {ha_symbol} {ha_color}{candle_color.upper()}{config.COLORS['reset']}{source_indicator} | RSI: {rsi_line}{signal_indicator}")
    
    def should_display_results(self, signals_analysis):
        """Détermine si on doit afficher les résultats selon la configuration"""
        signal_valid = signals_analysis['valid']
        
        if config.SIGNAL_SETTINGS['SHOW_MINIMAL_INFO']:
            return "minimal"
        
        if config.SIGNAL_SETTINGS['SHOW_ALL_CANDLES']:
            return True
        
        if config.SIGNAL_SETTINGS['SHOW_ONLY_VALID_SIGNALS']:
            return signal_valid
        
        if config.SIGNAL_SETTINGS['SHOW_NEUTRAL_ANALYSIS']:
            return True
        
        return signal_valid
    
    def display_results(self, display_data, rsi_data, candle_color, signals_analysis):
        """Affiche les résultats dans la console avec couleurs"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        signal_type = signals_analysis['type']
        
        # Couleur pour la bougie
        color_code = config.COLORS['green'] if candle_color == 'green' else config.COLORS['red']
        if candle_color == 'doji':
            color_code = config.COLORS['yellow']
        
        # Titre avec emphasis sur le signal détecté
        signal_emoji = self.trading_signals.get_signal_emoji(signal_type)
        if signals_analysis['valid']:
            signal_color = config.COLORS['green'] if signal_type == 'LONG' else config.COLORS['red']
            title_signal = f" - {signal_color}{config.COLORS['bold']}🚨 {signal_type} SIGNAL 🚨{config.COLORS['reset']}"
        else:
            title_signal = ""
        
        print(f"\n{config.COLORS['cyan']}{config.DISPLAY_SYMBOLS['SEPARATOR']}{config.COLORS['reset']}")
        print(f"{config.COLORS['bold']}[{timestamp}] {config.SYMBOL} - {config.TIMEFRAME}{title_signal}{config.COLORS['reset']}")
        print(f"{config.COLORS['cyan']}{config.DISPLAY_SYMBOLS['SEPARATOR']}{config.COLORS['reset']}")
        
        # Afficher les données Heikin Ashi selon configuration
        self._display_heikin_ashi_data(display_data, color_code, candle_color)
        
        # Afficher les RSI
        self._display_rsi_data(rsi_data, display_data['rsi_source'], signals_analysis, signal_type)
        
        # Afficher les signaux de trading
        self.display_trading_signals(signals_analysis)
        
        # Afficher l'état d'attente si applicable
        pending_status = self.trading_signals.get_pending_status()
        if pending_status and not signals_analysis['valid']:
            print(f"\n{config.COLORS['yellow']}{config.COLORS['bold']}{pending_status}{config.COLORS['reset']}")
        
        # Affichage de debug
        if config.SHOW_DEBUG:
            self._display_debug_info(display_data, signals_analysis, candle_color)
    
    def _display_heikin_ashi_data(self, display_data, color_code, candle_color):
        """Affiche les données Heikin Ashi selon la configuration"""
        filter_config = config.DOUBLE_HEIKIN_ASHI_FILTER
        
        if filter_config['ENABLED'] and filter_config['SHOW_BOTH_IN_DISPLAY']:
            # Afficher HA1 et HA2
            print(f"{config.COLORS['white']}Heikin Ashi 1 (HA1):{config.COLORS['reset']}")
            ha1_data = self.ha_df.iloc[-1]
            ha1_color = get_ha_candle_color(ha1_data['HA_open'], ha1_data['HA_close'])
            ha1_color_code = config.COLORS['green'] if ha1_color == 'green' else config.COLORS['red']
            if ha1_color == 'doji':
                ha1_color_code = config.COLORS['yellow']
            
            print(f"  Open:  {ha1_data['HA_open']:.6f}")
            print(f"  High:  {ha1_data['HA_high']:.6f}")
            print(f"  Low:   {ha1_data['HA_low']:.6f}")
            print(f"  Close: {ha1_data['HA_close']:.6f}")
            print(f"  Couleur: {ha1_color_code}{ha1_color.upper()}{config.COLORS['reset']}")
            
            print(f"\n{config.COLORS['white']}Heikin Ashi 2 (HA2) {config.DISPLAY_SYMBOLS['DOUBLE_HA_SYMBOL']}:{config.COLORS['reset']}")
            print(f"  Open:  {display_data['ha_open']:.6f}")
            print(f"  High:  {display_data['ha_high']:.6f}")
            print(f"  Low:   {display_data['ha_low']:.6f}")
            print(f"  Close: {display_data['ha_close']:.6f}")
            print(f"  Couleur: {color_code}{candle_color.upper()}{config.COLORS['reset']}")
            
            # Indiquer quelle version est utilisée pour les signaux
            active_source = display_data['ha_source']
            print(f"\n{config.COLORS['cyan']}📊 Signaux basés sur: {active_source}{config.COLORS['reset']}")
            
        else:
            # Afficher seulement la version active
            ha_title = f"Heikin Ashi"
            if filter_config['ENABLED']:
                ha_title += f" 2 {config.DISPLAY_SYMBOLS['DOUBLE_HA_SYMBOL']} (Double)"
            
            print(f"{config.COLORS['white']}{ha_title}:{config.COLORS['reset']}")
            print(f"  Open:  {display_data['ha_open']:.6f}")
            print(f"  High:  {display_data['ha_high']:.6f}")
            print(f"  Low:   {display_data['ha_low']:.6f}")
            print(f"  Close: {display_data['ha_close']:.6f}")
            print(f"  Couleur: {color_code}{candle_color.upper()}{config.COLORS['reset']}")
    
    def _display_rsi_data(self, rsi_data, rsi_source, signals_analysis, signal_type):
        """Affiche les données RSI avec indication de source"""
        rsi_title = f"RSI sur {rsi_source}"
        if config.DOUBLE_HEIKIN_ASHI_FILTER['ENABLED']:
            rsi_title += f" {config.DISPLAY_SYMBOLS['DOUBLE_HA_SYMBOL']}" if rsi_source == "HA2" else ""
        
        print(f"\n{config.COLORS['white']}{rsi_title}:{config.COLORS['reset']}")
        
        for rsi_name, rsi_value in rsi_data.items():
            if not np.isnan(rsi_value):
                oversold_threshold = config.SIGNAL_SETTINGS['RSI_OVERSOLD_THRESHOLD']
                overbought_threshold = config.SIGNAL_SETTINGS['RSI_OVERBOUGHT_THRESHOLD']
                
                if rsi_value <= oversold_threshold:
                    rsi_color = config.COLORS['green']
                    rsi_status = " (SURVENTE)" if signals_analysis['valid'] and signal_type == 'LONG' else ""
                elif rsi_value >= overbought_threshold:
                    rsi_color = config.COLORS['red']
                    rsi_status = " (SURACHAT)" if signals_analysis['valid'] and signal_type == 'SHORT' else ""
                else:
                    rsi_color = config.COLORS['white']
                    rsi_status = ""
                
                rounded_rsi = round(rsi_value, 1)
                if rounded_rsi == int(rounded_rsi):
                    rsi_str = f"{int(rounded_rsi)}.0"
                else:
                    rsi_str = f"{rounded_rsi}"
                
                print(f"  {rsi_name}: {rsi_color}{config.COLORS['bold']}{rsi_str}{rsi_status}{config.COLORS['reset']}")
            else:
                print(f"  {rsi_name}: N/A (pas assez de données)")
    
    def _display_debug_info(self, display_data, signals_analysis, candle_color):
        """Affiche les informations de debug"""
        print(f"\n{config.COLORS['yellow']}Debug:{config.COLORS['reset']}")
        print(f"  Nombre de bougies: {len(self.df)}")
        print(f"  Dernière bougie: {self.df.iloc[-1]['open_time']}")
        print(f"  Prix de clôture classique: {self.df.iloc[-1]['close']:.6f}")
        print(f"  Prix de clôture HA actif: {display_data['ha_close']:.6f}")
        
        # Debug du filtre Double HA si activé
        if config.DOUBLE_HEIKIN_ASHI_FILTER['ENABLED']:
            print(f"  HA1 Close: {self.ha_df.iloc[-1]['HA_close']:.6f}")
            print(f"  HA2 Close: {self.ha_df.iloc[-1]['HA2_close']:.6f}")
            print(f"  Source signaux: {display_data['ha_source']}")
            print(f"  Source RSI: {display_data['rsi_source']}")
        
        if config.LOG_SETTINGS['SHOW_RSI_CALCULATIONS']:
            print(f"  Seuils RSI: Survente={config.SIGNAL_SETTINGS['RSI_OVERSOLD_THRESHOLD']} | Surachat={config.SIGNAL_SETTINGS['RSI_OVERBOUGHT_THRESHOLD']}")
        
        if config.LOG_SETTINGS['SHOW_HA_CALCULATIONS']:
            print(f"  HA Open vs Close: {display_data['ha_open']:.6f} vs {display_data['ha_close']:.6f}")
            print(f"  Couleur bougie: {candle_color}")
        
        if config.LOG_SETTINGS['SHOW_SIGNAL_ANALYSIS']:
            print(f"  Signal détecté: {signals_analysis['type']}")
            print(f"  Signal valide: {signals_analysis['valid']}")
            print(f"  Compteur LONG: {signals_analysis['count']['LONG']}")
            print(f"  Compteur SHORT: {signals_analysis['count']['SHORT']}")
    
    def display_trading_signals(self, signals_analysis):
        """Affiche les signaux de trading"""
        if not config.SIGNAL_SETTINGS['SHOW_SIGNAL_DETAILS']:
            return
            
        signal_type = signals_analysis['type']
        signal_valid = signals_analysis['valid']
        
        print(f"\n{config.COLORS['bold']}{config.DISPLAY_SYMBOLS['TRADING_SIGNALS_TITLE']} SIGNAUX DE TRADING:{config.COLORS['reset']}")
        
        # Signal principal
        emoji = self.trading_signals.get_signal_emoji(signal_type)
        if signal_valid:
            if signal_type == 'LONG':
                signal_color = config.COLORS['green']
            else:
                signal_color = config.COLORS['red']
            print(f"  {emoji} {config.COLORS['bold']}{signal_color}SIGNAL {signal_type} ACTIVÉ !{config.COLORS['reset']}")
        else:
            print(f"  {emoji} {config.COLORS['white']}Aucun signal{config.COLORS['reset']}")
        
        # Détails des conditions
        if config.SIGNAL_SETTINGS['SHOW_SIGNAL_DETAILS']:
            print(f"\n{config.COLORS['white']}Conditions:{config.COLORS['reset']}")
            
            # Conditions LONG
            long_status = config.DISPLAY_SYMBOLS['CONDITION_MET'] if signals_analysis['long']['valid'] else config.DISPLAY_SYMBOLS['CONDITION_NOT_MET']
            long_color = config.COLORS['green'] if signals_analysis['long']['valid'] else config.COLORS['red']
            print(f"  {long_status} LONG:  {long_color}{signals_analysis['long']['reason']}{config.COLORS['reset']}")
            
            # Conditions SHORT
            short_status = config.DISPLAY_SYMBOLS['CONDITION_MET'] if signals_analysis['short']['valid'] else config.DISPLAY_SYMBOLS['CONDITION_NOT_MET']
            short_color = config.COLORS['green'] if signals_analysis['short']['valid'] else config.COLORS['red']
            print(f"  {short_status} SHORT: {short_color}{signals_analysis['short']['reason']}{config.COLORS['reset']}")
        
        # Compteurs de signaux
        if config.SIGNAL_SETTINGS['SHOW_SIGNAL_COUNTERS']:
            counts = signals_analysis['count']
            print(f"\n{config.COLORS['white']}Compteurs:{config.COLORS['reset']}")
            print(f"  {config.DISPLAY_SYMBOLS['LONG_SIGNAL']} LONG: {config.COLORS['green']}{counts['LONG']}{config.COLORS['reset']} | {config.DISPLAY_SYMBOLS['SHORT_SIGNAL']} SHORT: {config.COLORS['red']}{counts['SHORT']}{config.COLORS['reset']}")
    
    def on_kline_update(self, kline_data):
        """Callback appelé lors de la mise à jour d'une bougie"""
        try:
            is_closed = self.update_dataframe(kline_data)
            
            if is_closed:
                self.calculate_and_display_indicators()
                
        except Exception as e:
            print(f"Erreur lors du traitement de la bougie: {e}")
    
    def start(self):
        """Démarre le bot"""
        print(f"{config.COLORS['bold']}{config.COLORS['cyan']}")
        print("=" * 60)
        print("   BOT HEIKIN ASHI RSI - BINANCE FUTURES")
        print("=" * 60)
        print(f"{config.COLORS['reset']}")
        
        print(f"Configuration:")
        print(f"  Symbole: {config.SYMBOL}")
        print(f"  Timeframe: {config.TIMEFRAME}")
        print(f"  Périodes RSI: {config.RSI_PERIODS}")
        print(f"  Données historiques: {config.INITIAL_KLINES_LIMIT} bougies")
        
        # Initialiser les données historiques
        if not self.initialize_historical_data():
            return
        
        # Calculer et afficher les indicateurs initiaux
        print(f"\n{config.COLORS['yellow']}Calcul des indicateurs initiaux...{config.COLORS['reset']}")
        self.calculate_and_display_indicators()
        
        # Démarrer le WebSocket
        print(f"\n{config.COLORS['yellow']}Démarrage du WebSocket...{config.COLORS['reset']}")
        self.ws_handler = BinanceWebSocketHandler(
            config.SYMBOL, 
            config.TIMEFRAME, 
            self.on_kline_update
        )
        
        self.ws_handler.start()
        
        if not self.ws_handler.wait_for_connection():
            print("Impossible de se connecter au WebSocket")
            return
        
        print(f"{config.COLORS['green']}Bot démarré avec succès!{config.COLORS['reset']}")
        print(f"{config.COLORS['yellow']}Appuyez sur Ctrl+C pour arrêter{config.COLORS['reset']}")
        
        # Boucle principale
        try:
            while self.running and self.ws_handler.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.signal_handler(None, None)

if __name__ == "__main__":
    bot = HeikinAshiRSIBot()
    bot.start()