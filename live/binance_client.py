# binance_client.py
"""
Client API Binance Futures avec gestion d'erreurs robuste
"""
import logging
import time
from typing import Dict, List, Optional, Tuple
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException, BinanceOrderException
import requests

logger = logging.getLogger(__name__)

class BinanceFuturesClient:
    """Client Binance Futures avec gestion d'erreurs et retry"""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.client = None
        self.last_request_time = 0
        self.request_count = 0
        self.connect()
    
    def connect(self):
        """Établit la connexion à l'API Binance"""
        try:
            self.client = Client(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=self.testnet
            )
            
            # Test de connexion
            account_info = self.client.futures_account()
            logger.info(f"✅ Connexion Binance établie - Solde: {account_info.get('totalWalletBalance', 'N/A')} USDT")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur connexion Binance: {e}")
            return False
    
    def _rate_limit_check(self):
        """Gestion du rate limiting"""
        current_time = time.time()
        if current_time - self.last_request_time < 0.1:  # Max 10 req/sec
            time.sleep(0.1)
        self.last_request_time = current_time
        self.request_count += 1
    
    def _execute_request(self, func, *args, max_retries=3, **kwargs):
        """Exécute une requête avec retry automatique"""
        self._rate_limit_check()
        
        for attempt in range(max_retries):
            try:
                result = func(*args, **kwargs)
                return result, None
                
            except BinanceAPIException as e:
                logger.warning(f"Tentative {attempt + 1}/{max_retries} - Erreur API: {e}")
                if attempt == max_retries - 1:
                    return None, e
                time.sleep(2 ** attempt)  # Backoff exponentiel
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Tentative {attempt + 1}/{max_retries} - Erreur réseau: {e}")
                if attempt == max_retries - 1:
                    return None, e
                time.sleep(2 ** attempt)
                
            except Exception as e:
                logger.error(f"Erreur inattendue: {e}")
                return None, e
        
        return None, "Max retries exceeded"
    
    def get_account_balance(self) -> Tuple[Optional[float], Optional[str]]:
        """Récupère le solde du compte"""
        result, error = self._execute_request(self.client.futures_account)
        if error:
            return None, str(error)
        
        try:
            balance = float(result['totalWalletBalance'])
            return balance, None
        except (KeyError, ValueError) as e:
            return None, f"Erreur parsing balance: {e}"
    
    def get_current_price(self, symbol: str) -> Tuple[Optional[float], Optional[str]]:
        """Récupère le prix actuel d'une paire"""
        result, error = self._execute_request(
            self.client.futures_symbol_ticker,
            symbol=symbol
        )
        if error:
            return None, str(error)
        
        try:
            price = float(result['price'])
            return price, None
        except (KeyError, ValueError) as e:
            return None, f"Erreur parsing price: {e}"
    
    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> Tuple[Optional[List], Optional[str]]:
        """Récupère les données de chandelles"""
        result, error = self._execute_request(
            self.client.futures_klines,
            symbol=symbol,
            interval=interval,
            limit=limit
        )
        if error:
            return None, str(error)
        
        return result, None
    
    def place_market_order(self, symbol: str, side: str, quantity: float) -> Tuple[Optional[Dict], Optional[str]]:
        """Place un ordre au marché"""
        try:
            result, error = self._execute_request(
                self.client.futures_create_order,
                symbol=symbol,
                side=side,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
            
            if error:
                return None, str(error)
            
            logger.info(f"✅ Ordre market placé: {side} {quantity} {symbol}")
            return result, None
            
        except BinanceOrderException as e:
            logger.error(f"❌ Erreur ordre: {e}")
            return None, str(e)
    
    def place_stop_order(self, symbol: str, side: str, quantity: float, stop_price: float) -> Tuple[Optional[Dict], Optional[str]]:
        """Place un ordre stop loss"""
        try:
            result, error = self._execute_request(
                self.client.futures_create_order,
                symbol=symbol,
                side=side,
                type=ORDER_TYPE_STOP_MARKET,
                quantity=quantity,
                stopPrice=stop_price
            )
            
            if error:
                return None, str(error)
            
            logger.info(f"✅ Stop Loss placé: {side} {quantity} {symbol} @ {stop_price}")
            return result, None
            
        except BinanceOrderException as e:
            logger.error(f"❌ Erreur stop loss: {e}")
            return None, str(e)
    
    def place_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> Tuple[Optional[Dict], Optional[str]]:
        """Place un ordre limite (Take Profit)"""
        try:
            result, error = self._execute_request(
                self.client.futures_create_order,
                symbol=symbol,
                side=side,
                type=ORDER_TYPE_LIMIT,
                quantity=quantity,
                price=price,
                timeInForce=TIME_IN_FORCE_GTC
            )
            
            if error:
                return None, str(error)
            
            logger.info(f"✅ Take Profit placé: {side} {quantity} {symbol} @ {price}")
            return result, None
            
        except BinanceOrderException as e:
            logger.error(f"❌ Erreur take profit: {e}")
            return None, str(e)
    
    def cancel_order(self, symbol: str, order_id: int) -> Tuple[Optional[Dict], Optional[str]]:
        """Annule un ordre"""
        result, error = self._execute_request(
            self.client.futures_cancel_order,
            symbol=symbol,
            orderId=order_id
        )
        
        if error:
            return None, str(error)
        
        logger.info(f"✅ Ordre annulé: {order_id}")
        return result, None
    
    def get_open_orders(self, symbol: str) -> Tuple[Optional[List], Optional[str]]:
        """Récupère les ordres ouverts"""
        result, error = self._execute_request(
            self.client.futures_get_open_orders,
            symbol=symbol
        )
        
        if error:
            return None, str(error)
        
        return result, None
    
    def get_position_info(self, symbol: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Récupère les informations de position"""
        result, error = self._execute_request(
            self.client.futures_position_information,
            symbol=symbol
        )
        
        if error:
            return None, str(error)
        
        # Trouve la position pour le symbole
        for position in result:
            if position['symbol'] == symbol:
                return position, None
        
        return None, "Position non trouvée"
    
    def close_position(self, symbol: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Ferme une position ouverte"""
        position, error = self.get_position_info(symbol)
        if error:
            return None, error
        
        position_size = float(position['positionAmt'])
        if position_size == 0:
            return None, "Aucune position ouverte"
        
        # Détermine le côté pour fermer
        side = SIDE_SELL if position_size > 0 else SIDE_BUY
        quantity = abs(position_size)
        
        return self.place_market_order(symbol, side, quantity)
    
    def get_connection_status(self) -> Dict:
        """Vérifie le statut de la connexion"""
        try:
            start_time = time.time()
            self.client.futures_ping()
            latency = (time.time() - start_time) * 1000
            
            return {
                "connected": True,
                "latency_ms": round(latency, 2),
                "requests_count": self.request_count,
                "testnet": self.testnet
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
                "requests_count": self.request_count,
                "testnet": self.testnet
            }

# Fonctions utilitaires
def format_quantity(quantity: float, symbol: str) -> float:
    """Formate la quantité selon les règles du symbole"""
    # Pour BTCUSDT, généralement 3 décimales
    if "BTC" in symbol:
        return round(quantity, 3)
    elif "ETH" in symbol:
        return round(quantity, 2)
    else:
        return round(quantity, 1)

def format_price(price: float, symbol: str) -> float:
    """Formate le prix selon les règles du symbole"""
    # Pour BTCUSDT, généralement 1 décimale
    if "USDT" in symbol:
        return round(price, 1)
    else:
        return round(price, 4)