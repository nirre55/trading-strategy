# binance_client_improved.py
"""
Client API Binance Futures avec gestion d'erreurs robuste et formatage précis
AMÉLIORATIONS : Cache des précisions, validation automatique, formatage correct
"""
import logging
import time
import math
from typing import Dict, List, Optional, Tuple
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException, BinanceOrderException
import requests

logger = logging.getLogger(__name__)

class BinanceFuturesClient:
    """Client Binance Futures avec gestion d'erreurs et formatage précis"""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.client = None
        self.last_request_time = 0
        self.request_count = 0
        
        # 🆕 Cache pour les informations de précision
        self.symbol_info_cache = {}
        self.cache_loaded = False
        
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
            
            # 🆕 Chargement automatique des informations d'échange
            self._load_exchange_info()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur connexion Binance: {e}")
            return False
    
    def _load_exchange_info(self):
        """🆕 Charge les informations d'échange dans le cache"""
        try:
            logger.info("📊 Chargement des informations d'échange...")
            exchange_info = self.client.futures_exchange_info()
            
            for symbol_info in exchange_info['symbols']:
                symbol = symbol_info['symbol']
                filters = symbol_info['filters']
                
                precision_data = {
                    'quantityPrecision': symbol_info['quantityPrecision'],
                    'pricePrecision': symbol_info['pricePrecision'],
                    'baseAssetPrecision': symbol_info['baseAssetPrecision'],
                    'stepSize': None,
                    'tickSize': None,
                    'minQty': None,
                    'maxQty': None,
                    'minPrice': None,
                    'maxPrice': None,
                    'minNotional': None
                }
                
                # Extraction des filtres critiques
                for filter_info in filters:
                    if filter_info['filterType'] == 'LOT_SIZE':
                        precision_data['stepSize'] = float(filter_info['stepSize'])
                        precision_data['minQty'] = float(filter_info['minQty'])
                        precision_data['maxQty'] = float(filter_info['maxQty'])
                    elif filter_info['filterType'] == 'PRICE_FILTER':
                        precision_data['tickSize'] = float(filter_info['tickSize'])
                        precision_data['minPrice'] = float(filter_info['minPrice'])
                        precision_data['maxPrice'] = float(filter_info['maxPrice'])
                    elif filter_info['filterType'] == 'MIN_NOTIONAL':
                        precision_data['minNotional'] = float(filter_info['notional'])
                
                self.symbol_info_cache[symbol] = precision_data
            
            self.cache_loaded = True
            logger.info(f"✅ Informations chargées pour {len(self.symbol_info_cache)} symboles")
            
        except Exception as e:
            logger.error(f"❌ Erreur chargement exchange info: {e}")
            self.cache_loaded = False
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """🆕 Récupère les informations de précision pour un symbole"""
        if not self.cache_loaded:
            self._load_exchange_info()
        return self.symbol_info_cache.get(symbol)
    
    def format_quantity(self, quantity: float, symbol: str) -> float:
        """🔧 AMÉLIORÉ: Formate la quantité selon les règles exactes du symbole"""
        symbol_info = self.get_symbol_info(symbol)
        
        # Fallback si pas d'info
        if not symbol_info or symbol_info['stepSize'] is None:
            if "BTC" in symbol:
                return round(quantity, 3)
            elif "ETH" in symbol:
                return round(quantity, 2)
            else:
                return round(quantity, 1)
        
        step_size = symbol_info['stepSize']
        if step_size == 0:
            return quantity
        
        # Calcul précis du nombre de décimales
        step_str = f"{step_size:.10f}".rstrip('0')
        if '.' in step_str:
            decimals = len(step_str.split('.')[1])
        else:
            decimals = 0
        
        # ⚠️ CRITIQUE: Arrondi vers le bas pour éviter "insufficient balance"
        precision_factor = 10 ** decimals
        formatted_qty = math.floor(quantity * precision_factor) / precision_factor
        
        return round(formatted_qty, decimals)
    
    def format_price(self, price: float, symbol: str) -> float:
        """🔧 AMÉLIORÉ: Formate le prix selon les règles exactes du symbole"""
        symbol_info = self.get_symbol_info(symbol)
        
        # Fallback si pas d'info
        if not symbol_info or symbol_info['tickSize'] is None:
            if "USDT" in symbol or "USDC" in symbol:
                return round(price, 1)
            else:
                return round(price, 4)
        
        tick_size = symbol_info['tickSize']
        if tick_size == 0:
            return price
        
        # Calcul précis du nombre de décimales
        tick_str = f"{tick_size:.10f}".rstrip('0')
        if '.' in tick_str:
            decimals = len(tick_str.split('.')[1])
        else:
            decimals = 0
        
        # Arrondi au tick size le plus proche
        formatted_price = round(price / tick_size) * tick_size
        
        return round(formatted_price, decimals)
    
    def validate_order_params(self, symbol: str, quantity: float, price: Optional[float] = None) -> Tuple[bool, str, Dict]:
        """🆕 NOUVEAU: Valide et formate automatiquement les paramètres d'ordre"""
        symbol_info = self.get_symbol_info(symbol)
        if not symbol_info:
            return False, f"Informations de symbole non disponibles pour {symbol}", {}
        
        # Formatage de la quantité
        formatted_qty = self.format_quantity(quantity, symbol)
        
        # Vérifications quantité
        if symbol_info['minQty'] and formatted_qty < symbol_info['minQty']:
            return False, f"Quantité {formatted_qty} < minimum {symbol_info['minQty']}", {}
        
        if symbol_info['maxQty'] and formatted_qty > symbol_info['maxQty']:
            return False, f"Quantité {formatted_qty} > maximum {symbol_info['maxQty']}", {}
        
        result = {
            'quantity': formatted_qty,
            'symbol_info': symbol_info
        }
        
        # Formatage du prix si fourni
        if price is not None:
            formatted_price = self.format_price(price, symbol)
            
            if symbol_info['minPrice'] and formatted_price < symbol_info['minPrice']:
                return False, f"Prix {formatted_price} < minimum {symbol_info['minPrice']}", {}
            
            if symbol_info['maxPrice'] and formatted_price > symbol_info['maxPrice']:
                return False, f"Prix {formatted_price} > maximum {symbol_info['maxPrice']}", {}
            
            result['price'] = formatted_price
        
        # Vérification notional minimum
        if price is not None and symbol_info['minNotional']:
            notional = formatted_qty * price
            if notional < symbol_info['minNotional']:
                return False, f"Notional {notional:.2f} < minimum {symbol_info['minNotional']}", {}
        
        return True, "Paramètres valides", result
    
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
    
    def get_account_balance(self, asset: str = "USDT") -> Tuple[Optional[float], Optional[str]]:
        """Récupère le solde du compte pour un asset spécifique"""
        result, error = self._execute_request(self.client.futures_account)
        if error:
            return None, str(error)
        
        try:
            for balance in result.get('assets', []):
                if balance['asset'] == asset:
                    wallet_balance = float(balance['walletBalance'])
                    return wallet_balance, None
            
            return 0.0, f"Asset {asset} non trouvé"
            
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
        """🔧 AMÉLIORÉ: Place un ordre au marché avec validation automatique"""
        try:
            # 🆕 Validation automatique des paramètres
            valid, message, params = self.validate_order_params(symbol, quantity)
            if not valid:
                return None, f"Validation échouée: {message}"
            
            formatted_qty = params['quantity']
            
            result, error = self._execute_request(
                self.client.futures_create_order,
                symbol=symbol,
                side=side,
                type=FUTURE_ORDER_TYPE_MARKET,
                quantity=formatted_qty
            )
            
            if error:
                return None, str(error)
            
            logger.info(f"✅ Ordre market placé: {side} {formatted_qty} {symbol}")
            return result, None
            
        except BinanceOrderException as e:
            logger.error(f"❌ Erreur ordre: {e}")
            return None, str(e)
    
    def place_stop_order(self, symbol: str, side: str, quantity: float, stop_price: float) -> Tuple[Optional[Dict], Optional[str]]:
        """🔧 AMÉLIORÉ: Place un ordre stop loss avec validation"""
        try:
            # 🆕 Validation automatique
            valid, message, params = self.validate_order_params(symbol, quantity, stop_price)
            if not valid:
                return None, f"Validation échouée: {message}"
            
            formatted_qty = params['quantity']
            formatted_price = params['price']
            
            result, error = self._execute_request(
                self.client.futures_create_order,
                symbol=symbol,
                side=side,
                type=FUTURE_ORDER_TYPE_STOP_MARKET,
                quantity=formatted_qty,
                stopPrice=formatted_price
            )
            
            if error:
                return None, str(error)
            
            logger.info(f"✅ Stop Loss placé: {side} {formatted_qty} {symbol} @ {formatted_price}")
            return result, None
            
        except BinanceOrderException as e:
            logger.error(f"❌ Erreur stop loss: {e}")
            return None, str(e)
    
    def place_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> Tuple[Optional[Dict], Optional[str]]:
        """🔧 AMÉLIORÉ: Place un ordre limite avec validation"""
        try:
            # 🆕 Validation automatique
            valid, message, params = self.validate_order_params(symbol, quantity, price)
            if not valid:
                return None, f"Validation échouée: {message}"
            
            formatted_qty = params['quantity']
            formatted_price = params['price']
            
            result, error = self._execute_request(
                self.client.futures_create_order,
                symbol=symbol,
                side=side,
                type=FUTURE_ORDER_TYPE_LIMIT,
                quantity=formatted_qty,
                price=formatted_price,
                timeInForce=TIME_IN_FORCE_GTC
            )
            
            if error:
                return None, str(error)
            
            logger.info(f"✅ Take Profit placé: {side} {formatted_qty} {symbol} @ {formatted_price}")
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
                "testnet": self.testnet,
                "cache_loaded": self.cache_loaded,
                "symbols_cached": len(self.symbol_info_cache)
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
                "requests_count": self.request_count,
                "testnet": self.testnet,
                "cache_loaded": self.cache_loaded
            }