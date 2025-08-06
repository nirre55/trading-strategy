"""
Module de gestion des positions et calculs de trading
"""
import os
from binance.client import Client
from binance.exceptions import BinanceAPIException
import pandas as pd
import config

def load_api_credentials_from_env(key_name, filename=".env"):
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"Fichier .env non trouvé à l'emplacement : {env_path}")
    
    with open(env_path, "r") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if f"{key_name}=" in line:
                return line.split("=", 1)[1].strip()
    
    raise ValueError(f"Clé '{key_name}' manquante dans le fichier .env")

class PositionManager:
    def __init__(self):
        """Initialise le gestionnaire de positions"""
        try:
            # Chargement des clés API depuis .env
            api_key = load_api_credentials_from_env("BINANCE_API_KEY")
            api_secret = load_api_credentials_from_env("BINANCE_API_SECRET")
            
            # Client Binance Futures
            self.client = Client(api_key, api_secret)
            self.client.API_URL = 'https://fapi.binance.com'  # Futures API
            
            # Cache pour les infos symbole
            self.symbol_info_cache = {}
            self._load_symbol_info()
            
            print(f"✅ PositionManager initialisé pour {config.ASSET_CONFIG['SYMBOL']}")
            
        except Exception as e:
            print(f"❌ Erreur initialisation PositionManager: {e}")
            raise
    
    def _load_symbol_info(self):
        """Charge les informations du symbole (précision, limites)"""
        try:
            exchange_info = self.client.futures_exchange_info()
            symbol = config.ASSET_CONFIG['SYMBOL']
            
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    # Extraire précisions
                    price_precision = int(s['pricePrecision'])
                    quantity_precision = int(s['quantityPrecision'])
                    
                    # Extraire limites depuis les filtres
                    min_qty = 0.001  # Valeur par défaut
                    min_notional = 5.0  # Valeur par défaut
                    tick_size = 0.01  # Valeur par défaut
                    
                    for f in s['filters']:
                        if f['filterType'] == 'LOT_SIZE':
                            min_qty = float(f['minQty'])
                        elif f['filterType'] == 'MIN_NOTIONAL':
                            min_notional = float(f['notional'])
                        elif f['filterType'] == 'PRICE_FILTER':
                            tick_size = float(f['tickSize'])
                    
                    self.symbol_info_cache = {
                        'symbol': symbol,
                        'price_precision': price_precision,
                        'quantity_precision': quantity_precision,
                        'min_quantity': min_qty,
                        'min_notional': min_notional,
                        'tick_size': tick_size,
                        'status': s['status']
                    }
                    
                    print(f"📊 Info symbole {symbol}:")
                    print(f"   Prix: {price_precision} décimales | Quantité: {quantity_precision} décimales")
                    print(f"   Min Qty: {min_qty} | Min Notional: {min_notional}")
                    return
            
            raise ValueError(f"Symbole {symbol} non trouvé")
            
        except BinanceAPIException as e:
            print(f"❌ Erreur API lors du chargement info symbole: {e}")
            raise
        except Exception as e:
            print(f"❌ Erreur lors du chargement info symbole: {e}")
            raise
    
    def get_account_balance(self, asset="USDT"):
        """Récupère la balance du compte pour l'asset spécifié"""
        try:
            # Récupérer toutes les balances du compte Futures
            account = self.client.futures_account()
            
            for balance in account['assets']:
                if balance['asset'] == asset:
                    available_balance = float(balance['availableBalance'])
                    print(f"💰 Balance {asset}: {available_balance}")
                    return available_balance
            
            print(f"⚠️ Asset {asset} non trouvé dans le compte")
            return 0.0
            
        except BinanceAPIException as e:
            print(f"❌ Erreur API lors récupération balance: {e}")
            return 0.0
        except Exception as e:
            print(f"❌ Erreur lors récupération balance: {e}")
            return 0.0
    
    def get_symbol_info(self):
        """Retourne les informations du symbole"""
        return self.symbol_info_cache.copy()
    
    def format_price(self, price):
        """Formate le prix selon la précision du symbole"""
        if not self.symbol_info_cache:
            return price
        
        precision = self.symbol_info_cache['price_precision']
        formatted = round(float(price), precision)
        
        # S'assurer que le prix respecte le tick size
        tick_size = self.symbol_info_cache['tick_size']
        formatted = round(formatted / tick_size) * tick_size
        formatted = round(formatted, precision)
        
        return formatted
    
    def format_quantity(self, quantity):
        """Formate la quantité selon la précision du symbole"""
        if not self.symbol_info_cache:
            return quantity
        
        precision = self.symbol_info_cache['quantity_precision']
        formatted = round(float(quantity), precision)
        
        # Vérifier quantité minimale
        min_qty = self.symbol_info_cache['min_quantity']
        if formatted < min_qty:
            print(f"⚠️ Quantité {formatted} < minimum {min_qty}")
            return min_qty
        
        return formatted
    
    def calculate_stop_loss_price(self, candles_data, side, lookback_candles, offset_percent):
        """
        Calcule le prix de Stop Loss basé sur les bougies historiques
        
        Args:
            candles_data: Liste des dernières bougies (dict avec 'high', 'low')
            side: 'LONG' ou 'SHORT'
            lookback_candles: Nombre de bougies à analyser
            offset_percent: Pourcentage d'offset à ajouter
        
        Returns:
            Prix de stop loss formaté
        """
        try:
            if len(candles_data) < lookback_candles:
                print(f"⚠️ Pas assez de bougies: {len(candles_data)} < {lookback_candles}")
                lookback_candles = len(candles_data)
            
            # Prendre les dernières bougies
            recent_candles = candles_data[-lookback_candles:]
            
            if side == 'LONG':
                # Pour LONG: SL en dessous du plus bas low
                lowest_low = min(float(candle['low']) for candle in recent_candles)
                sl_price = lowest_low - (lowest_low * offset_percent / 100)
                print(f"📉 LONG SL: Plus bas des {lookback_candles} bougies = {lowest_low}")
                print(f"   SL avec offset {offset_percent}% = {sl_price}")
                
            else:  # SHORT
                # Pour SHORT: SL au dessus du plus haut high
                highest_high = max(float(candle['high']) for candle in recent_candles)
                sl_price = highest_high + (highest_high * offset_percent / 100)
                print(f"📈 SHORT SL: Plus haut des {lookback_candles} bougies = {highest_high}")
                print(f"   SL avec offset {offset_percent}% = {sl_price}")
            
            return self.format_price(sl_price)
            
        except Exception as e:
            print(f"❌ Erreur calcul Stop Loss: {e}")
            return None
    
    def calculate_take_profit_price(self, entry_price, side, tp_percent):
        """
        Calcule le prix de Take Profit fixe depuis le prix d'entrée
        
        Args:
            entry_price: Prix d'entrée réel
            side: 'LONG' ou 'SHORT' 
            tp_percent: Pourcentage de profit cible
            
        Returns:
            Prix de take profit formaté
        """
        try:
            entry_price = float(entry_price)
            
            if side == 'LONG':
                # Pour LONG: TP au dessus du prix d'entrée
                tp_price = entry_price + (entry_price * tp_percent / 100)
                print(f"📈 LONG TP: {entry_price} + {tp_percent}% = {tp_price}")
                
            else:  # SHORT
                # Pour SHORT: TP en dessous du prix d'entrée
                tp_price = entry_price - (entry_price * tp_percent / 100)
                print(f"📉 SHORT TP: {entry_price} - {tp_percent}% = {tp_price}")
            
            return self.format_price(tp_price)
            
        except Exception as e:
            print(f"❌ Erreur calcul Take Profit: {e}")
            return None
    
    def calculate_position_size(self, balance, risk_percent, entry_price, stop_loss_price):
        """
        Calcule la taille de position basée sur le risk management
        
        Args:
            balance: Balance disponible
            risk_percent: Pourcentage de risque du capital
            entry_price: Prix d'entrée
            stop_loss_price: Prix de stop loss
            
        Returns:
            Quantité formatée selon les règles du symbole
        """
        try:
            balance = float(balance)
            risk_percent = float(risk_percent)
            entry_price = float(entry_price)
            stop_loss_price = float(stop_loss_price)
            
            # Montant à risquer
            risk_amount = balance * risk_percent / 100
            
            # Distance entre entrée et SL
            price_diff = abs(entry_price - stop_loss_price)
            
            if price_diff == 0:
                print("❌ Différence de prix nulle entre entrée et SL")
                return 0
            
            # Quantité = Montant_risque / Distance_prix
            quantity = risk_amount / price_diff
            
            print(f"💼 Calcul position:")
            print(f"   Balance: {balance} | Risque: {risk_percent}% = {risk_amount}")
            print(f"   Distance prix: {price_diff}")
            print(f"   Quantité brute: {quantity}")
            
            # Formatter et vérifier limites
            formatted_quantity = self.format_quantity(quantity)
            
            # Vérifier notional minimum
            notional = formatted_quantity * entry_price
            min_notional = self.symbol_info_cache.get('min_notional', 5.0)
            
            if notional < min_notional:
                print(f"⚠️ Notional {notional} < minimum {min_notional}")
                # Ajuster la quantité au minimum notional
                formatted_quantity = self.format_quantity(min_notional / entry_price)
                print(f"   Quantité ajustée: {formatted_quantity}")
            
            return formatted_quantity
            
        except Exception as e:
            print(f"❌ Erreur calcul taille position: {e}")
            return 0
    
    def get_current_positions(self):
        """Récupère les positions ouvertes"""
        try:
            positions = self.client.futures_position_information()
            
            # Filtrer seulement les positions avec une quantité non nulle
            active_positions = []
            for pos in positions:
                if pos['symbol'] == config.ASSET_CONFIG['SYMBOL']:
                    position_amt = float(pos['positionAmt'])
                    if position_amt != 0:
                        active_positions.append({
                            'symbol': pos['symbol'],
                            'side': 'LONG' if position_amt > 0 else 'SHORT',
                            'size': abs(position_amt),
                            'entry_price': float(pos['entryPrice']),
                            'mark_price': float(pos['markPrice']),
                            'pnl': float(pos['unRealizedProfit'])
                        })
            
            if active_positions:
                print(f"📊 Positions actives: {len(active_positions)}")
                for pos in active_positions:
                    print(f"   {pos['side']}: {pos['size']} @ {pos['entry_price']} (PnL: {pos['pnl']})")
            else:
                print("📊 Aucune position active")
            
            return active_positions
            
        except BinanceAPIException as e:
            print(f"❌ Erreur API récupération positions: {e}")
            return []
        except Exception as e:
            print(f"❌ Erreur récupération positions: {e}")
            return []
    
    def validate_trade_conditions(self, required_balance=None):
        """
        Valide les conditions avant de placer un trade
        
        Args:
            required_balance: Balance minimale requise (optionnel)
            
        Returns:
            dict avec status et message
        """
        try:
            # Vérifier connexion API
            try:
                server_time = self.client.futures_time()
                if not server_time:
                    return {'status': False, 'message': 'Connexion API échouée'}
            except:
                return {'status': False, 'message': 'Impossible de se connecter à Binance'}
            
            # Vérifier status du symbole
            if self.symbol_info_cache.get('status') != 'TRADING':
                return {'status': False, 'message': f"Symbole {config.ASSET_CONFIG['SYMBOL']} non disponible pour trading"}
            
            # Vérifier balance
            balance_asset = config.ASSET_CONFIG['BALANCE_ASSET']
            balance = self.get_account_balance(balance_asset)
            
            min_balance = required_balance or config.TRADING_CONFIG['MIN_BALANCE']
            if balance < min_balance:
                return {'status': False, 'message': f'Balance insuffisante: {balance} < {min_balance} {balance_asset}'}
            
            # Vérifier positions existantes si limite activée
            if config.TRADING_CONFIG['MAX_POSITIONS'] > 0:
                current_positions = self.get_current_positions()
                if len(current_positions) >= config.TRADING_CONFIG['MAX_POSITIONS']:
                    return {'status': False, 'message': f'Limite positions atteinte: {len(current_positions)}/{config.TRADING_CONFIG["MAX_POSITIONS"]}'}
            
            return {'status': True, 'message': 'Conditions validées'}
            
        except Exception as e:
            return {'status': False, 'message': f'Erreur validation: {str(e)}'}

