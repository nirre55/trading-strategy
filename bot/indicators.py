"""
Module pour le calcul des indicateurs techniques
"""
import pandas as pd
import numpy as np

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