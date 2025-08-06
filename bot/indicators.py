"""
Module pour le calcul des indicateurs techniques - Avec Double Heikin Ashi
"""
import pandas as pd
import numpy as np
import config

def calculate_rsi(series, period):
    """Calcule le RSI pour une série de prix donnée"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def compute_heikin_ashi(df, prefix="HA"):
    """
    Calcule les valeurs Heikin Ashi
    
    Args:
        df: DataFrame avec colonnes 'open', 'high', 'low', 'close'
        prefix: Préfixe pour les colonnes de sortie (ex: "HA" ou "HA2")
    
    Returns:
        DataFrame avec colonnes préfixées (ex: HA_open, HA_high, HA_low, HA_close)
    """
    ha = df.copy()
    
    # Calcul du close HA
    close_col = f'{prefix}_close'
    open_col = f'{prefix}_open'
    high_col = f'{prefix}_high' 
    low_col = f'{prefix}_low'
    
    # Pour le premier calcul HA, utiliser les colonnes standards
    if prefix == "HA":
        base_open = 'open'
        base_high = 'high'
        base_low = 'low'
        base_close = 'close'
    else:
        # Pour le double HA, utiliser les colonnes du premier HA
        base_open = 'HA_open'
        base_high = 'HA_high'
        base_low = 'HA_low'
        base_close = 'HA_close'
    
    # HA Close = moyenne des 4 prix
    ha[close_col] = (df[base_open] + df[base_high] + df[base_low] + df[base_close]) / 4
    
    # HA Open - calculé séquentiellement
    ha_open = [(df[base_open].iloc[0] + df[base_close].iloc[0]) / 2]
    for i in range(1, len(df)):
        ha_open.append((ha_open[i - 1] + ha[close_col].iloc[i - 1]) / 2)
    ha[open_col] = ha_open
    
    # HA High = maximum entre HA_open, HA_close et high original
    ha[high_col] = ha[[open_col, close_col, base_high]].max(axis=1)
    
    # HA Low = minimum entre HA_open, HA_close et low original  
    ha[low_col] = ha[[open_col, close_col, base_low]].min(axis=1)
    
    return ha

def compute_double_heikin_ashi(df):
    """
    Calcule Double Heikin Ashi (HA sur HA)
    
    Args:
        df: DataFrame avec les données OHLC originales
        
    Returns:
        DataFrame avec HA1 et HA2
    """
    # Premier calcul HA (HA1)
    ha1_df = compute_heikin_ashi(df, "HA")
    
    if config.LOG_SETTINGS['SHOW_DOUBLE_HA_CALCULATIONS']:
        print(f"HA1 calculé - dernière bougie: O:{ha1_df['HA_open'].iloc[-1]:.6f} C:{ha1_df['HA_close'].iloc[-1]:.6f}")
    
    # Deuxième calcul HA sur les données HA1 (HA2)
    ha2_df = compute_heikin_ashi(ha1_df, "HA2")
    
    if config.LOG_SETTINGS['SHOW_DOUBLE_HA_CALCULATIONS']:
        print(f"HA2 calculé - dernière bougie: O:{ha2_df['HA2_open'].iloc[-1]:.6f} C:{ha2_df['HA2_close'].iloc[-1]:.6f}")
    
    return ha2_df

def get_ha_candle_color(ha_open, ha_close):
    """Détermine la couleur de la bougie Heikin Ashi"""
    if ha_close > ha_open:
        return "green"
    elif ha_close < ha_open:
        return "red"
    else:
        return "doji"

def calculate_multiple_rsi(ha_close_series, periods):
    """Calcule plusieurs RSI avec différentes périodes"""
    rsi_values = {}
    for period in periods:
        rsi_values[f'RSI_{period}'] = calculate_rsi(ha_close_series, period)
    return rsi_values

def get_active_ha_data(ha_df):
    """
    Retourne les données HA actives selon la configuration
    
    Returns:
        tuple: (ha_open, ha_close, ha_high, ha_low, source_name)
    """
    filter_config = config.DOUBLE_HEIKIN_ASHI_FILTER
    
    if filter_config['ENABLED'] and filter_config['USE_FOR_SIGNALS']:
        # Utiliser HA2 pour les signaux
        return (
            ha_df['HA2_open'].iloc[-1],
            ha_df['HA2_close'].iloc[-1], 
            ha_df['HA2_high'].iloc[-1],
            ha_df['HA2_low'].iloc[-1],
            "HA2"
        )
    else:
        # Utiliser HA1 pour les signaux
        return (
            ha_df['HA_open'].iloc[-1],
            ha_df['HA_close'].iloc[-1],
            ha_df['HA_high'].iloc[-1], 
            ha_df['HA_low'].iloc[-1],
            "HA1"
        )

def get_rsi_source_data(ha_df):
    """
    Retourne la série de prix à utiliser pour le calcul RSI
    
    Returns:
        tuple: (price_series, source_name)
    """
    filter_config = config.DOUBLE_HEIKIN_ASHI_FILTER
    
    if filter_config['ENABLED'] and filter_config['USE_FOR_RSI']:
        # Utiliser HA2 pour les RSI
        return ha_df['HA2_close'], "HA2"
    else:
        # Utiliser HA1 pour les RSI
        return ha_df['HA_close'], "HA1"