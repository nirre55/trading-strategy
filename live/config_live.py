# config_live.py
"""
Configuration pour le trading live sur Binance Futures
"""
import os
from datetime import datetime

# Configuration de l'environnement
ENVIRONMENT = {
    "mode": "live",  # "testnet" ou "live" 
    "log_level": "INFO",  # DEBUG, INFO, WARNING, ERROR
    "auto_trade": False,  # False = surveillance seulement, True = trading auto
}

# Clés API Binance (à définir dans les variables d'environnement)
API_CONFIG = {
    "api_key": os.getenv("BINANCE_API_KEY", ""),
    "api_secret": os.getenv("BINANCE_API_SECRET", ""),
    "testnet": ENVIRONMENT["mode"] == "testnet"
}

# Configuration de trading
TRADING_CONFIG = {
    # Paire de trading
    "symbol": "BTCUSDT",
    "timeframe": "5m",
    
    # Capital et gestion du risque
    "max_balance_risk": 0.02,  # 2% du solde max par trade
    "min_position_size": 10,   # Position minimum en USDT
    "max_position_size": 100,  # Position maximum en USDT
    
    # Stratégie (reprend votre config backtest)
    "rsi_periods": [5, 14, 21],
    "rsi_oversold": 30,
    "rsi_overbought": 70,
    "rsi_mtf_period": 14,
    "rsi_mtf_tf": "15m",
    
    # EMA trend
    "ema_period": 200,
    "ema_slope_lookback": 5,
    
    # SL/TP
    "sl_buffer_pct": 0.001,
    "tp_ratio": 0.5,
    
    # Frais et slippage
    "trading_fees": 0.0004,  # 0.04% (maker/taker Binance Futures)
    "slippage": 0.0002,      # 0.02% slippage estimé
}

# Filtres activés
FILTERS_CONFIG = {
    "filter_ha": True,
    "filter_trend": False,
    "filter_mtf_rsi": True
}

# Configuration de surveillance
MONITORING_CONFIG = {
    "telegram_enabled": False,
    "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
    "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
    
    "discord_enabled": False,
    "discord_webhook": os.getenv("DISCORD_WEBHOOK", ""),
    
    "email_enabled": False,
    "email_smtp": "smtp.gmail.com",
    "email_port": 587,
    "email_user": os.getenv("EMAIL_USER", ""),
    "email_password": os.getenv("EMAIL_PASSWORD", ""),
    "email_to": os.getenv("EMAIL_TO", ""),
}

# Configuration base de données
DATABASE_CONFIG = {
    "enabled": True,
    "type": "sqlite",  # sqlite ou mysql
    "filename": f"live_trading_{datetime.now().strftime('%Y%m%d')}.db",
    "table_trades": "live_trades",
    "table_signals": "live_signals",
    "table_logs": "live_logs"
}

# Limites de sécurité
SAFETY_LIMITS = {
    "max_daily_trades": 50,
    "max_daily_loss": 100,  # USDT
    "max_consecutive_losses": 5,
    "emergency_stop_loss": 500,  # USDT - Stop total du bot
    
    # Surveillance technique
    "max_latency_ms": 1000,  # Latence max API
    "max_reconnect_attempts": 5,
    "heartbeat_interval": 30,  # secondes
}

# Configuration des logs
LOGGING_CONFIG = {
    "log_to_file": True,
    "log_to_console": True,
    "log_filename": f"live_bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
    "log_rotation": "midnight",
    "log_retention": 30,  # jours
}

# Validation de la configuration
def validate_config():
    """Valide la configuration avant le démarrage"""
    errors = []
    
    # Vérification API
    if not API_CONFIG["api_key"]:
        errors.append("BINANCE_API_KEY manquante")
    if not API_CONFIG["api_secret"]:
        errors.append("BINANCE_API_SECRET manquante")
    
    # Vérification Telegram si activé
    if MONITORING_CONFIG["telegram_enabled"]:
        if not MONITORING_CONFIG["telegram_bot_token"]:
            errors.append("TELEGRAM_BOT_TOKEN manquant")
        if not MONITORING_CONFIG["telegram_chat_id"]:
            errors.append("TELEGRAM_CHAT_ID manquant")
    
    # Vérification cohérence des paramètres
    if TRADING_CONFIG["min_position_size"] > TRADING_CONFIG["max_position_size"]:
        errors.append("min_position_size > max_position_size")
    
    if TRADING_CONFIG["tp_ratio"] <= 0:
        errors.append("tp_ratio doit être positif")
    
    return errors

# Configuration par défaut pour les tests
DEFAULT_TEST_CONFIG = {
    "symbol": "BTCUSDT",
    "position_size": 10,  # USDT
    "max_test_duration": 3600,  # 1 heure de test max
}