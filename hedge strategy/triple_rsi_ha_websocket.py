import json
import websocket
from datetime import datetime
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
import os

class CandleColorDetector:
    def __init__(self, symbol="btcusdt", interval="1m", callback=None, market_type="futures"):
        self.symbol = symbol.lower()
        self.interval = interval
        self.ws = None
        self.last_close_time = None
        self.callback = callback
        self.market_type = market_type.lower()  # "spot" ou "futures"
        
        # URLs selon le type de marché
        if self.market_type == "futures":
            self.api_base_url = "https://fapi.binance.com"
            self.ws_base_url = "wss://fstream.binance.com"
        else:
            self.api_base_url = "https://api.binance.com"
            self.ws_base_url = "wss://stream.binance.com:9443"
        
        # Stockage des prix pour calculs RSI
        self.prices = []
        self.max_history = 50  # Garde les 50 derniers prix
        
        # Variables Heikin-Ashi précédentes
        self.prev_ha_open = None
        self.prev_ha_close = None
        
        # Variables de trading
        self.waiting_for_long_confirmation = False
        self.waiting_for_short_confirmation = False
        self.pending_long_signal = None
        self.pending_short_signal = None
        self.current_position = None
        
        # Fichier de log des trades
        self.log_file = f"trades_log_{self.symbol}_{self.interval}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        self.init_log_file()
    
    def init_log_file(self):
        """Initialise le fichier de log des trades"""
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write(f"LOG DES TRADES - {self.symbol.upper()} {self.interval}\n")
                f.write(f"Démarrage: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("="*80 + "\n\n")
            print(f"📝 Fichier de log créé: {self.log_file}")
        except Exception as e:
            print(f"⚠️  Erreur création fichier log: {e}")
    
    def log_trade_event(self, event_type, details):
        """Log un événement de trading dans le fichier"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {event_type}\n")
                for key, value in details.items():
                    f.write(f"  {key}: {value}\n")
                f.write("-" * 50 + "\n\n")
        except Exception as e:
            print(f"⚠️  Erreur écriture log: {e}")
    
    def check_rsi_signal(self, rsi_data):
        """Vérifie les conditions RSI pour entrée en position"""
        rsi_5 = rsi_data.get('rsi_5')
        rsi_14 = rsi_data.get('rsi_14')
        rsi_21 = rsi_data.get('rsi_21')
        
        # Vérifie que tous les RSI sont disponibles
        if any(rsi is None or pd.isna(rsi) for rsi in [rsi_5, rsi_14, rsi_21]):
            return None
        
        # Signal LONG: Tous les RSI < 30
        if rsi_5 < 30 and rsi_14 < 30 and rsi_21 < 30:
            return "LONG"
        
        # Signal SHORT: Tous les RSI > 70
        elif rsi_5 > 70 and rsi_14 > 70 and rsi_21 > 70:
            return "SHORT"
        
        return None
    
    def calculate_long_levels(self, entry_price, ha_low):
        """Calcule SL et TP pour position LONG"""
        stop_loss = ha_low * (1 - 0.001)  # SL = haLow - 0.1%
        risk = entry_price - stop_loss
        take_profit = entry_price + (risk * 1.2)  # TP = Entry + (Risk × 1.2)
        
        return {
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'risk': risk,
            'reward': take_profit - entry_price
        }
    
    def calculate_short_levels(self, entry_price, ha_high):
        """Calcule SL et TP pour position SHORT"""
        stop_loss = ha_high * (1 + 0.001)  # SL = haHigh + 0.1%
        risk = stop_loss - entry_price
        take_profit = entry_price - (risk * 1.2)  # TP = Entry - (Risk × 1.2)
        
        return {
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'risk': risk,
            'reward': entry_price - take_profit
        }
    
    def check_position_exit(self, current_price):
        """Vérifie si la position doit être fermée (SL ou TP atteint)"""
        if not self.current_position:
            return None
        
        position = self.current_position
        
        if position['direction'] == 'LONG':
            if current_price <= position['stop_loss']:
                return 'STOP_LOSS'
            elif current_price >= position['take_profit']:
                return 'TAKE_PROFIT'
        
        elif position['direction'] == 'SHORT':
            if current_price >= position['stop_loss']:
                return 'STOP_LOSS'
            elif current_price <= position['take_profit']:
                return 'TAKE_PROFIT'
        
        return None
    
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
    
    def calculate_rsi_values(self, close_price):
        """
        Met à jour et calcule les valeurs RSI avec la bibliothèque TA
        """
        # Ajoute le nouveau prix
        self.prices.append(close_price)
        
        # Garde seulement les prix nécessaires
        if len(self.prices) > self.max_history:
            self.prices = self.prices[-self.max_history:]
        
        # Convertit en pandas Series pour la bibliothèque TA
        price_series = pd.Series(self.prices)
        
        # Calcule RSI avec la bibliothèque TA pour différentes périodes
        rsi_5 = None
        rsi_14 = None
        rsi_21 = None
        
        try:
            if len(self.prices) >= 5:
                rsi_5_indicator = RSIIndicator(close=price_series, window=5)
                rsi_5_series = rsi_5_indicator.rsi()
                rsi_5 = rsi_5_series.iloc[-1] if not rsi_5_series.empty and not pd.isna(rsi_5_series.iloc[-1]) else None
                
            if len(self.prices) >= 14:
                rsi_14_indicator = RSIIndicator(close=price_series, window=14)
                rsi_14_series = rsi_14_indicator.rsi()
                rsi_14 = rsi_14_series.iloc[-1] if not rsi_14_series.empty and not pd.isna(rsi_14_series.iloc[-1]) else None
                
            if len(self.prices) >= 21:
                rsi_21_indicator = RSIIndicator(close=price_series, window=21)
                rsi_21_series = rsi_21_indicator.rsi()
                rsi_21 = rsi_21_series.iloc[-1] if not rsi_21_series.empty and not pd.isna(rsi_21_series.iloc[-1]) else None
                
        except Exception as e:
            print(f"⚠️  Erreur calcul RSI TA: {e}")
        
        return {
            'rsi_5': rsi_5,
            'rsi_14': rsi_14,
            'rsi_21': rsi_21
        }
    
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
    
    def get_timeout_seconds(self):
        """Calcule le timeout selon l'intervalle (5 bougies max)"""
        interval_to_seconds = {
            '1m': 60,
            '3m': 180,
            '5m': 300,
            '15m': 900,
            '30m': 1800,
            '1h': 3600,
            '2h': 7200,
            '4h': 14400,
            '6h': 21600,
            '8h': 28800,
            '12h': 43200,
            '1d': 86400
        }
        base_seconds = interval_to_seconds.get(self.interval, 300)  # Default 5m
        return base_seconds * 5  # 5 bougies max
    
    def on_message(self, ws, message):
        """Traite les messages WebSocket avec latence minimale"""
        try:
            data = json.loads(message)
            kline = data['k']
            
            # Vérifie si la bougie est fermée
            if kline['x']:  # kline is closed = True
                open_price = float(kline['o'])
                close_price = float(kline['c'])
                high_price = float(kline['h'])
                low_price = float(kline['l'])
                close_time = kline['T']  # Close timestamp
                
                # Évite les doublons
                if self.last_close_time != close_time:
                    self.last_close_time = close_time
                    
                    # Timestamp lisible - DÉFINI ICI EN PREMIER
                    close_datetime = datetime.fromtimestamp(close_time / 1000)
                    
                    # Calcule les valeurs Heikin-Ashi
                    ha_data = self.calculate_heikin_ashi(open_price, high_price, low_price, close_price)
                    
                    # Détermine la couleur basée sur Heikin-Ashi
                    color, trend, ha_change_pct = self.get_heikin_ashi_color_and_trend(ha_data)
                    
                    # Calcul du changement en % normal (pour comparaison)
                    normal_change_pct = ((close_price - open_price) / open_price) * 100
                    
                    # Met à jour les RSI avec le nouveau prix de fermeture (TA Library)
                    rsi_data = self.calculate_rsi_values(close_price)
                    
                    # ===============================
                    # LOGIQUE DE TRADING
                    # ===============================
                    
                    # 1. Vérifier si position ouverte doit être fermée
                    if self.current_position:
                        exit_reason = self.check_position_exit(close_price)
                        if exit_reason:
                            pnl = 0
                            if self.current_position['direction'] == 'LONG':
                                pnl = close_price - self.current_position['entry_price']
                            else:  # SHORT
                                pnl = self.current_position['entry_price'] - close_price
                            
                            pnl_pct = (pnl / self.current_position['entry_price']) * 100
                            
                            # Log fermeture position
                            self.log_trade_event("FERMETURE POSITION", {
                                "Direction": self.current_position['direction'],
                                "Raison": exit_reason,
                                "Prix d'entrée": f"${self.current_position['entry_price']:,.2f}",
                                "Prix de sortie": f"${close_price:,.2f}",
                                "PnL": f"${pnl:,.2f}",
                                "PnL %": f"{pnl_pct:+.2f}%",
                                "Stop Loss": f"${self.current_position['stop_loss']:,.2f}",
                                "Take Profit": f"${self.current_position['take_profit']:,.2f}",
                                "Durée": str(close_datetime - self.current_position['entry_time'])
                            })
                            
                            print(f"\n🚪 FERMETURE POSITION {self.current_position['direction']} - {exit_reason}")
                            print(f"💰 PnL: ${pnl:,.2f} ({pnl_pct:+.2f}%)")
                            
                            # Reset position
                            self.current_position = None
                    
                    # 2. Si pas de position, vérifier nouveaux signaux RSI
                    if not self.current_position:
                        rsi_signal = self.check_rsi_signal(rsi_data)
                        
                        # Signal RSI LONG détecté
                        if rsi_signal == "LONG" and not self.waiting_for_long_confirmation:
                            self.waiting_for_long_confirmation = True
                            self.pending_long_signal = {
                                'timestamp': close_datetime,
                                'rsi_5': rsi_data['rsi_5'],
                                'rsi_14': rsi_data['rsi_14'],
                                'rsi_21': rsi_data['rsi_21'],
                                'trigger_price': close_price
                            }
                            
                            self.log_trade_event("SIGNAL RSI LONG DÉTECTÉ", {
                                "RSI 5": f"{rsi_data['rsi_5']:.1f}",
                                "RSI 14": f"{rsi_data['rsi_14']:.1f}",
                                "RSI 21": f"{rsi_data['rsi_21']:.1f}",
                                "Prix": f"${close_price:,.2f}",
                                "Statut": "En attente de bougie HA verte"
                            })
                            
                            print(f"\n🟢 SIGNAL RSI LONG DÉTECTÉ !")
                            print(f"   RSI(5)={rsi_data['rsi_5']:.1f}, RSI(14)={rsi_data['rsi_14']:.1f}, RSI(21)={rsi_data['rsi_21']:.1f}")
                            print(f"   ⏳ En attente de bougie Heikin-Ashi VERTE...")
                        
                        # Signal RSI SHORT détecté
                        elif rsi_signal == "SHORT" and not self.waiting_for_short_confirmation:
                            self.waiting_for_short_confirmation = True
                            self.pending_short_signal = {
                                'timestamp': close_datetime,
                                'rsi_5': rsi_data['rsi_5'],
                                'rsi_14': rsi_data['rsi_14'],
                                'rsi_21': rsi_data['rsi_21'],
                                'trigger_price': close_price
                            }
                            
                            self.log_trade_event("SIGNAL RSI SHORT DÉTECTÉ", {
                                "RSI 5": f"{rsi_data['rsi_5']:.1f}",
                                "RSI 14": f"{rsi_data['rsi_14']:.1f}",
                                "RSI 21": f"{rsi_data['rsi_21']:.1f}",
                                "Prix": f"${close_price:,.2f}",
                                "Statut": "En attente de bougie HA rouge"
                            })
                            
                            print(f"\n🔴 SIGNAL RSI SHORT DÉTECTÉ !")
                            print(f"   RSI(5)={rsi_data['rsi_5']:.1f}, RSI(14)={rsi_data['rsi_14']:.1f}, RSI(21)={rsi_data['rsi_21']:.1f}")
                            print(f"   ⏳ En attente de bougie Heikin-Ashi ROUGE...")
                    
                    # 3. Vérifier confirmations Heikin-Ashi
                    if self.waiting_for_long_confirmation and ha_data['ha_close'] > ha_data['ha_open']:
                        # Bougie HA verte confirmée pour LONG
                        # Note: Dans la réalité, l'entrée se ferait à l'ouverture de la bougie SUIVANTE
                        # Ici on simule avec le prix de clôture actuel comme proxy
                        entry_price = close_price
                        levels = self.calculate_long_levels(entry_price, ha_data['ha_low'])
                        
                        self.current_position = {
                            'direction': 'LONG',
                            'entry_price': entry_price,
                            'entry_time': close_datetime,
                            'stop_loss': levels['stop_loss'],
                            'take_profit': levels['take_profit'],
                            'ha_confirmation': {
                                'ha_open': ha_data['ha_open'],
                                'ha_close': ha_data['ha_close'],
                                'ha_low': ha_data['ha_low']
                            }
                        }
                        
                        self.log_trade_event("ENTRÉE LONG CONFIRMÉE", {
                            "Signal RSI": f"RSI(5)={self.pending_long_signal['rsi_5']:.1f}, RSI(14)={self.pending_long_signal['rsi_14']:.1f}, RSI(21)={self.pending_long_signal['rsi_21']:.1f}", # type: ignore
                            "Confirmation HA": f"HA Close ({ha_data['ha_close']:.2f}) > HA Open ({ha_data['ha_open']:.2f})",
                            "Prix d'entrée": f"${entry_price:,.2f}",
                            "Stop Loss": f"${levels['stop_loss']:,.2f}",
                            "Take Profit": f"${levels['take_profit']:,.2f}",
                            "Risk": f"${levels['risk']:.2f}",
                            "Reward": f"${levels['reward']:.2f}",
                            "R/R Ratio": f"1:{levels['reward']/levels['risk']:.2f}"
                        })
                        
                        print(f"\n🚀 ENTRÉE LONG CONFIRMÉE !")
                        print(f"   💰 Entry: ${entry_price:,.2f}")
                        print(f"   🛡️  SL: ${levels['stop_loss']:,.2f}")
                        print(f"   🎯 TP: ${levels['take_profit']:,.2f}")
                        print(f"   📊 R/R: 1:{levels['reward']/levels['risk']:.2f}")
                        
                        # Reset signals
                        self.waiting_for_long_confirmation = False
                        self.pending_long_signal = None
                    
                    elif self.waiting_for_short_confirmation and ha_data['ha_close'] < ha_data['ha_open']:
                        # Bougie HA rouge confirmée pour SHORT
                        # Note: Dans la réalité, l'entrée se ferait à l'ouverture de la bougie SUIVANTE
                        # Ici on simule avec le prix de clôture actuel comme proxy
                        entry_price = close_price
                        levels = self.calculate_short_levels(entry_price, ha_data['ha_high'])
                        
                        self.current_position = {
                            'direction': 'SHORT',
                            'entry_price': entry_price,
                            'entry_time': close_datetime,
                            'stop_loss': levels['stop_loss'],
                            'take_profit': levels['take_profit'],
                            'ha_confirmation': {
                                'ha_open': ha_data['ha_open'],
                                'ha_close': ha_data['ha_close'],
                                'ha_high': ha_data['ha_high']
                            }
                        }
                        
                        self.log_trade_event("ENTRÉE SHORT CONFIRMÉE", {
                            "Signal RSI": f"RSI(5)={self.pending_short_signal['rsi_5']:.1f}, RSI(14)={self.pending_short_signal['rsi_14']:.1f}, RSI(21)={self.pending_short_signal['rsi_21']:.1f}", # type: ignore
                            "Confirmation HA": f"HA Close ({ha_data['ha_close']:.2f}) < HA Open ({ha_data['ha_open']:.2f})",
                            "Prix d'entrée": f"${entry_price:,.2f}",
                            "Stop Loss": f"${levels['stop_loss']:,.2f}",
                            "Take Profit": f"${levels['take_profit']:,.2f}",
                            "Risk": f"${levels['risk']:.2f}",
                            "Reward": f"${levels['reward']:.2f}",
                            "R/R Ratio": f"1:{levels['reward']/levels['risk']:.2f}"
                        })
                        
                        print(f"\n🩸 ENTRÉE SHORT CONFIRMÉE !")
                        print(f"   💰 Entry: ${entry_price:,.2f}")
                        print(f"   🛡️  SL: ${levels['stop_loss']:,.2f}")
                        print(f"   🎯 TP: ${levels['take_profit']:,.2f}")
                        print(f"   📊 R/R: 1:{levels['reward']/levels['risk']:.2f}")
                        
                        # Reset signals
                        self.waiting_for_short_confirmation = False
                        self.pending_short_signal = None
                    
                    # 4. Gérer les timeouts de signaux (éviter signaux trop anciens)
                    timeout_seconds = self.get_timeout_seconds()
                    
                    if self.waiting_for_long_confirmation and self.pending_long_signal:
                        time_diff = close_datetime - self.pending_long_signal['timestamp']
                        if time_diff.total_seconds() > timeout_seconds:
                            print(f"⏰ TIMEOUT - Signal LONG annulé après {timeout_seconds//60:.0f} minutes")
                            self.log_trade_event("TIMEOUT SIGNAL LONG", {
                                "Raison": f"Signal en attente depuis plus de {timeout_seconds//60:.0f} minutes",
                                "Signal original": f"RSI(5)={self.pending_long_signal['rsi_5']:.1f}",
                                "Durée d'attente": f"{time_diff.total_seconds():.0f} secondes"
                            })
                            self.waiting_for_long_confirmation = False
                            self.pending_long_signal = None
                    
                    if self.waiting_for_short_confirmation and self.pending_short_signal:
                        time_diff = close_datetime - self.pending_short_signal['timestamp']
                        if time_diff.total_seconds() > timeout_seconds:
                            print(f"⏰ TIMEOUT - Signal SHORT annulé après {timeout_seconds//60:.0f} minutes")
                            self.log_trade_event("TIMEOUT SIGNAL SHORT", {
                                "Raison": f"Signal en attente depuis plus de {timeout_seconds//60:.0f} minutes",
                                "Signal original": f"RSI(5)={self.pending_short_signal['rsi_5']:.1f}",
                                "Durée d'attente": f"{time_diff.total_seconds():.0f} secondes"
                            })
                            self.waiting_for_short_confirmation = False
                            self.pending_short_signal = None
                    
                    # ===============================
                    # AFFICHAGE ET CALLBACK
                    # ===============================
                    
                    # Affichage avec statut position
                    position_status = ""
                    if self.current_position:
                        pos = self.current_position
                        pnl = 0
                        if pos['direction'] == 'LONG':
                            pnl = close_price - pos['entry_price']
                        else:
                            pnl = pos['entry_price'] - close_price
                        pnl_pct = (pnl / pos['entry_price']) * 100
                        position_status = f" | 📈 {pos['direction']} PnL: ${pnl:+,.2f} ({pnl_pct:+.2f}%)"
                    elif self.waiting_for_long_confirmation:
                        position_status = " | ⏳ En attente HA VERTE"
                    elif self.waiting_for_short_confirmation:
                        position_status = " | ⏳ En attente HA ROUGE"
                    
                    # Affichage ultra-rapide avec RSI TA et Heikin-Ashi
                    print(f"\n⚡ BOUGIE FERMÉE - {close_datetime.strftime('%H:%M:%S')}{position_status}")
                    print(f"📊 {self.symbol.upper()} | {self.interval}")
                    print(f"💰 Normal: O=${open_price:,.2f} | C=${close_price:,.2f} | Δ={normal_change_pct:+.3f}%")
                    print(f"🎯 Heikin-Ashi: O=${ha_data['ha_open']:,.2f} | C=${ha_data['ha_close']:,.2f} | Δ={ha_change_pct:+.3f}%")
                    print(f"🎨 Couleur: {color} | {trend}")
                    print(f"📊 RSI 5 (TA):  {self.get_rsi_signal(rsi_data['rsi_5'])}")
                    print(f"📊 RSI 14 (TA): {self.get_rsi_signal(rsi_data['rsi_14'])}")
                    print(f"📊 RSI 21 (TA): {self.get_rsi_signal(rsi_data['rsi_21'])}")
                    print("-" * 50)
                    
                    # Appel de callback personnalisé si défini
                    if self.callback:
                        self.callback({
                            'symbol': self.symbol.upper(),
                            'interval': self.interval,
                            'open': open_price,
                            'close': close_price,
                            'high': high_price,
                            'low': low_price,
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
                            'rsi_21': rsi_data['rsi_21'],
                            'waiting_long': self.waiting_for_long_confirmation,
                            'waiting_short': self.waiting_for_short_confirmation,
                            'current_position': self.current_position
                        })
                        
        except Exception as e:
            print(f"❌ Erreur: {e}")
    
    def on_error(self, ws, error):
        print(f"❌ Erreur WebSocket: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        print("🔌 Connexion fermée")
    
    def on_open(self, ws):
        print(f"🚀 Connexion ouverte pour {self.symbol.upper()} ({self.market_type.upper()})")
        print(f"⏱️  Intervalle: {self.interval}")
        print("🎯 En attente de fermeture de bougie...")
        print("-" * 50)
    
    def load_initial_data(self):
        """Charge les données initiales pour calculer les RSI dès le début"""
        try:
            import requests
            
            # URL selon le type de marché
            if self.market_type == "futures":
                url = f"{self.api_base_url}/fapi/v1/klines"
            else:
                url = f"{self.api_base_url}/api/v3/klines"
                
            params = {
                'symbol': self.symbol.upper(),
                'interval': self.interval,
                'limit': 50  # Assez pour calculer RSI 21
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                
                # Extrait les données OHLC pour initialiser Heikin-Ashi
                for kline in data:
                    open_price = float(kline[1])  # Index 1 = open price
                    high_price = float(kline[2])  # Index 2 = high price
                    low_price = float(kline[3])   # Index 3 = low price
                    close_price = float(kline[4]) # Index 4 = close price
                    
                    # Ajoute aux prix pour RSI
                    self.prices.append(close_price)
                    
                    # Initialise Heikin-Ashi avec les données historiques
                    ha_data = self.calculate_heikin_ashi(open_price, high_price, low_price, close_price)
                
                print(f"✅ {len(self.prices)} prix historiques chargés pour calcul RSI TA ({self.market_type.upper()})")
                
                # Affiche les RSI initiaux avec la bibliothèque TA
                if len(self.prices) >= 5:
                    price_series = pd.Series(self.prices)
                    
                    try:
                        rsi_5_str = 'N/A'
                        rsi_14_str = 'N/A'
                        rsi_21_str = 'N/A'
                        
                        if len(self.prices) >= 5:
                            rsi_5_indicator = RSIIndicator(close=price_series, window=5)
                            rsi_5_series = rsi_5_indicator.rsi()
                            if not rsi_5_series.empty and not pd.isna(rsi_5_series.iloc[-1]):
                                rsi_5_str = f"{rsi_5_series.iloc[-1]:.1f}"
                        
                        if len(self.prices) >= 14:
                            rsi_14_indicator = RSIIndicator(close=price_series, window=14)
                            rsi_14_series = rsi_14_indicator.rsi()
                            if not rsi_14_series.empty and not pd.isna(rsi_14_series.iloc[-1]):
                                rsi_14_str = f"{rsi_14_series.iloc[-1]:.1f}"
                        
                        if len(self.prices) >= 21:
                            rsi_21_indicator = RSIIndicator(close=price_series, window=21)
                            rsi_21_series = rsi_21_indicator.rsi()
                            if not rsi_21_series.empty and not pd.isna(rsi_21_series.iloc[-1]):
                                rsi_21_str = f"{rsi_21_series.iloc[-1]:.1f}"
                        
                        print(f"📊 RSI TA initial - 5: {rsi_5_str}, 14: {rsi_14_str}, 21: {rsi_21_str}")
                        
                    except Exception as e:
                        print(f"⚠️  Erreur calcul RSI TA initial: {e}")
                      
            else:
                print("⚠️  Impossible de charger les données historiques, RSI disponible après quelques bougies")
                
        except Exception as e:
            print(f"⚠️  Erreur lors du chargement initial: {e}")
            print("RSI sera disponible après quelques bougies")
    
    def start_monitoring(self):
        """Démarre le monitoring avec latence minimale"""
        # Charge les données historiques pour RSI
        print("🔄 Chargement des données historiques...")
        self.load_initial_data()
        
        # URL WebSocket selon le type de marché
        if self.market_type == "futures":
            socket_url = f"{self.ws_base_url}/ws/{self.symbol}@kline_{self.interval}"
        else:
            socket_url = f"{self.ws_base_url}/ws/{self.symbol}@kline_{self.interval}"
        
        print(f"🔗 Connexion WebSocket: {self.market_type.upper()}")
        
        self.ws = websocket.WebSocketApp(
            socket_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        
        # Run forever avec reconnexion automatique
        self.ws.run_forever(
            ping_interval=20,  # Ping toutes les 20s
            ping_timeout=10    # Timeout après 10s
        )
    
    def stop_monitoring(self):
        """Arrête le monitoring"""
        if self.ws:
            self.ws.close()


# Fonctions utilitaires pour usage simple
def monitor_single_pair(symbol="btcusdt", interval="1m", market_type="futures"):
    """Fonction simple pour monitorer une paire"""
    detector = CandleColorDetector(symbol, interval, market_type=market_type)
    
    try:
        detector.start_monitoring()
    except KeyboardInterrupt:
        print("\n🛑 Arrêt du monitoring...")
        detector.stop_monitoring()

def monitor_with_callback(symbol="btcusdt", interval="1m", callback_func=None, market_type="futures"):
    """Monitor avec callback personnalisé"""
    detector = CandleColorDetector(symbol, interval, callback_func, market_type=market_type)
    
    try:
        detector.start_monitoring()
    except KeyboardInterrupt:
        print("\n🛑 Arrêt du monitoring...")
        detector.stop_monitoring()

# Exemple de callback personnalisé avec RSI TA et Heikin-Ashi
def my_candle_callback(candle_data):
    """Exemple de fonction callback avec RSI TA et Heikin-Ashi"""
    print(f"\n🎯 CALLBACK DÉCLENCHÉ:")
    
    # Analyse basée sur Heikin-Ashi
    if candle_data['color'] == 'green':
        print(f"✅ Bougie Heikin-Ashi VERTE sur {candle_data['symbol']}")
        print(f"   📈 HA: {candle_data['ha_change_pct']:+.3f}% | Normal: {candle_data['normal_change_pct']:+.3f}%")
    elif candle_data['color'] == 'red':
        print(f"🚨 Bougie Heikin-Ashi ROUGE sur {candle_data['symbol']}")
        print(f"   📉 HA: {candle_data['ha_change_pct']:+.3f}% | Normal: {candle_data['normal_change_pct']:+.3f}%")
    
    # Analyse RSI TA
    rsi_14 = candle_data.get('rsi_14')
    if rsi_14 is not None and not pd.isna(rsi_14):
        if rsi_14 >= 70:
            print(f"⚠️  RSI 14 TA en SURVENTE: {rsi_14:.1f}")
        elif rsi_14 <= 30:
            print(f"💡 RSI 14 TA en SURACHAT: {rsi_14:.1f}")
    
    # Analyse des signaux en cours
    if candle_data.get('waiting_long'):
        print(f"⏳ En attente de confirmation LONG (bougie HA verte)")
    elif candle_data.get('waiting_short'):
        print(f"⏳ En attente de confirmation SHORT (bougie HA rouge)")
    
    # Analyse position en cours
    current_pos = candle_data.get('current_position')
    if current_pos:
        direction = current_pos['direction']
        entry = current_pos['entry_price']
        sl = current_pos['stop_loss']
        tp = current_pos['take_profit']
        
        # Calcul PnL actuel (approximatif avec prix de clôture)
        current_price = candle_data['close']
        if direction == 'LONG':
            pnl = current_price - entry
        else:
            pnl = entry - current_price
        
        pnl_pct = (pnl / entry) * 100
        
        print(f"📊 Position {direction} active:")
        print(f"   Entry: ${entry:,.2f} | SL: ${sl:,.2f} | TP: ${tp:,.2f}")
        print(f"   PnL actuel: ${pnl:+,.2f} ({pnl_pct:+.2f}%)")
        
        # Distance aux niveaux
        if direction == 'LONG':
            dist_sl = ((current_price - sl) / entry) * 100
            dist_tp = ((tp - current_price) / entry) * 100
            print(f"   Distance SL: +{dist_sl:.2f}% | Distance TP: -{dist_tp:.2f}%")
        else:
            dist_sl = ((sl - current_price) / entry) * 100
            dist_tp = ((current_price - tp) / entry) * 100
            print(f"   Distance SL: +{dist_sl:.2f}% | Distance TP: -{dist_tp:.2f}%")
    
    # Analyse combinée HA + RSI TA
    if candle_data['color'] == 'green' and rsi_14 is not None and not pd.isna(rsi_14) and rsi_14 <= 35:
        print(f"🚀 SIGNAL FORT: Bougie HA verte + RSI TA bas ({rsi_14:.1f}) = Potentiel BULLISH")
    elif candle_data['color'] == 'red' and rsi_14 is not None and not pd.isna(rsi_14) and rsi_14 >= 65:
        print(f"🔥 SIGNAL FORT: Bougie HA rouge + RSI TA haut ({rsi_14:.1f}) = Potentiel BEARISH")
    
    # Analyse de la force du mouvement HA vs Normal
    ha_change = abs(candle_data['ha_change_pct'])
    normal_change = abs(candle_data['normal_change_pct'])
    
    if ha_change > normal_change * 1.5:
        print(f"💪 Mouvement HA amplifié: {ha_change:.3f}% vs {normal_change:.3f}% (tendance forte)")
    elif ha_change < normal_change * 0.5:
        print(f"🤏 Mouvement HA atténué: {ha_change:.3f}% vs {normal_change:.3f}% (consolidation)")

# Utilisation simple
if __name__ == "__main__":
    print("🎯 Détecteur de couleur de bougie - Heikin-Ashi + RSI TA Library + Trading Logic")
    print("=" * 80)
    print("📋 Dépendances requises:")
    print("   pip install ta pandas numpy websocket-client requests")
    print("=" * 80)
    print("🎮 Fonctionnalités:")
    print("   ✅ Détection RSI (5, 14, 21)")
    print("   ✅ Signaux LONG/SHORT (tous RSI < 30 ou > 70)")
    print("   ✅ Confirmation Heikin-Ashi (bougie verte/rouge)")
    print("   ✅ Calculs SL/TP automatiques (R/R = 1:1.2)")
    print("   ✅ Gestion positions (entrée/sortie simulées)")
    print("   ✅ Logging détaillé dans fichier")
    print("   ✅ Timeouts intelligents (5 bougies max)")
    print("   ✅ Monitoring PnL temps réel")
    print("=" * 80)
    
    # Option 1: Monitoring simple FUTURES (par défaut)
    # monitor_single_pair("btcusdt", "1m", "futures")
    
    # Option 2: Monitoring simple SPOT
    # monitor_single_pair("btcusdt", "1m", "spot")
    
    # Option 3: Avec callback personnalisé FUTURES
    # monitor_with_callback("btcusdt", "1m", my_candle_callback, "futures")
    
    # Option 4: Avec callback personnalisé SPOT
    monitor_with_callback("btcusdt", "5m", my_candle_callback, "spot")