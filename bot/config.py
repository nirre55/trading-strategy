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