import pandas as pd
import ta
import ta.volatility

def calculate_atr_simple(data_frame=None, period=14):
    """
    Calcule l'ATR avec la bibliothèque ta (SUPER SIMPLE!)
    
    Args:
        symbol (str): Symbole de trading
        period (int): Période ATR (défaut: 14)
        interval (str): Intervalle de temps
        limit (int): Nombre de bougies
    
    Returns:
        dict: Résultats ATR
    """
    if data_frame is None or len(data_frame) < period:
        return None
    
    # Calcul ATR avec la bibliothèque ta (1 LIGNE!)
    data_frame['atr'] = ta.volatility.AverageTrueRange(
        high=data_frame['high'],
        low=data_frame['low'],
        close=data_frame['close'],
        window=period
    ).average_true_range()
    
    # Résultats
    current_price = data_frame['close'].iloc[-1]
    current_atr = data_frame['atr'].iloc[-1]
    atr_percent = (current_atr / current_price) * 100

    return current_price, current_atr, atr_percent