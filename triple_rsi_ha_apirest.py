import json
import requests
import time
from datetime import datetime
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator

class CandleColorDetectorREST:
    def __init__(self, symbol="btcusdt", interval="1m", callback=None, market_type="futures", poll_interval=5):
        self.symbol = symbol.lower()
        self.interval = interval
        self.callback = callback
        self.market_type = market_type.lower()  # "spot" ou "futures"
        self.poll_interval = poll_interval  # Intervalle de polling en secondes
        self.running = False
        
        # URLs selon le type de marché
        if self.market_type == "futures":
            self.api_base_url = "https://fapi.binance.com"
            self.klines_endpoint = "/fapi/v1/klines"
        else:
            self.api_base_url = "https://api.binance.com"
            self.klines_endpoint = "/api/v3/klines"
        
        # Stockage des prix pour calculs RSI
        self.prices = []
        self.max_history = 50  # Garde les 50 derniers prix
        
        # Variables Heikin-Ashi précédentes
        self.prev_ha_open = None
        self.prev_ha_close = None
        
        # Stockage de la dernière bougie pour éviter les doublons
        self.last_candle_time = None
        
        # Instances RSI de la bibliothèque TA
        self.rsi_5_indicator = None
        self.rsi_14_indicator = None
        self.rsi_21_indicator = None
    
    def calculate_heikin_ashi(self, open_price, high_price, low_price, close_price):
        """
        Calcule les valeurs Heikin-Ashi pour la bougie courante
        """
        # Calcul Heikin-Ashi Close
        ha_close = (open_price + high_price + low_price + close_price) / 4
        
        # Calcul Heikin-Ashi Open
        if self.prev_ha_open is None or self.prev_ha_close is None:
            # Première bougie : utilise les valeurs normales
            ha_open = (open_price + close_price) / 2
        else:
            # Bougies suivantes : moyenne des HA open/close précédents
            ha_open = (self.prev_ha_open + self.prev_ha_close) / 2
        
        # Calcul Heikin-Ashi High et Low
        ha_high = max(high_price, ha_open, ha_close)
        ha_low = min(low_price, ha_open, ha_close)
        
        # Sauvegarde pour la prochaine bougie
        self.prev_ha_open = ha_open
        self.prev_ha_close = ha_close
        
        return {
            'ha_open': ha_open,
            'ha_high': ha_high,
            'ha_low': ha_low,
            'ha_close': ha_close
        }
    
    def get_heikin_ashi_color_and_trend(self, ha_data):
        """
        Détermine la couleur et la tendance basée sur Heikin-Ashi
        """
        ha_open = ha_data['ha_open']
        ha_close = ha_data['ha_close']
        
        # Détermine la couleur selon Heikin-Ashi
        if ha_close > ha_open:
            color = "🟢 VERTE (HA)"
            trend = "BULLISH"
        elif ha_close < ha_open:
            color = "🔴 ROUGE (HA)"
            trend = "BEARISH"
        else:
            color = "⚪ DOJI (HA)"
            trend = "NEUTRAL"
        
        # Calcul du changement en % basé sur Heikin-Ashi
        if ha_open != 0:
            ha_change_pct = ((ha_close - ha_open) / ha_open) * 100
        else:
            ha_change_pct = 0
            
        return color, trend, ha_change_pct
    
    def update_rsi_indicators(self):
        """
        Met à jour les indicateurs RSI avec les prix actuels
        """
        if len(self.prices) < 5:
            return
            
        # Convertit en pandas Series pour la bibliothèque TA
        price_series = pd.Series(self.prices)
        
        # Crée/met à jour les indicateurs RSI
        if len(self.prices) >= 5:
            self.rsi_5_indicator = RSIIndicator(close=price_series, window=5)
        if len(self.prices) >= 14:
            self.rsi_14_indicator = RSIIndicator(close=price_series, window=14)
        if len(self.prices) >= 21:
            self.rsi_21_indicator = RSIIndicator(close=price_series, window=21)
    
    def get_current_rsi_values(self):
        """
        Récupère les valeurs RSI actuelles
        """
        rsi_5 = None
        rsi_14 = None
        rsi_21 = None
        
        try:
            if self.rsi_5_indicator is not None:
                rsi_5 = self.rsi_5_indicator.rsi().iloc[-1]
                
            if self.rsi_14_indicator is not None:
                rsi_14 = self.rsi_14_indicator.rsi().iloc[-1]
                
            if self.rsi_21_indicator is not None:
                rsi_21 = self.rsi_21_indicator.rsi().iloc[-1]
                
        except Exception as e:
            print(f"⚠️  Erreur calcul RSI: {e}")
            
        return {
            'rsi_5': rsi_5,
            'rsi_14': rsi_14,
            'rsi_21': rsi_21
        }
    
    def update_rsi_values(self, close_price):
        """
        Met à jour les valeurs RSI avec le nouveau prix
        """
        # Calcule RSI AVANT d'ajouter le nouveau prix (synchronisation TradingView)
        current_rsi = self.get_current_rsi_values()
        
        # Ajoute le nouveau prix APRÈS avoir calculé le RSI
        self.prices.append(close_price)
        
        # Garde seulement les prix nécessaires
        if len(self.prices) > self.max_history:
            self.prices = self.prices[-self.max_history:]
        
        # Met à jour les indicateurs pour le prochain calcul
        self.update_rsi_indicators()
        
        # Retourne le RSI calculé AVANT l'ajout du nouveau prix
        return current_rsi
    
    def get_rsi_signal(self, rsi_value):
        """Détermine le signal RSI"""
        if rsi_value is None or pd.isna(rsi_value):
            return "⏳ N/A"
        elif rsi_value >= 70:
            return f"🔴 SURVENTE ({rsi_value:.1f})"
        elif rsi_value <= 30:
            return f"🟢 SURACHAT ({rsi_value:.1f})"
        else:
            return f"⚪ NEUTRE ({rsi_value:.1f})"
    
    def get_latest_candles(self, limit=2):
        """
        Récupère les dernières bougies via API REST
        """
        try:
            url = f"{self.api_base_url}{self.klines_endpoint}"
            params = {
                'symbol': self.symbol.upper(),
                'interval': self.interval,
                'limit': limit
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"⚠️  Erreur API: Status {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Erreur réseau: {e}")
            return None
        except Exception as e:
            print(f"⚠️  Erreur get_latest_candles: {e}")
            return None
    
    def process_candle(self, candle_data):
        """
        Traite une bougie fermée
        """
        try:
            # Extraction des données de la bougie
            open_time = int(candle_data[0])
            open_price = float(candle_data[1])
            high_price = float(candle_data[2])
            low_price = float(candle_data[3])
            close_price = float(candle_data[4])
            volume = float(candle_data[5])
            close_time = int(candle_data[6])
            
            # Vérifie si c'est une nouvelle bougie
            if self.last_candle_time is None or close_time > self.last_candle_time:
                self.last_candle_time = close_time
                
                # Calcule les valeurs Heikin-Ashi
                ha_data = self.calculate_heikin_ashi(open_price, high_price, low_price, close_price)
                
                # Détermine la couleur basée sur Heikin-Ashi
                color, trend, ha_change_pct = self.get_heikin_ashi_color_and_trend(ha_data)
                
                # Calcul du changement en % normal (pour comparaison)
                normal_change_pct = ((close_price - open_price) / open_price) * 100
                
                # Met à jour les RSI avec le nouveau prix de fermeture
                rsi_data = self.update_rsi_values(close_price)
                
                # Timestamp lisible
                close_datetime = datetime.fromtimestamp(close_time / 1000)
                
                # Affichage des résultats
                print(f"\n⚡ BOUGIE FERMÉE - {close_datetime.strftime('%H:%M:%S')}")
                print(f"📊 {self.symbol.upper()} | {self.interval} | {self.market_type.upper()}")
                print(f"💰 Normal: O=${open_price:,.2f} | C=${close_price:,.2f} | Δ={normal_change_pct:+.3f}%")
                print(f"🎯 Heikin-Ashi: O=${ha_data['ha_open']:,.2f} | C=${ha_data['ha_close']:,.2f} | Δ={ha_change_pct:+.3f}%")
                print(f"🎨 Couleur: {color} | {trend}")
                print(f"📊 RSI 5:  {self.get_rsi_signal(rsi_data['rsi_5'])}")
                print(f"📊 RSI 14: {self.get_rsi_signal(rsi_data['rsi_14'])}")
                print(f"📊 RSI 21: {self.get_rsi_signal(rsi_data['rsi_21'])}")
                print(f"📈 Volume: {volume:,.0f}")
                print("-" * 60)
                
                # Appel de callback personnalisé si défini
                if self.callback:
                    self.callback({
                        'symbol': self.symbol.upper(),
                        'interval': self.interval,
                        'market_type': self.market_type,
                        'open': open_price,
                        'close': close_price,
                        'high': high_price,
                        'low': low_price,
                        'volume': volume,
                        'ha_open': ha_data['ha_open'],
                        'ha_close': ha_data['ha_close'],
                        'ha_high': ha_data['ha_high'],
                        'ha_low': ha_data['ha_low'],
                        'color': 'green' if ha_data['ha_close'] > ha_data['ha_open'] else 'red' if ha_data['ha_close'] < ha_data['ha_open'] else 'doji',
                        'normal_change_pct': normal_change_pct,
                        'ha_change_pct': ha_change_pct,
                        'timestamp': close_datetime,
                        'rsi_5': rsi_data['rsi_5'],
                        'rsi_14': rsi_data['rsi_14'],
                        'rsi_21': rsi_data['rsi_21']
                    })
                
                return True  # Nouvelle bougie traitée
            
            return False  # Pas de nouvelle bougie
            
        except Exception as e:
            print(f"❌ Erreur process_candle: {e}")
            return False
    
    def load_initial_data(self):
        """Charge les données initiales pour calculer les RSI dès le début"""
        try:
            url = f"{self.api_base_url}{self.klines_endpoint}"
            params = {
                'symbol': self.symbol.upper(),
                'interval': self.interval,
                'limit': 50  # Assez pour calculer RSI 21
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                # Extrait les données OHLC pour initialiser Heikin-Ashi et RSI
                for candle in data[:-1]:  # Exclut la dernière bougie (en cours)
                    open_price = float(candle[1])  # Index 1 = open price
                    high_price = float(candle[2])  # Index 2 = high price
                    low_price = float(candle[3])   # Index 3 = low price
                    close_price = float(candle[4]) # Index 4 = close price
                    
                    # Ajoute aux prix pour RSI
                    self.prices.append(close_price)
                    
                    # Initialise Heikin-Ashi avec les données historiques
                    ha_data = self.calculate_heikin_ashi(open_price, high_price, low_price, close_price)
                
                # Initialise les indicateurs RSI avec les données historiques
                self.update_rsi_indicators()
                
                print(f"✅ {len(self.prices)} prix historiques chargés pour calcul RSI ({self.market_type.upper()})")
                
                # Affiche les RSI initiaux
                initial_rsi = self.get_current_rsi_values()
                rsi_5_str = f"{initial_rsi['rsi_5']:.1f}" if initial_rsi['rsi_5'] is not None and not pd.isna(initial_rsi['rsi_5']) else 'N/A'
                rsi_14_str = f"{initial_rsi['rsi_14']:.1f}" if initial_rsi['rsi_14'] is not None and not pd.isna(initial_rsi['rsi_14']) else 'N/A'
                rsi_21_str = f"{initial_rsi['rsi_21']:.1f}" if initial_rsi['rsi_21'] is not None and not pd.isna(initial_rsi['rsi_21']) else 'N/A'
                print(f"📊 RSI initial - 5: {rsi_5_str}, 14: {rsi_14_str}, 21: {rsi_21_str}")
                      
            else:
                print("⚠️  Impossible de charger les données historiques, RSI disponible après quelques bougies")
                
        except Exception as e:
            print(f"⚠️  Erreur lors du chargement initial: {e}")
            print("RSI sera disponible après quelques bougies")
    
    def start_monitoring(self):
        """Démarre le monitoring via polling REST API"""
        print("🔄 Chargement des données historiques...")
        self.load_initial_data()
        
        print(f"🚀 Démarrage du monitoring REST API")
        print(f"📊 {self.symbol.upper()} | {self.interval} | {self.market_type.upper()}")
        print(f"⏱️  Polling toutes les {self.poll_interval} secondes")
        print("🎯 En attente de nouvelles bougies fermées...")
        print("-" * 60)
        
        self.running = True
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while self.running:
            try:
                # Récupère les dernières bougies
                candles = self.get_latest_candles(limit=2)
                
                if candles and len(candles) >= 2:
                    # Traite la bougie fermée (avant-dernière)
                    closed_candle = candles[-2]  # Avant-dernière = fermée
                    processed = self.process_candle(closed_candle)
                    
                    if processed:
                        consecutive_errors = 0  # Reset le compteur d'erreurs
                    
                else:
                    print("⚠️  Aucune donnée reçue de l'API")
                    consecutive_errors += 1
                
                # Vérification du nombre d'erreurs consécutives
                if consecutive_errors >= max_consecutive_errors:
                    print(f"❌ Trop d'erreurs consécutives ({consecutive_errors}). Arrêt du monitoring.")
                    break
                
                # Attendre avant le prochain poll
                time.sleep(self.poll_interval)
                
            except KeyboardInterrupt:
                print("\n🛑 Arrêt demandé par l'utilisateur...")
                break
            except Exception as e:
                print(f"❌ Erreur monitoring: {e}")
                consecutive_errors += 1
                time.sleep(self.poll_interval)
        
        self.running = False
        print("🔌 Monitoring arrêté")
    
    def stop_monitoring(self):
        """Arrête le monitoring"""
        self.running = False
        print("🛑 Arrêt du monitoring REST API...")


# Fonctions utilitaires pour usage simple
def monitor_single_pair_rest(symbol="btcusdt", interval="1m", market_type="futures", poll_interval=5):
    """Fonction simple pour monitorer une paire via REST API"""
    detector = CandleColorDetectorREST(symbol, interval, market_type=market_type, poll_interval=poll_interval)
    
    try:
        detector.start_monitoring()
    except KeyboardInterrupt:
        print("\n🛑 Arrêt du monitoring...")
        detector.stop_monitoring()

def monitor_with_callback_rest(symbol="btcusdt", interval="1m", callback_func=None, market_type="futures", poll_interval=5):
    """Monitor avec callback personnalisé via REST API"""
    detector = CandleColorDetectorREST(symbol, interval, callback_func, market_type=market_type, poll_interval=poll_interval)
    
    try:
        detector.start_monitoring()
    except KeyboardInterrupt:
        print("\n🛑 Arrêt du monitoring...")
        detector.stop_monitoring()

# Exemple de callback personnalisé avec RSI et Heikin-Ashi
def my_candle_callback_rest(candle_data):
    """Exemple de fonction callback avec RSI et Heikin-Ashi pour REST API"""
    print(f"\n🎯 CALLBACK REST DÉCLENCHÉ:")
    
    # Analyse basée sur Heikin-Ashi
    if candle_data['color'] == 'green':
        print(f"✅ Bougie Heikin-Ashi VERTE sur {candle_data['symbol']} ({candle_data['market_type'].upper()})")
        print(f"   📈 HA: {candle_data['ha_change_pct']:+.3f}% | Normal: {candle_data['normal_change_pct']:+.3f}%")
    elif candle_data['color'] == 'red':
        print(f"🚨 Bougie Heikin-Ashi ROUGE sur {candle_data['symbol']} ({candle_data['market_type'].upper()})")
        print(f"   📉 HA: {candle_data['ha_change_pct']:+.3f}% | Normal: {candle_data['normal_change_pct']:+.3f}%")
    
    # Analyse RSI avec seuils plus conservateurs pour le REST
    rsi_14 = candle_data.get('rsi_14')
    if rsi_14 is not None and not pd.isna(rsi_14):
        if rsi_14 >= 75:  # Seuil plus élevé pour le REST
            print(f"⚠️  RSI 14 TRÈS SURVENTE: {rsi_14:.1f}")
        elif rsi_14 <= 25:  # Seuil plus bas pour le REST
            print(f"💡 RSI 14 TRÈS SURACHAT: {rsi_14:.1f}")
        elif rsi_14 >= 70:
            print(f"📊 RSI 14 en zone de survente: {rsi_14:.1f}")
        elif rsi_14 <= 30:
            print(f"📊 RSI 14 en zone de surachat: {rsi_14:.1f}")
    
    # Analyse de volume (disponible avec REST API)
    volume = candle_data.get('volume', 0)
    print(f"📊 Volume: {volume:,.0f}")
    
    # Signaux forts basés sur HA + RSI + Volume
    if (candle_data['color'] == 'green' and 
        rsi_14 is not None and not pd.isna(rsi_14) and rsi_14 <= 30 and 
        abs(candle_data['ha_change_pct']) > 0.1):
        print(f"🚀 SIGNAL BULLISH FORT: HA verte + RSI bas ({rsi_14:.1f}) + Mouvement significatif")
    
    elif (candle_data['color'] == 'red' and 
          rsi_14 is not None and not pd.isna(rsi_14) and rsi_14 >= 70 and 
          abs(candle_data['ha_change_pct']) > 0.1):
        print(f"🔥 SIGNAL BEARISH FORT: HA rouge + RSI haut ({rsi_14:.1f}) + Mouvement significatif")

# Utilisation simple
if __name__ == "__main__":
    print("🎯 Détecteur de couleur de bougie - REST API Version")
    print("📡 Heikin-Ashi + TA Library RSI + Polling REST")
    print("=" * 70)
    print("📋 Dépendances requises:")
    print("   pip install ta pandas numpy requests")
    print("=" * 70)
    
    # Option 1: Monitoring simple FUTURES avec polling rapide
    # monitor_single_pair_rest("btcusdt", "1m", "futures", poll_interval=3)
    
    # Option 2: Monitoring simple SPOT avec polling standard
    monitor_single_pair_rest("btcusdt", "1m", "spot", poll_interval=5)
    
    # Option 3: Avec callback personnalisé FUTURES (recommandé)
    # monitor_with_callback_rest("btcusdt", "1m", my_candle_callback_rest, "futures", poll_interval=5)
    
    # Option 4: Monitoring lent pour éviter les limites de rate
    # monitor_with_callback_rest("btcusdt", "5m", my_candle_callback_rest, "futures", poll_interval=10)