# filters.py
"""
Module contenant les différents filtres de trading
"""

class TradingFilters:
    """
    Classe contenant tous les filtres de trading
    """
    
    @staticmethod
    def heikin_ashi_filter(row, direction):
        """
        Filtre basé sur la direction des bougies Heikin Ashi
        """
        if direction == 'long':
            return row['HA_close'] > row['HA_open']
        elif direction == 'short':
            return row['HA_close'] < row['HA_open']
        return False
    
    @staticmethod
    def trend_filter(row, direction):
        """
        Filtre de tendance basé sur EMA et sa pente
        """
        if direction == 'long':
            return row['close'] > row['EMA'] and row['EMA_slope'] > 0
        elif direction == 'short':
            return row['close'] < row['EMA'] and row['EMA_slope'] < 0
        return False
    
    @staticmethod
    def multi_timeframe_rsi_filter(row, direction):
        """
        Filtre RSI multi-timeframe
        """
        if direction == 'long':
            return row['RSI_mtf'] > 50
        elif direction == 'short':
            return row['RSI_mtf'] < 50
        return False
    
    @staticmethod
    def volume_filter(row, direction, volume_threshold=1.5):
        """
        Filtre de volume (optionnel, nécessite une colonne 'volume')
        """
        if 'volume' not in row.index:
            return True  # Pas de filtre si pas de données volume
        
        # Volume actuel vs moyenne mobile du volume
        if 'volume_ma' in row.index:
            return row['volume'] > row['volume_ma'] * volume_threshold
        return True
    
    @staticmethod
    def volatility_filter(row, direction, volatility_threshold=0.02):
        """
        Filtre de volatilité basé sur l'ATR ou range
        """
        if 'atr' in row.index:
            return row['atr'] > volatility_threshold
        elif all(col in row.index for col in ['high', 'low']):
            # Utiliser le range de la bougie comme proxy de volatilité
            candle_range = (row['high'] - row['low']) / row['close']
            return candle_range > volatility_threshold
        return True
    
    @classmethod
    def apply_all_filters(cls, row, direction, filters_config):
        """
        Applique tous les filtres activés selon la configuration
        
        Args:
            row: Ligne du DataFrame
            direction: 'long' ou 'short'
            filters_config: Dict avec les filtres activés
        
        Returns:
            bool: True si tous les filtres passent
        """
        filters_map = {
            "filter_ha": cls.heikin_ashi_filter,
            "filter_trend": cls.trend_filter,
            "filter_mtf_rsi": cls.multi_timeframe_rsi_filter,
            "filter_volume": cls.volume_filter,
            "filter_volatility": cls.volatility_filter
        }
        
        for filter_name, filter_func in filters_map.items():
            if filters_config.get(filter_name, False):
                if not filter_func(row, direction):
                    return False
        
        return True