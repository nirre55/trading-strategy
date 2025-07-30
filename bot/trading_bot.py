"""
Bot principal pour le trading avec Heikin Ashi et RSI
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
from indicators import compute_heikin_ashi, calculate_multiple_rsi, get_ha_candle_color
from signals import TradingSignals

class HeikinAshiRSIBot:
    def __init__(self):
        self.binance_client = BinanceClient()
        self.df = pd.DataFrame()
        self.ha_df = pd.DataFrame()
        self.ws_handler = None
        self.running = True
        self.trading_signals = TradingSignals()  # Instance des signaux
        
        # Configuration du gestionnaire de signal pour arrêt propre
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
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
        
        # Calculer Heikin Ashi sur les données historiques
        self.ha_df = compute_heikin_ashi(self.df)
        
        print(f"Données historiques chargées: {len(self.df)} bougies")
        return True
    
    def update_dataframe(self, kline_data):
        """Met à jour le DataFrame avec une nouvelle bougie"""
        # Vérifier que le DataFrame est initialisé
        if self.df is None:
            print("DataFrame non initialisé")
            return False
            
        formatted_data = self.binance_client.format_kline_data(kline_data)
        
        # Si la bougie n'est pas fermée, ne pas mettre à jour pour éviter les incohérences
        # Les calculs RSI se basent uniquement sur les bougies fermées
        if not formatted_data['is_closed']:
            if config.LOG_SETTINGS['SHOW_DATAFRAME_UPDATES']:
                print(f"Bougie en cours - pas de mise à jour des calculs")
            return False
        
        # Si la bougie est fermée, l'ajouter comme nouvelle ligne
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
            # Vérifier si c'est une nouvelle bougie
            last_open_time = self.df.iloc[-1]['open_time']
            if formatted_data['open_time'] > last_open_time:
                # Nouvelle bougie - ajouter une nouvelle ligne
                new_index = len(self.df)
                for col, value in new_row_data.items():
                    self.df.loc[new_index, col] = value
                
                # Garder seulement les dernières bougies pour optimiser la mémoire
                if len(self.df) > config.INITIAL_KLINES_LIMIT:
                    self.df = self.df.tail(config.INITIAL_KLINES_LIMIT).reset_index(drop=True)
                
                if config.LOG_SETTINGS['SHOW_DATAFRAME_UPDATES']:
                    print(f"Nouvelle bougie ajoutée: {formatted_data['open_time']}")
            else:
                # Mise à jour de la dernière bougie fermée (rare, mais possible)
                last_index = self.df.index[-1]
                for col, value in new_row_data.items():
                    self.df.loc[last_index, col] = value
                
                if config.LOG_SETTINGS['SHOW_DATAFRAME_UPDATES']:
                    print(f"Bougie mise à jour: {formatted_data['open_time']}")
                # Mise à jour de la dernière bougie fermée (rare, mais possible)
                last_index = self.df.index[-1]
                for col, value in new_row_data.items():
                    self.df.loc[last_index, col] = value
                
                if config.SHOW_DEBUG:
                    print(f"Bougie mise à jour: {formatted_data['open_time']}")
        
        return True  # Bougie fermée traitée
    
    def calculate_and_display_indicators(self):
        """Calcule et affiche les indicateurs"""
        # Vérifier que le DataFrame est initialisé et a assez de données
        if self.df is None or len(self.df) < max(config.RSI_PERIODS) + 1:
            return
        
        # Calculer Heikin Ashi
        self.ha_df = compute_heikin_ashi(self.df)
        
        # Calculer les RSI sur les prix de clôture Heikin Ashi
        rsi_values = calculate_multiple_rsi(self.ha_df['HA_close'], config.RSI_PERIODS)
        
        # Obtenir les dernières valeurs
        last_ha = self.ha_df.iloc[-1]
        last_rsi = {key: values.iloc[-1] for key, values in rsi_values.items()}
        
        # Déterminer la couleur de la bougie HA
        candle_color = get_ha_candle_color(last_ha['HA_open'], last_ha['HA_close'])
        
        # Analyser les signaux de trading
        signals_analysis = self.trading_signals.analyze_signals(
            last_rsi, 
            last_ha['HA_open'], 
            last_ha['HA_close']
        )
        
        # Affichage coloré
        self.display_results(last_ha, last_rsi, candle_color, signals_analysis)
    
    def display_results(self, ha_data, rsi_data, candle_color, signals_analysis):
        """Affiche les résultats dans la console avec couleurs"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Couleur pour la bougie
        color_code = config.COLORS['green'] if candle_color == 'green' else config.COLORS['red']
        if candle_color == 'doji':
            color_code = config.COLORS['yellow']
        
        print(f"\n{config.COLORS['cyan']}{config.DISPLAY_SYMBOLS['SEPARATOR']}{config.COLORS['reset']}")
        print(f"{config.COLORS['bold']}[{timestamp}] {config.SYMBOL} - {config.TIMEFRAME}{config.COLORS['reset']}")
        print(f"{config.COLORS['cyan']}{config.DISPLAY_SYMBOLS['SEPARATOR']}{config.COLORS['reset']}")
        
        # Afficher les données Heikin Ashi
        print(f"{config.COLORS['white']}Heikin Ashi:{config.COLORS['reset']}")
        print(f"  Open:  {ha_data['HA_open']:.6f}")
        print(f"  High:  {ha_data['HA_high']:.6f}")
        print(f"  Low:   {ha_data['HA_low']:.6f}")
        print(f"  Close: {ha_data['HA_close']:.6f}")
        print(f"  Couleur: {color_code}{candle_color.upper()}{config.COLORS['reset']}")
        
        # Afficher les RSI avec arrondi intelligent
        print(f"\n{config.COLORS['white']}RSI sur Heikin Ashi:{config.COLORS['reset']}")
        for rsi_name, rsi_value in rsi_data.items():
            if not np.isnan(rsi_value):
                # Couleur selon la valeur du RSI
                if rsi_value >= 70:
                    rsi_color = config.COLORS['red']  # Surachat
                elif rsi_value <= 30:
                    rsi_color = config.COLORS['green']  # Survente
                else:
                    rsi_color = config.COLORS['white']  # Neutre
                
                print(f"  {rsi_name}: {rsi_color}{rsi_value}{config.COLORS['reset']}")
            else:
                print(f"  {rsi_name}: N/A (pas assez de données)")
        
        # Afficher les signaux de trading
        self.display_trading_signals(signals_analysis)
        
        # Affichage de debug - nombre de bougies utilisées
        if config.SHOW_DEBUG:
            print(f"\n{config.COLORS['yellow']}Debug:{config.COLORS['reset']}")
            print(f"  Nombre de bougies: {len(self.df)}")
            print(f"  Dernière bougie: {self.df.iloc[-1]['open_time']}")
            print(f"  Prix de clôture classique: {self.df.iloc[-1]['close']:.6f}")
            print(f"  Prix de clôture HA: {ha_data['HA_close']:.6f}")
            
            # Debug des calculs RSI si activé
            if config.LOG_SETTINGS['SHOW_RSI_CALCULATIONS']:
                print(f"  Seuils RSI: Survente={config.SIGNAL_SETTINGS['RSI_OVERSOLD_THRESHOLD']} | Surachat={config.SIGNAL_SETTINGS['RSI_OVERBOUGHT_THRESHOLD']}")
            
            # Debug des calculs HA si activé  
            if config.LOG_SETTINGS['SHOW_HA_CALCULATIONS']:
                print(f"  HA Open vs Close: {ha_data['HA_open']:.6f} vs {ha_data['HA_close']:.6f}")
                print(f"  Couleur bougie: {candle_color}")
            
            # Debug de l'analyse des signaux si activé
            if config.LOG_SETTINGS['SHOW_SIGNAL_ANALYSIS']:
                print(f"  Signal détecté: {signals_analysis['type']}")
                print(f"  Signal valide: {signals_analysis['valid']}")
                print(f"  Compteur LONG: {signals_analysis['count']['LONG']}")
                print(f"  Compteur SHORT: {signals_analysis['count']['SHORT']}")
    
    def display_trading_signals(self, signals_analysis):
        """Affiche les signaux de trading"""
        # Vérifier si l'affichage des signaux est activé
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
            else:  # SHORT
                signal_color = config.COLORS['red']
            print(f"  {emoji} {config.COLORS['bold']}{signal_color}SIGNAL {signal_type} ACTIVÉ !{config.COLORS['reset']}")
        else:
            print(f"  {emoji} {config.COLORS['white']}Aucun signal{config.COLORS['reset']}")
        
        # Détails des conditions (si activé)
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
        
        # Compteurs de signaux (si activé)
        if config.SIGNAL_SETTINGS['SHOW_SIGNAL_COUNTERS']:
            counts = signals_analysis['count']
            print(f"\n{config.COLORS['white']}Compteurs:{config.COLORS['reset']}")
            print(f"  {config.DISPLAY_SYMBOLS['LONG_SIGNAL']} LONG: {config.COLORS['green']}{counts['LONG']}{config.COLORS['reset']} | {config.DISPLAY_SYMBOLS['SHORT_SIGNAL']} SHORT: {config.COLORS['red']}{counts['SHORT']}{config.COLORS['reset']}")
    
    def on_kline_update(self, kline_data):
        """Callback appelé lors de la mise à jour d'une bougie"""
        try:
            is_closed = self.update_dataframe(kline_data)
            
            # Ne calculer et afficher que si la bougie est fermée
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