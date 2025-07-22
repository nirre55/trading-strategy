# indicators.py
"""
Module contenant tous les indicateurs techniques
"""
import pandas as pd

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

def compute_heikin_ashi(df):
    """Calcule les valeurs Heikin Ashi"""
    ha = df.copy()
    ha['HA_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    ha_open = [(df['open'].iloc[0] + df['close'].iloc[0]) / 2]
    for i in range(1, len(df)):
        ha_open.append((ha_open[i - 1] + ha['HA_close'].iloc[i - 1]) / 2)
    ha['HA_open'] = ha_open
    ha['HA_high'] = ha[['HA_open', 'HA_close', 'high']].max(axis=1)
    ha['HA_low'] = ha[['HA_open', 'HA_close', 'low']].min(axis=1)
    return ha

def compute_trend_indicators(df, ema_period=200, slope_lookback=5):
    """Calcule les indicateurs de tendance (EMA et slope)"""
    df['EMA'] = df['close'].ewm(span=ema_period, adjust=False).mean()
    df['EMA_slope'] = (df['EMA'] - df['EMA'].shift(slope_lookback)) / slope_lookback
    return df

def calculate_mtf_rsi(df_5m, period=14, higher_tf="15min"):
    """Calcule le RSI multi-timeframe"""
    df_mtf = df_5m[['close']].resample(higher_tf).agg({'close': 'last'})
    rsi_mtf = calculate_rsi(df_mtf['close'], period)
    rsi_mtf_expanded = rsi_mtf.reindex(df_5m.index, method='ffill')
    return rsi_mtf_expanded

def add_all_indicators(df, config):
    """Ajoute tous les indicateurs au DataFrame"""
    # Calcul des indicateurs de tendance
    df = compute_trend_indicators(df, config["ema_period"], config["ema_slope_lookback"])
    
    # Calcul Heikin Ashi
    df = compute_heikin_ashi(df)
    
    # Calcul des RSI multiples
    df['RSI_5'] = calculate_rsi(df['HA_close'], config["rsi_periods"][0]).round(2)
    df['RSI_14'] = calculate_rsi(df['HA_close'], config["rsi_periods"][1]).round(2)
    df['RSI_21'] = calculate_rsi(df['HA_close'], config["rsi_periods"][2]).round(2)
    
    # RSI multi-timeframe
    df['RSI_mtf'] = calculate_mtf_rsi(df, config["rsi_mtf_period"], config["rsi_mtf_tf"]).round(2)
    
    return df