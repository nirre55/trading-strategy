"""
Client pour interagir avec l'API Binance Futures
"""
import requests
import pandas as pd
from datetime import datetime
import config
from trading_logger import trading_logger
from retry_manager import RetryManager

class BinanceClient:
    def __init__(self):
        self.base_url = "https://fapi.binance.com"
        
    def get_historical_klines(self, symbol, interval, limit=500):
        """Récupère les données historiques de bougies"""
        endpoint = f"{self.base_url}/fapi/v1/klines"
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit + 1  # +1 pour avoir la bougie en cours
        }
        
        try:
            @RetryManager.with_configured_retry('PRICE')
            def _get():
                return requests.get(endpoint, params=params)

            response = _get()
            response.raise_for_status()
            data = response.json()
            
            # Convertir en DataFrame
            df = pd.DataFrame(data, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Convertir les colonnes nécessaires en float
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            # Convertir les timestamps
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
            
            # Supprimer la dernière bougie (en cours) pour éviter les doublons
            # et garantir que nous avons seulement des bougies fermées
            df = df[:-1].copy()
            
            return df
            
        except requests.exceptions.RequestException as e:
            print(f"Erreur lors de la récupération des données historiques: {e}")
            trading_logger.error_occurred(
                "HISTORICAL_DATA",
                f"Requête échouée: {type(e).__name__} - {e}",
                context=f"endpoint={endpoint} symbol={symbol} interval={interval} limit={limit}"
            )
            return None
        except Exception as e:
            print(f"Erreur lors du traitement des données: {e}")
            trading_logger.error_occurred(
                "HISTORICAL_DATA_PROCESSING",
                str(e),
                context=f"symbol={symbol} interval={interval} limit={limit}"
            )
            return None
    
    def format_kline_data(self, kline_data):
        """Formate les données de bougie reçues via WebSocket"""
        return {
            'open_time': pd.to_datetime(kline_data['t'], unit='ms'),
            'close_time': pd.to_datetime(kline_data['T'], unit='ms'),
            'open': float(kline_data['o']),
            'high': float(kline_data['h']),
            'low': float(kline_data['l']),
            'close': float(kline_data['c']),
            'volume': float(kline_data['v']),
            'is_closed': kline_data['x']  # True si la bougie est fermée
        }