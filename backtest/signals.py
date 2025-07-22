# signals.py
"""
Module de génération des signaux de trading
"""

def rsi_condition(row, direction):
    """
    Vérifie les conditions RSI pour un signal
    """
    if direction == 'long':
        return row['RSI_5'] < 30 and row['RSI_14'] < 30 and row['RSI_21'] < 30
    elif direction == 'short':
        return row['RSI_5'] > 70 and row['RSI_14'] > 70 and row['RSI_21'] > 70
    return False

def ha_confirmation(row, direction):
    """
    Confirmation Heikin Ashi du signal
    """
    if direction == 'long':
        return row['HA_close'] > row['HA_open']
    elif direction == 'short':
        return row['HA_close'] < row['HA_open']
    return False

def trend_filter(row, direction):
    """
    Filtre de tendance basé sur EMA
    """
    if direction == 'long':
        return row['close'] > row['EMA'] and row['EMA_slope'] > 0
    elif direction == 'short':
        return row['close'] < row['EMA'] and row['EMA_slope'] < 0
    return False

def multi_tf_rsi_filter(row, direction):
    """
    Filtre RSI multi-timeframe
    """
    if direction == 'long':
        return row['RSI_mtf'] > 50
    elif direction == 'short':
        return row['RSI_mtf'] < 50
    return False

def check_signal_conditions(row, direction, filters_config):
    """
    Vérifie toutes les conditions de signal selon la configuration des filtres
    
    Args:
        row: Ligne du DataFrame avec les données
        direction: 'long' ou 'short'
        filters_config: Configuration des filtres activés
    
    Returns:
        bool: True si toutes les conditions sont remplies
    """
    # Condition RSI obligatoire
    if not rsi_condition(row, direction):
        return False
    
    # Vérification des filtres optionnels
    if filters_config.get("filter_ha", False):
        if not ha_confirmation(row, direction):
            return False
    
    if filters_config.get("filter_trend", False):
        if not trend_filter(row, direction):
            return False
    
    if filters_config.get("filter_mtf_rsi", False):
        if not multi_tf_rsi_filter(row, direction):
            return False
    
    return True