"""
Configuration du bot de trading Binance Futures
"""

# Configuration du symbole et timeframe
SYMBOL = "BTCUSDT"
TIMEFRAME = "1m"  # 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M

# Configuration des périodes RSI
RSI_PERIODS = [5, 14, 21]

# Configuration WebSocket
WEBSOCKET_URL = "wss://fstream.binance.com/ws/"

# Nombre de bougies historiques à récupérer au démarrage
INITIAL_KLINES_LIMIT = 500

# Configuration d'affichage
SHOW_DEBUG = False

# Configuration du filtre Double Heikin Ashi
DOUBLE_HEIKIN_ASHI_FILTER = {
    'ENABLED': True,  # True pour activer le double calcul HA
    'USE_FOR_SIGNALS': True,  # True: utiliser HA2 pour les signaux, False: garder HA1
    'USE_FOR_RSI': False,  # True: calculer RSI sur HA2, False: calculer RSI sur HA1
    'SHOW_BOTH_IN_DISPLAY': True,  # True: afficher HA1 et HA2, False: afficher seulement celui utilisé
    'DESCRIPTION': 'Double Heikin Ashi: Calcul HA sur les données HA pour plus de lissage',
    
    # Explications des combinaisons possibles:
    # ENABLED=True, USE_FOR_SIGNALS=True, USE_FOR_RSI=True   -> Signaux et RSI basés sur HA2 (plus lisse)
    # ENABLED=True, USE_FOR_SIGNALS=True, USE_FOR_RSI=False  -> Signaux sur HA2, RSI sur HA1 (mixte)
    # ENABLED=True, USE_FOR_SIGNALS=False, USE_FOR_RSI=True  -> Signaux sur HA1, RSI sur HA2 (mixte) 
    # ENABLED=True, USE_FOR_SIGNALS=False, USE_FOR_RSI=False -> Double calcul mais utilise HA1 (pour comparaison)
}

# Configuration des signaux de trading
SIGNAL_SETTINGS = {
    # Configuration des signaux
    'RSI_OVERSOLD_THRESHOLD': 30,    # Seuil de survente pour signal LONG
    'RSI_OVERBOUGHT_THRESHOLD': 70,  # Seuil de surachat pour signal SHORT
    
    # Périodes RSI requises pour les signaux (doit correspondre à RSI_PERIODS)
    'REQUIRED_RSI_PERIODS': [5, 14, 21],
    
    # Mode de déclenchement des signaux
    'SIGNAL_MODE': 'DELAYED',  # 'IMMEDIATE' ou 'DELAYED'
    # IMMEDIATE: Toutes les conditions doivent être réunies en même temps
    # DELAYED: RSI d'abord, puis attendre le changement de couleur HA
    
    # Conditions des signaux
    'LONG_CONDITIONS': {
        'rsi_all_below_threshold': True,    # Tous les RSI < seuil survente
        'ha_candle_green': True,            # Bougie HA verte (close > open)
        'description': 'RSI(5,14,21) < 30 + HA Verte'
    },
    
    'SHORT_CONDITIONS': {
        'rsi_all_above_threshold': True,    # Tous les RSI > seuil surachat  
        'ha_candle_red': True,              # Bougie HA rouge (close < open)
        'description': 'RSI(5,14,21) > 70 + HA Rouge'
    },
    
    # Options d'affichage des signaux
    'SHOW_SIGNAL_DETAILS': True,           # Afficher les détails des conditions
    'SHOW_SIGNAL_COUNTERS': True,          # Afficher les compteurs de signaux
    'SHOW_REJECTION_REASONS': True,        # Afficher pourquoi un signal est rejeté
    'SHOW_ONLY_VALID_SIGNALS': True,       # Afficher SEULEMENT les signaux valides
    'SHOW_ALL_CANDLES': False,             # Afficher toutes les bougies (même sans signal)
    'SHOW_NEUTRAL_ANALYSIS': False,        # Afficher l'analyse même quand pas de signal
    'SHOW_MINIMAL_INFO': True,            # Afficher seulement couleur HA + RSI à chaque bougie
    
    # Alertes sonores (pour extension future)
    'SOUND_ALERTS': False,                  # Alertes sonores pour les signaux
    'ALERT_LONG_SOUND': 'beep_long.wav',   # Fichier son pour signal LONG
    'ALERT_SHORT_SOUND': 'beep_short.wav', # Fichier son pour signal SHORT
}

# Emojis et symboles pour l'affichage
DISPLAY_SYMBOLS = {
    'LONG_SIGNAL': '🟢',
    'SHORT_SIGNAL': '🔴',
    'NEUTRAL_SIGNAL': '⚪',
    'CONDITION_MET': '✅',
    'CONDITION_NOT_MET': '❌',
    'SEPARATOR': '='*60,
    'TRADING_SIGNALS_TITLE': '🎯',
    'DOUBLE_HA_SYMBOL': '🔄',  # Symbole pour Double HA
}

# Couleurs pour l'affichage console
COLORS = {
    'green': '\033[92m',
    'red': '\033[91m',
    'yellow': '\033[93m',
    'blue': '\033[94m',
    'magenta': '\033[95m',
    'cyan': '\033[96m',
    'white': '\033[97m',
    'reset': '\033[0m',
    'bold': '\033[1m'
}

# Configuration des niveaux de log
LOG_SETTINGS = {
    'SHOW_WEBSOCKET_DEBUG': False,         # Messages debug WebSocket
    'SHOW_DATAFRAME_UPDATES': False,       # Messages mise à jour DataFrame
    'SHOW_SIGNAL_ANALYSIS': False,         # Messages analyse des signaux
    'SHOW_RSI_CALCULATIONS': False,        # Messages calculs RSI
    'SHOW_HA_CALCULATIONS': False,         # Messages calculs Heikin Ashi
    'SHOW_DOUBLE_HA_CALCULATIONS': False,  # Messages calculs Double Heikin Ashi
}