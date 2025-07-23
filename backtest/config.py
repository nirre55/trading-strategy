# config.py
"""
Configuration centralisée pour le système de backtest
"""

# Bloc de configuration centralisé
CONFIG = {
    # Capital & gestion du risque
    "capital_initial": 1000,
    "risk_par_trade": 10,

    # Martingale
    "martingale_enabled": True,
    "martingale_type": "none",   # Options: "normal", "reverse", "none"
    "martingale_multiplier": 2.0,
    "win_streak_max": 3,

    # RSI
    "rsi_periods": [5, 14, 21],
    "rsi_mtf_period": 14,
    "rsi_mtf_tf": "15min",

    # EMA
    "ema_period": 200,
    "ema_slope_lookback": 5,

    # SL/TP
    "sl_buffer_pct": 0.001,
    "tp_ratio": 0.5
}

# Configuration centralisée pour activer/désactiver les filtres
FILTERS = {
    "filter_ha": True,
    "filter_trend": False,
    "filter_mtf_rsi": True
}