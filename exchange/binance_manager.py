from binance.client import Client
import binance.enums as enumsBinance
from binance.exceptions import BinanceAPIException
from utils import load_api_credentials_from_env
from decimal import Decimal
import pandas as pd
import json
from binance.enums import (
    SIDE_BUY, SIDE_SELL,
    FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET, FUTURE_ORDER_TYPE_STOP_MARKET,
    TIME_IN_FORCE_GTC, FUTURE_ORDER_TYPE_TAKE_PROFIT,FUTURE_ORDER_TYPE_STOP
)

class BinanceHedgeTrader:
    def __init__(self, testnet=True, symbol="BTCUSDT", leverage=1, margin_type="CROSSED", hedge_mode=True):
        self.client = self.connect_to_binance_futures(testnet)
        self.set_leverage(symbol, leverage)
        self.set_margin_type(symbol, margin_type)
        self.activate_hedge_mode(hedge_mode)

    def connect_to_binance_futures(self, use_testnet):
        """
        Se connecte à Binance Futures avec les clés API du fichier .env
        
        Args:
            use_testnet (bool): Si True, utilise le testnet de Binance
            
        Returns:
            Client: Client Binance Futures connecté
        """
        # Récupération des clés API
        if use_testnet:
            api_key = load_api_credentials_from_env("API_KEY_TESTNET")
            secret_key = load_api_credentials_from_env("SECRET_KEY_TESTNET")
        else:
            api_key = load_api_credentials_from_env("API_KEY")
            secret_key = load_api_credentials_from_env("SECRET_KEY")
        
        # Création du client
        client = Client(api_key, secret_key, testnet=use_testnet)
        
        # Test de la connexion
        try:
            account_info = client.futures_account()
            print(f"✅ Connexion réussie à Binance Futures {'Testnet' if use_testnet else 'Production'}")
            print(f"💰 Solde USDT: {account_info['totalWalletBalance']}")
            return client
        except Exception as e:
            raise ConnectionError(f"Erreur de connexion à Binance Futures: {str(e)}")
        
    def set_leverage(self, symbol, leverage):
        """
        Définit le levier pour un symbole spécifique
        
        Args:
            symbol (str): Symbole de trading (ex: 'BTCUSDT')
            leverage (int): Niveau de levier (1-125 selon le symbole)
        """
        try:
            
            print(f"Configuration du levier {leverage}x pour {symbol}...")
            
            # Définition du levier
            result = self.client.futures_change_leverage(
                symbol=symbol,
                leverage=leverage
            )
            
            print(f"✅ Levier configuré avec succès:")
            print(f"   Symbole: {result['symbol']}")
            print(f"   Levier: {result['leverage']}x")
            print(f"   Marge maximale: {result['maxNotionalValue']}")
            
            return result
        
        except BinanceAPIException as e:
            print(f"❌ Erreur API Binance: {e}")
            if e.code == -4028:
                print(" Le levier spécifié n'est pas autorisé pour ce symbole")
            elif e.code == -4131:
                print(" Réduisez vos positions avant de changer le levier")
        except Exception as e:
            print(f"❌ Erreur générale: {e}")
            
        return None
    
    def set_margin_type(self, symbol, margin_type):
        """
        Définit le type de marge (ISOLATED ou CROSSED)
        
        Args:
            symbol (str): Symbole de trading
            margin_type (str): 'ISOLATED' ou 'CROSSED'
        """
        try:
            
            print(f"Configuration du type de marge {margin_type} pour {symbol}...")
            
            result = self.client.futures_change_margin_type(
                symbol=symbol,
                marginType=margin_type
            )
            
            print(f"✅ Type de marge configuré: {margin_type}")
            return result
     
        except BinanceAPIException as e:
            print(f"❌ Erreur API Binance: {e}")
            if e.code == -4046:
                print("   Le type de marge est déjà configuré sur cette valeur")
        except Exception as e:
            print(f"❌ Erreur générale: {e}")
            
        return None

    def activate_hedge_mode(self, hedge_mode=True):
        """
        Active le mode hedge sur Binance Futures
        "true": Hedge Mode; "false": One-way Mode
        """
        try:
            
            # Vérification du statut actuel du mode hedge
            print("Vérification du statut actuel du mode hedge...")
            position_mode = self.client.futures_get_position_mode()
            print(f"Mode de position actuel: {self.get_mode_position_name(position_mode['dualSidePosition'])}")
            
            # Si le mode hedge n'est pas déjà activé
            if not position_mode['dualSidePosition']:
                print("Activation du mode hedge...")
                
                # Activation du mode hedge
                result = self.client.futures_change_position_mode(dualSidePosition=hedge_mode)
                print(f"Résultat de l'activation: {result['msg']}")
                
                # Vérification après activation
                new_position_mode = self.client.futures_get_position_mode()
                
                if new_position_mode['dualSidePosition']:
                    print("✅ Mode hedge activé avec succès!")
                else:
                    print("❌ Échec de l'activation du mode hedge")
            else:
                print("✅ Le mode hedge est déjà activé")
                
        except BinanceAPIException as e:
            print(f"❌ Erreur API Binance: {e}")
            if e.code == -4059:
                print("Note: Assurez-vous que vous n'avez pas de positions ouvertes avant d'activer le mode hedge")
        except Exception as e:
            print(f"❌ Erreur générale: {e}")

    def get_mode_position_name(self, mode_position):
        """
        Récupère le nom du mode de position
        """
        if mode_position:
            return "Hedge Mode"
        else:
            return "One-way Mode"

    def get_symbol_info(self, symbol):
        """
        Récupère les informations de précision pour un symbole
        
        Args:
            symbol (str): Symbole de trading (ex: 'BTCUSDT')
        
        Returns:
            dict: Informations de précision du symbole
        """
        try:
            exchange_info = self.client.futures_exchange_info()

            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    # Extraction des informations de précision
                    price_precision = int(s['pricePrecision'])
                    quantity_precision = int(s['quantityPrecision'])
                    
                    # Filtres pour les tailles min/max
                    filters = {f['filterType']: f for f in s['filters']}
                    
                    lot_size = filters.get('LOT_SIZE', {})
                    price_filter = filters.get('PRICE_FILTER', {})
                    return {
                        'symbol': symbol,
                        'price_precision': price_precision,
                        'quantity_precision': quantity_precision,
                        'min_qty': float(lot_size.get('minQty', 0)),
                        'max_qty': float(lot_size.get('maxQty', 0)),
                        'step_size': float(lot_size.get('stepSize', 0)),
                        'min_price': float(price_filter.get('minPrice', 0)),
                        'max_price': float(price_filter.get('maxPrice', 0)),
                        'tick_size': float(price_filter.get('tickSize', 0))
                    }
            
            print(f"❌ Symbole {symbol} non trouvé")
            return None
            
        except Exception as e:
            print(f"❌ Erreur lors de la récupération des infos du symbole: {e}")
            return None

    def format_quantity(self, quantity, symbol_info):
        """
        Formate la quantité selon la précision du symbole
        
        Args:
            quantity (float): Quantité à formater
            symbol_info (dict): Informations du symbole
        
        Returns:
            str: Quantité formatée
        """
        if symbol_info is None:
            return str(quantity)
        
        precision = symbol_info['quantity_precision']
        step_size = symbol_info['step_size']
        
        # Arrondir à la baisse selon le step_size
        if step_size > 0:
            quantity = float(Decimal(str(quantity)) // Decimal(str(step_size))) * step_size
        
        return f"{quantity:.{precision}f}"

    def format_price(self, price, symbol_info):
        """
        Formate le prix selon la précision du symbole
        
        Args:
            price (float): Prix à formater
            symbol_info (dict): Informations du symbole
        
        Returns:
            str: Prix formaté
        """
        if symbol_info is None:
            return str(price)
        
        precision = symbol_info['price_precision']
        tick_size = symbol_info['tick_size']
        
        # Arrondir selon le tick_size
        if tick_size > 0:
            price = float(Decimal(str(price)) // Decimal(str(tick_size))) * tick_size
        
        return f"{price:.{precision}f}"

    def get_current_price(self, symbol):
        """
        Récupère le prix actuel d'un symbole (simple)
        
        Args:
            symbol (str): Symbole de trading (ex: 'BTCUSDT')
        
        Returns:
            float: Prix actuel ou None si erreur
        """
        try:
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except Exception as e:
            print(f"❌ Erreur lors de la récupération du prix de {symbol}: {e}")
            return None
        
    def get_binance_data(self, symbol, interval, limit=100):
        """
        Récupère les données OHLCV depuis Binance et retourne un DataFrame
        
        Args:
            symbol (str): Symbole (ex: 'BTCUSDT')
            interval (str): Intervalle ('1m', '5m', '1h', '4h', '1d', etc.)
            limit (int): Nombre de bougies
        
        Returns:
            pd.DataFrame: DataFrame avec colonnes OHLCV
        """
        try:
            
            # Récupération des klines
            klines = self.client.futures_klines(symbol=symbol, interval=interval, limit=limit)

            # Conversion en DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Nettoyage et conversion des types
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            df['volume'] = df['volume'].astype(float)
            
            # Garde seulement les colonnes nécessaires
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            return df
            
        except Exception as e:
            print(f"❌ Erreur récupération données: {e}")
            return None

    def get_simple_order_status(self, symbol, order_id):
        """
        Retourne le statut simple d'un ordre
        
        Args:
            symbol (str): Symbole de trading
            order_id (int): ID de l'ordre
        
        Returns:
            str: 'NEW', 'FILLED', 'CANCELED', 'PARTIALLY_FILLED', 'EXPIRED'
            None: Si erreur
        """
        try:
            order_info = self.client.futures_get_order(symbol=symbol, orderId=order_id)
            return order_info['status']
            
        except BinanceAPIException as e:
            if e.code == -2013:
                print(f"❌ Ordre {order_id} n'existe pas")
            else:
                print(f"❌ Erreur API: {e}")
            return None
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return None

    def cancel_order(self, symbol, order_id):
        """
        Annule un ordre
        
        Args:
            symbol (str): Symbole de trading
            order_id (int): ID de l'ordre à annuler
        
        Returns:
            dict: Résultat de l'annulation ou None si erreur
        """
        try:
            result = self.client.futures_cancel_order(
                symbol=symbol,
                orderId=order_id
            )
            
            print(f"✅ Ordre {order_id} annulé avec succès!")
            return result
            
        except BinanceAPIException as e:
            print(f"❌ Erreur API Binance: {e}")
            return None
        except Exception as e:
            print(f"❌ Erreur générale: {e}")
            return None
    
    def place_market_order(self, symbol, side, quantity, position_side=None, reduce_only=False):
        """
        Place un ordre au marché
        
        Args:
            symbol (str): Symbole de trading (ex: 'BTCUSDT')
            side (str): 'BUY' ou 'SELL'
            quantity (float): Quantité à trader
            position_side (str): 'LONG', 'SHORT' (pour mode hedge) ou None 
            reduce_only (bool): True pour fermer seulement (réduire position)
        
        Returns:
            dict: Résultat de l'ordre ou None si erreur
        """
        try:            
            # Récupération des infos du symbole
            symbol_info = self.get_symbol_info(symbol)
            if symbol_info is None:
                return None
            
            # Formatage de la quantité
            formatted_quantity = self.format_quantity(quantity, symbol_info)
            
            print(f"📈 Placement d'un ordre MARKET:")
            print(f"   Symbole: {symbol}")
            print(f"   Côté: {side}")
            print(f"   Quantité: {formatted_quantity}")
            print(f"   Position: {position_side if position_side else 'Auto'}")
            print(f"   Réduction seulement: {reduce_only}")
            
            # Paramètres de l'ordre
            order_params = {
                'symbol': symbol,
                'side': side,
                'type': enumsBinance.FUTURE_ORDER_TYPE_MARKET,
                'quantity': formatted_quantity,
            }
            
            # Ajout des paramètres optionnels
            if position_side:
                order_params['positionSide'] = position_side
            if reduce_only:
                order_params['reduceOnly'] = reduce_only
            
            # Placement de l'ordre
            result = self.client.futures_create_order(**order_params)
            
            print(f"✅ Ordre MARKET placé avec succès!")
            print(f"   ID Ordre: {result['orderId']}")
            print(f"   Statut: {result['status']}")
            print(f"   Prix moyen: {result.get('avgPrice', 'N/A')}")
            
            return result
            
        except BinanceAPIException as e:
            print(f"❌ Erreur API Binance: {e}")
            return None
        except Exception as e:
            print(f"❌ Erreur générale: {e}")
            return None

    def place_limit_order(self, symbol, side, quantity, price, position_side=None, reduce_only=False, 
                      time_in_force='GTC'):
        """
        Place un ordre à cours limité
        
        Args:
            symbol (str): Symbole de trading
            side (str): 'BUY' ou 'SELL'
            quantity (float): Quantité à trader
            price (float): Prix limite
            position_side (str): 'LONG', 'SHORT' ou None
            reduce_only (bool): True pour fermer seulement
            time_in_force (str): 'GTC' (Good Till Cancel), 'IOC' (Immediate Or Cancel), 'FOK' (Fill Or Kill)
        
        Returns:
            dict: Résultat de l'ordre ou None si erreur
        """
        try:
            
            # Récupération des infos du symbole
            symbol_info = self.get_symbol_info(symbol)
            if symbol_info is None:
                return None
            
            # Formatage de la quantité et du prix
            formatted_quantity = self.format_quantity(quantity, symbol_info)
            formatted_price = self.format_price(price, symbol_info)

            print(f"📊 Placement d'un ordre LIMIT:")
            print(f"   Symbole: {symbol}")
            print(f"   Côté: {side}")
            print(f"   Quantité: {formatted_quantity}")
            print(f"   Prix: {formatted_price}")
            print(f"   Position: {position_side if position_side else 'Auto'}")
            print(f"   Réduction seulement: {reduce_only}")
            print(f"   Time in Force: {time_in_force}")
            
            # Paramètres de l'ordre
            order_params = {
                'symbol': symbol,
                'side': side,
                'type': enumsBinance.FUTURE_ORDER_TYPE_LIMIT,
                'quantity': formatted_quantity,
                'price': formatted_price,
                'timeInForce': time_in_force,
            }
            
            # Ajout des paramètres optionnels
            if position_side:
                order_params['positionSide'] = position_side
            if reduce_only:
                order_params['reduceOnly'] = reduce_only
            
            # Placement de l'ordre
            result = self.client.futures_create_order(**order_params)

            print(f"✅ Ordre LIMIT placé avec succès!")
            print(f"   ID Ordre: {result['orderId']}")
            print(f"   Statut: {result['status']}")
            
            return result
            
        except BinanceAPIException as e:
            print(f"❌ Erreur API Binance: {e}")
            return None
        except Exception as e:
            print(f"❌ Erreur générale: {e}")
            return None

    def place_stop_limit_order(self, symbol, side, quantity, price, stop_price, position_side=None, 
                            reduce_only=False, time_in_force='GTC'):
        """
        Place un ordre stop-limit
        
        Args:
            symbol (str): Symbole de trading
            side (str): 'BUY' ou 'SELL'
            quantity (float): Quantité à trader
            price (float): Prix limite (prix d'exécution)
            stop_price (float): Prix de déclenchement du stop
            position_side (str): 'LONG', 'SHORT' ou None
            reduce_only (bool): True pour fermer seulement
            time_in_force (str): 'GTC', 'IOC', 'FOK'
        
        Returns:
            dict: Résultat de l'ordre ou None si erreur
        """
        try:            
            # Récupération des infos du symbole
            symbol_info = self.get_symbol_info(symbol)
            if symbol_info is None:
                return None
            
            # Formatage des valeurs
            formatted_quantity = self.format_quantity(quantity, symbol_info)
            formatted_price = self.format_price(price, symbol_info)
            formatted_stop_price = self.format_price(stop_price, symbol_info)

            print(f"🛑 Placement d'un ordre STOP_LIMIT:")
            print(f"   Symbole: {symbol}")
            print(f"   Côté: {side}")
            print(f"   Quantité: {formatted_quantity}")
            print(f"   Prix limite: {formatted_price}")
            print(f"   Prix stop: {formatted_stop_price}")
            print(f"   Position: {position_side if position_side else 'Auto'}")
            print(f"   Réduction seulement: {reduce_only}")
            print(f"   Time in Force: {time_in_force}")
            
            # Paramètres de l'ordre
            order_params = {
                'symbol': symbol,
                'side': side,
                'type': enumsBinance.FUTURE_ORDER_TYPE_STOP,
                'quantity': formatted_quantity,
                'price': formatted_price,
                'stopPrice': formatted_stop_price,
                'timeInForce': time_in_force
            }
            
            # Ajout des paramètres optionnels
            if position_side:
                order_params['positionSide'] = position_side
            if reduce_only:
                order_params['reduceOnly'] = reduce_only
            
            # Placement de l'ordre
            result = self.client.futures_create_order(**order_params)

            print(f"✅ Ordre STOP_LIMIT placé avec succès!")
            print(f"   ID Ordre: {result['orderId']}")
            print(f"   Statut: {result['status']}")
            
            return result
            
        except BinanceAPIException as e:
            print(f"❌ Erreur API Binance: {e}")
            return None
        except Exception as e:
            print(f"❌ Erreur générale: {e}")
            return None
        
    def place_stop_market_order(self, symbol, side, quantity, stop_price, position_side=None,
                            reduce_only=False, working_type='MARK_PRICE', price_protect=True):
        """
        Place un ordre STOP-MARKET (ordre au marché déclenché par un seuil)

        Args:
            symbol (str): Symbole de trading (ex: 'BTCUSDT')
            side (str): 'BUY' ou 'SELL' (direction de l'ordre)
            quantity (float): Quantité à trader
            stop_price (float): Seuil de déclenchement du stop
            position_side (str): 'LONG' ou 'SHORT' (obligatoire si mode hedge)
            reduce_only (bool): True pour clôturer uniquement
            working_type (str): 'MARK_PRICE' ou 'CONTRACT_PRICE' (défaut: 'MARK_PRICE')
            price_protect (bool): True pour activer la protection contre la manipulation de prix

        Returns:
            dict ou None: Détails de l'ordre ou None si erreur
        """
        try:
            # Infos du symbole
            symbol_info = self.get_symbol_info(symbol)
            if symbol_info is None:
                return None

            # Formatage
            formatted_quantity = self.format_quantity(quantity, symbol_info)
            formatted_stop_price = self.format_price(stop_price, symbol_info)

            print(f"🛑 Placement d'un ordre STOP_MARKET:")
            print(f"   Symbole: {symbol}")
            print(f"   Côté: {side}")
            print(f"   Quantité: {formatted_quantity}")
            print(f"   Stop: {formatted_stop_price}")
            print(f"   Position: {position_side if position_side else 'Auto'}")
            print(f"   Réduction seulement: {reduce_only}")

            order_params = {
                'symbol': symbol,
                'side': side,
                'type': enumsBinance.FUTURE_ORDER_TYPE_STOP_MARKET,
                'stopPrice': formatted_stop_price,
                'quantity': formatted_quantity,
                'workingType': working_type,
                'priceProtect': price_protect
            }

            if position_side:
                order_params['positionSide'] = position_side
            if reduce_only:
                order_params['reduceOnly'] = reduce_only

            result = self.client.futures_create_order(**order_params)

            print(f"✅ Ordre STOP_MARKET placé avec succès!")
            print(f"   ID Ordre: {result['orderId']}")
            print(f"   Statut: {result['status']}")
            return result

        except BinanceAPIException as e:
            print(f"❌ Erreur API Binance: {e}")
            return None
        except Exception as e:
            print(f"❌ Erreur générale: {e}")
            return None
 
    def create_take_profit_limit(self, symbol, side, tp_price, stop_price, quantity):
        """Crée un ordre TAKE_PROFIT_LIMIT optimisé"""
        try:
            # Déterminer positionSide selon le side
            position_side = 'LONG' if side == 'BUY' else 'SHORT'
            tp_side = 'SELL' if side == 'BUY' else 'BUY'

            # Récupération des infos du symbole
            symbol_info = self.get_symbol_info(symbol)
            if symbol_info is None:
                return None
            
            # Formatage des valeurs
            formatted_quantity = self.format_quantity(quantity, symbol_info)
            formatted_price = self.format_price(tp_price, symbol_info)
            formatted_stop_price = self.format_price(stop_price, symbol_info)

            order = self.client.futures_create_order(
                symbol=symbol,
                side=tp_side,
                positionSide=position_side,
                type='TAKE_PROFIT',  # ✅ Type correct (pas TAKE_PROFIT_LIMIT)
                quantity=formatted_quantity,
                price=formatted_price,           # Prix limite pour frais maker
                stopPrice=formatted_stop_price,
                timeInForce='GTX',        # Post Only - garantit frais maker
                workingType='MARK_PRICE',
                priceProtect=True
            )

            print(f"✅ Take Profit LIMIT créé - ID: {order['orderId']}")
            print(f"   Stop: {stop_price}, Limit: {tp_price}")
            return order
            
        except Exception as e:
            print(f"❌ Erreur TAKE_PROFIT_LIMIT: {e}")
            return None
        


    def place_batch_stop_market_orders_from_json(self, symbol, json_file_path):
        """
        Lit un fichier JSON contenant plusieurs ordres et place des ordres STOP_MARKET pour chacun.

        Args:
            symbol (str): Le symbole de trading (ex: BTCUSDT)
            json_file_path (str): Chemin du fichier JSON
        """
        try:
            with open(json_file_path, 'r') as f:
                data = json.load(f)

            orders = data.get("orders", [])
            if not orders:
                print("❌ Aucun ordre trouvé dans le fichier JSON.")
                return

            for order in orders:
                order_id = order.get("id")
                price = order.get("price")
                quantity = order.get("quantity")
                side = order.get("side", "").upper()

                if side not in ["LONG", "SHORT"]:
                    print(f"❌ Ordre {order_id} ignoré : side invalide '{side}'")
                    continue

                # Déterminer les paramètres selon la position
                if side == "LONG":
                    position_side = "LONG"
                    direction = "BUY"
                else:
                    position_side = "SHORT"
                    direction = "SELL"

                print(f"\n📦 Traitement de l'ordre #{order_id} ({side})")

                self.place_stop_market_order(
                    symbol=symbol,
                    side=direction,
                    quantity=quantity,
                    stop_price=price,
                    position_side=position_side,
                    reduce_only=False
                )

        except FileNotFoundError:
            print(f"❌ Fichier non trouvé : {json_file_path}")
        except json.JSONDecodeError as e:
            print(f"❌ Erreur de lecture JSON : {e}")
        except Exception as e:
            print(f"❌ Erreur inattendue : {e}")

   #24.46
   #24.55