if __name__ == "__main__":
    # Test du module
    try:
        print("🧪 Test PositionManager...")
        pm = PositionManager()
        
        # Test récupération balance
        balance = pm.get_account_balance(config.ASSET_CONFIG['BALANCE_ASSET'])
        
        # Test info symbole
        symbol_info = pm.get_symbol_info()
        print(f"📊 Info symbole: {symbol_info}")
        
        # Test formatage
        test_price = 43256.789123
        test_qty = 0.001234567
        
        formatted_price = pm.format_price(test_price)
        formatted_qty = pm.format_quantity(test_qty)
        
        print(f"🔢 Prix: {test_price} → {formatted_price}")
        print(f"🔢 Quantité: {test_qty} → {formatted_qty}")
        
        # Test calcul SL (avec données fictives)
        fake_candles = [
            {'high': 43300, 'low': 43200},
            {'high': 43280, 'low': 43180},
            {'high': 43320, 'low': 43220},
            {'high': 43290, 'low': 43150},  # Plus bas low
            {'high': 43310, 'low': 43190}
        ]
        
        sl_long = pm.calculate_stop_loss_price(fake_candles, 'LONG', 5, 0.1)
        sl_short = pm.calculate_stop_loss_price(fake_candles, 'SHORT', 5, 0.1)
        
        print(f"📉 SL LONG: {sl_long}")
        print(f"📈 SL SHORT: {sl_short}")
        
        # Test calcul TP
        tp_long = pm.calculate_take_profit_price(43200, 'LONG', 1.5)
        tp_short = pm.calculate_take_profit_price(43200, 'SHORT', 1.5)
        
        print(f"📈 TP LONG: {tp_long}")
        print(f"📉 TP SHORT: {tp_short}")
        
        # Test taille position
        if sl_long:
            position_size = pm.calculate_position_size(balance, 2.0, 43200, sl_long)
            print(f"💼 Taille position: {position_size}")
        
        # Test validation
        validation = pm.validate_trade_conditions()
        print(f"✅ Validation: {validation}")
        
        # Test positions actuelles
        positions = pm.get_current_positions()
        
        print("✅ Test PositionManager terminé avec succès")
        
    except Exception as e:
        print(f"❌ Erreur test PositionManager: {e}")