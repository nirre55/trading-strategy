"""
Configuration du bot de trading Binance Futures
"""

# Configuration Asset & Symbol (centralisé)
ASSET_CONFIG = {
    'BALANCE_ASSET': 'USDC',            # Asset pour balance (USDT/USDC/BUSD)
    'SYMBOL': 'BTCUSDC',                # Symbole trading
    'TIMEFRAME': '5m',                  # 1m,3m,5m,15m,30m,1h,2h,4h,6h,8h,12h,1d,3d,1w,1M
}

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
    
}


# Configuration Trading avancée
TRADING_CONFIG = {
    'ENABLED': True,                       # Trading automatique (désactivé par défaut)
    'RISK_PERCENT': 5.0,                   # % du capital par trade
    
    # Configuration Take Profit (fixe depuis entrée)
    'TAKE_PROFIT_PERCENT': 0.15,            # TP à 0.15% depuis prix entrée

    # Configuration Stop Loss (basé sur bougies)
    'STOP_LOSS_LOOKBACK_CANDLES': 5,       # Regarder 5 dernières bougies
    'STOP_LOSS_OFFSET_PERCENT': 0.1,       # Offset 0.1% depuis low/high trouvé
    
    # Configuration ordres
    'ENTRY_ORDER_TYPE': 'LIMIT',           # MARKET ou LIMIT
    'LIMIT_SPREAD_PERCENT': 0.01,          # 0.01% pour prix limit
    'ORDER_EXECUTION_TIMEOUT': 60,         # Timeout attente exécution (secondes)
    
    # Configuration sécurité
    'MIN_BALANCE': 10,                      # Balance minimale
    'MAX_POSITIONS': 1,                     # Nb max positions simultanées

    # Configuration Fallback Market (NOUVEAU)
    'MARKET_FALLBACK_ENABLED': True,       # Activer fallback MARKET après timeout LIMIT
    'FALLBACK_MAX_SLIPPAGE': 0.03,         # Slippage maximum accepté pour fallback (%)
}


# Configuration sécurité supplémentaire
SAFETY_CONFIG = {
    'MAX_DAILY_TRADES': 1000,                 # Limite quotidienne de trades
    'CONFIRM_BEFORE_TRADE': False,           # Demander confirmation avant trade
    'EMERGENCY_STOP': False,                # Arrêt d'urgence (fermer tout)
    'LOG_TO_CONSOLE': True,                 # Afficher logs dans console aussi
}

# Configuration de connexion et résilience (NOUVEAU)
CONNECTION_CONFIG = {
'WEBSOCKET_RETRY_ENABLED': True,        # Activer reconnexion automatique WebSocket
    'WEBSOCKET_RETRY_INTERVAL': 30,         # Délai entre tentatives reconnexion (secondes)
    'WEBSOCKET_MAX_RETRIES': 0,             # Max tentatives (0 = infini)
    'WEBSOCKET_BACKOFF_MAX': 300,           # Délai maximum entre tentatives (5 min)
    'WEBSOCKET_HEALTH_CHECK': 60,           # Intervalle vérification santé connexion
    
    'SYNC_AFTER_RECONNECTION': True,        # Synchronisation obligatoire après reconnexion
    'BLOCK_TRADES_ON_POSITION': True,       # Bloquer nouveaux trades si position détectée
    'AUTO_CLEANUP_GHOST_TRADES': True,      # Nettoyage automatique trades fantômes
    'SAFE_MODE_DURATION': 300,              # Durée mode sécurisé après reconnexion (5 min)
}

# Configuration du système de retry API
RETRY_CONFIG = {
    # Défauts
    'DEFAULT_MAX_RETRIES': 5,
    'DEFAULT_DELAY': 10,                 # secondes
    'DEFAULT_BACKOFF_MULTIPLIER': 1.2,

    # Spécifiques par type d'opération
    'VALIDATION_RETRIES': 5,
    'VALIDATION_DELAY': 10,

    'PRICE_FETCH_RETRIES': 5,            # Récupération prix ticker
    'BALANCE_FETCH_RETRIES': 5,          # Récupération balance
    'POSITION_FETCH_RETRIES': 5,         # Récupération positions

    'ORDER_PLACEMENT_RETRIES': 3,        # Placement d'ordres
    'ORDER_STATUS_RETRIES': 3,           # Lecture statut ordre
    'ORDER_CANCELLATION_RETRIES': 3,     # Annulation d'ordres

    # Délais spécifiques
    'ORDER_DELAY': 5,                    # Délai entre tentatives de placement d'ordre
    'STATUS_CHECK_DELAY': 2,             # Délai entre lectures de statut
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