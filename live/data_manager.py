# data_manager.py
"""
Gestionnaire de données temps réel via WebSocket et API REST
"""
import logging
import json
import time
import threading
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
import websocket
from queue import Queue
from binance_client import BinanceFuturesClient

logger = logging.getLogger(__name__)

class RealTimeDataManager:
    """Gestionnaire de données temps réel pour le trading live"""
    
    def __init__(self, binance_client: BinanceFuturesClient, symbol: str = "BTCUSDT", timeframe: str = "5m"):
        self.client = binance_client
        self.symbol = symbol
        self.timeframe = timeframe
        
        # Stockage des données
        self.candles_df = pd.DataFrame()
        self.current_candle = {}
        self.indicators = {}
        
        # WebSocket
        self.ws = None
        self.ws_running = False
        self.reconnect_attempts = 0
        self.max_reconnects = 5
        
        # Callbacks
        self.on_candle_closed_callbacks = []
        self.on_price_update_callbacks = []
        
        # Threading
        self.data_lock = threading.Lock()
        self.update_queue = Queue()
        
        # Dernière mise à jour
        self.last_update = None
        self.heartbeat_interval = 30  # secondes
        
    def add_candle_closed_callback(self, callback: Callable):
        """Ajoute un callback appelé à chaque fermeture de bougie"""
        self.on_candle_closed_callbacks.append(callback)
    
    def add_price_update_callback(self, callback: Callable):
        """Ajoute un callback appelé à chaque mise à jour de prix"""
        self.on_price_update_callbacks.append(callback)
    
    def initialize_data(self, lookback_candles: int = 200):
        """Initialise les données historiques avec timeout réduit"""
        try:
            logger.info(f"📊 Initialisation des données {self.symbol} {self.timeframe}...")
            
            # Récupération des données historiques avec timeout réduit
            logger.debug("Appel API get_klines...")
            klines, error = self.client.get_klines(
                symbol=self.symbol,
                interval=self.timeframe,
                limit=lookback_candles  # Réduit de 500 à 200 pour être plus rapide
            )
            
            if error:
                logger.error(f"❌ Erreur récupération données: {error}")
                return False
            
            logger.debug(f"✅ {len(klines)} klines reçues")
            
            # Conversion en DataFrame
            logger.debug("Conversion en DataFrame...")
            df_data = []
            for i, kline in enumerate(klines):
                if i % 50 == 0:  # Log de progression
                    logger.debug(f"Traitement kline {i}/{len(klines)}")
                
                df_data.append({
                    'timestamp': pd.to_datetime(kline[0], unit='ms'),
                    'open': float(kline[1]),
                    'high': float(kline[2]),
                    'low': float(kline[3]),
                    'close': float(kline[4]),
                    'volume': float(kline[5])
                })
            
            logger.debug("Création DataFrame...")
            with self.data_lock:
                self.candles_df = pd.DataFrame(df_data)
                self.candles_df.set_index('timestamp', inplace=True)
                logger.debug("Calcul des indicateurs...")
                self.calculate_indicators()
            
            logger.info(f"✅ {len(self.candles_df)} bougies historiques chargées")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur initialisation données: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def calculate_indicators(self):
        """Calcule tous les indicateurs techniques - Version SANS THREADING"""
        if len(self.candles_df) < 50:
            logger.debug("Pas assez de données pour les indicateurs")
            return
        
        try:
            logger.debug("Import des fonctions d'indicateurs...")
            
            # Ajout du chemin vers le dossier backtest
            import sys
            from pathlib import Path
            backtest_path = Path(__file__).parent.parent / "backtest"
            if str(backtest_path) not in sys.path:
                sys.path.insert(0, str(backtest_path))
            
            # Import simple
            from indicators import (
                calculate_rsi, compute_heikin_ashi, 
                compute_trend_indicators, calculate_mtf_rsi
            )
            logger.debug("✅ Import indicators OK")
            
            # Copie des données
            logger.debug("Copie des données...")
            df_copy = self.candles_df.copy()
            logger.debug(f"Données copiées: {len(df_copy)} lignes")
            
            # Calculs step by step
            logger.debug("Calcul trend indicators...")
            df_copy = compute_trend_indicators(df_copy, ema_period=200, slope_lookback=5)
            logger.debug(f"✅ EMA calculée: {df_copy['EMA'].iloc[-1]:.2f}")
            
            logger.debug("Calcul Heikin Ashi...")
            df_copy = compute_heikin_ashi(df_copy)
            logger.debug(f"✅ HA calculé: {df_copy['HA_close'].iloc[-1]:.2f}")
            
            logger.debug("Calcul RSI multiples...")
            df_copy['RSI_5'] = calculate_rsi(df_copy['HA_close'], 5).round(2)
            df_copy['RSI_14'] = calculate_rsi(df_copy['HA_close'], 14).round(2)
            df_copy['RSI_21'] = calculate_rsi(df_copy['HA_close'], 21).round(2)
            logger.debug(f"✅ RSI calculés: {df_copy['RSI_14'].iloc[-1]:.1f}")
            
            logger.debug("Calcul RSI MTF...")
            df_copy['RSI_mtf'] = calculate_mtf_rsi(df_copy['HA_close'], 14).round(2)
            logger.debug(f"✅ RSI MTF: {df_copy['RSI_mtf'].iloc[-1]:.1f}")
            
            # Préparation des indicateurs
            logger.debug("Préparation des indicateurs...")
            new_indicators = {
                'RSI_5': float(df_copy['RSI_5'].iloc[-1]),
                'RSI_14': float(df_copy['RSI_14'].iloc[-1]),
                'RSI_21': float(df_copy['RSI_21'].iloc[-1]),
                'RSI_mtf': float(df_copy['RSI_mtf'].iloc[-1]),
                'HA_close': float(df_copy['HA_close'].iloc[-1]),
                'HA_open': float(df_copy['HA_open'].iloc[-1]),
                'HA_high': float(df_copy['HA_high'].iloc[-1]),
                'HA_low': float(df_copy['HA_low'].iloc[-1]),
                'EMA': float(df_copy['EMA'].iloc[-1]),
                'EMA_slope': float(df_copy['EMA_slope'].iloc[-1]),
                'close': float(df_copy['close'].iloc[-1]),
            }
            logger.debug("✅ Indicateurs préparés")
            
            # Mise à jour DIRECTE (sans lock pour éviter deadlock)
            logger.debug("Mise à jour directe...")
            self.candles_df = df_copy
            self.indicators = new_indicators
            logger.debug("✅ Mise à jour directe terminée")
            
            logger.debug("✅ Indicateurs calculés avec succès")
            logger.info(f"📊 Indicateurs mis à jour - RSI14: {self.indicators['RSI_14']:.1f}")
            
        except Exception as e:
            logger.error(f"❌ Erreur calcul indicateurs: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            
            # Fallback simple
            self._set_default_indicators()
    
    def _set_default_indicators(self):
        """Définit des indicateurs par défaut en cas d'erreur"""
        logger.warning("🔄 Utilisation d'indicateurs par défaut")
        try:
            if len(self.candles_df) > 0:
                last_close = float(self.candles_df['close'].iloc[-1])
            else:
                last_close = 40000.0  # Valeur par défaut
            
            default_indicators = {
                'RSI_5': 50.0,
                'RSI_14': 50.0,
                'RSI_21': 50.0,
                'RSI_mtf': 50.0,
                'HA_close': last_close,
                'HA_open': last_close,
                'HA_high': last_close,
                'HA_low': last_close,
                'EMA': last_close,
                'EMA_slope': 0.0,
                'close': last_close,
            }
            
            # Mise à jour directe
            self.indicators = default_indicators
            logger.info("✅ Indicateurs par défaut définis")
            
        except Exception as e:
            logger.error(f"❌ Erreur fallback: {e}")
            self.indicators = {k: 0.0 for k in ['RSI_5', 'RSI_14', 'RSI_21', 'RSI_mtf', 
                                               'HA_close', 'HA_open', 'HA_high', 'HA_low', 
                                               'EMA', 'EMA_slope', 'close']}
    
    def start_websocket(self):
        """Démarre le WebSocket pour les données temps réel"""
        if self.ws_running:
            return
        
        try:
            # URL WebSocket Binance
            base_url = "wss://fstream.binance.com" if not self.client.testnet else "wss://testnet.binancefuture.com"
            stream_name = f"{self.symbol.lower()}@kline_{self.timeframe}"
            ws_url = f"{base_url}/ws/{stream_name}"
            
            logger.info(f"🔌 Connexion WebSocket: {ws_url}")
            
            self.ws = websocket.WebSocketApp(
                ws_url,
                on_open=self._on_ws_open,
                on_message=self._on_ws_message,
                on_error=self._on_ws_error,
                on_close=self._on_ws_close
            )
            
            # Démarrage dans un thread séparé
            self.ws_thread = threading.Thread(target=self.ws.run_forever)
            self.ws_thread.daemon = True
            self.ws_thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur démarrage WebSocket: {e}")
            return False
    
    def _on_ws_open(self, ws):
        """Callback ouverture WebSocket"""
        logger.info("✅ WebSocket connecté")
        self.ws_running = True
        self.reconnect_attempts = 0
    
    def _on_ws_message(self, ws, message):
        """Callback réception message WebSocket"""
        try:
            data = json.loads(message)
            kline_data = data.get('k', {})
            
            if not kline_data:
                return
            
            # Mise à jour bougie courante
            self.current_candle = {
                'timestamp': pd.to_datetime(kline_data['t'], unit='ms'),
                'open': float(kline_data['o']),
                'high': float(kline_data['h']),
                'low': float(kline_data['l']),
                'close': float(kline_data['c']),
                'volume': float(kline_data['v']),
                'is_closed': kline_data['x']  # True si bougie fermée
            }
            
            self.last_update = datetime.now()
            
            # Callback mise à jour prix
            for callback in self.on_price_update_callbacks:
                try:
                    callback(self.current_candle)
                except Exception as e:
                    logger.error(f"❌ Erreur callback price update: {e}")
            
            # Si bougie fermée, mise à jour des données
            if self.current_candle['is_closed']:
                self._process_closed_candle()
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement message WebSocket: {e}")
    
    def _process_closed_candle(self):
        """Traite une bougie fermée - SANS LOCK"""
        try:
            new_candle = pd.DataFrame([{
                'timestamp': self.current_candle['timestamp'],
                'open': self.current_candle['open'],
                'high': self.current_candle['high'],
                'low': self.current_candle['low'],
                'close': self.current_candle['close'],
                'volume': self.current_candle['volume']
            }])
            new_candle.set_index('timestamp', inplace=True)
            
            # Ajout de la nouvelle bougie SANS LOCK
            self.candles_df = pd.concat([self.candles_df, new_candle])
            
            # Limitation de l'historique (garde 1000 bougies max)
            if len(self.candles_df) > 1000:
                self.candles_df = self.candles_df.tail(1000)
            
            # Recalcul des indicateurs
            self.calculate_indicators()
            
            logger.info(f"📊 Nouvelle bougie: {self.current_candle['close']:.1f} USDT")
            
            # Callbacks fermeture bougie
            for callback in self.on_candle_closed_callbacks:
                try:
                    callback(self.get_latest_data())
                except Exception as e:
                    logger.error(f"❌ Erreur callback candle closed: {e}")
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement bougie fermée: {e}")
    
    def _on_ws_error(self, ws, error):
        """Callback erreur WebSocket"""
        logger.error(f"❌ Erreur WebSocket: {error}")
    
    def _on_ws_close(self, ws, close_status_code, close_msg):
        """Callback fermeture WebSocket"""
        logger.warning(f"⚠️ WebSocket fermé: {close_status_code} - {close_msg}")
        self.ws_running = False
        
        # Tentative de reconnexion
        if self.reconnect_attempts < self.max_reconnects:
            self.reconnect_attempts += 1
            logger.info(f"🔄 Tentative de reconnexion {self.reconnect_attempts}/{self.max_reconnects}")
            time.sleep(5)
            self.start_websocket()
        else:
            logger.error("❌ Max tentatives de reconnexion atteint")
    
    def stop_websocket(self):
        """Arrête le WebSocket"""
        if self.ws:
            self.ws_running = False
            self.ws.close()
            logger.info("🔌 WebSocket fermé")
    
    def get_latest_data(self) -> Optional[Dict]:
        """Récupère les dernières données avec indicateurs - SANS LOCK"""
        if len(self.candles_df) == 0:
            return None
        
        try:
            latest_row = self.candles_df.iloc[-1]
            
            return {
                'timestamp': latest_row.name,
                'open': latest_row['open'],
                'high': latest_row['high'],
                'low': latest_row['low'],
                'close': latest_row['close'],
                'volume': latest_row['volume'],
                'indicators': self.indicators.copy() if self.indicators else {},
                'current_price': self.current_candle.get('close', latest_row['close'])
            }
        except Exception as e:
            logger.error(f"❌ Erreur get_latest_data: {e}")
            return None
    
    def get_connection_status(self) -> Dict:
        """Vérifie le statut de la connexion données"""
        return {
            'websocket_connected': self.ws_running,
            'last_update': self.last_update,
            'reconnect_attempts': self.reconnect_attempts,
            'data_points': len(self.candles_df),
            'current_price': self.current_candle.get('close', 0),
            'indicators_ready': len(self.indicators) > 0
        }
    
    def is_healthy(self) -> bool:
        """Vérifie si la connexion est saine"""
        if not self.ws_running:
            return False
        
        if self.last_update is None:
            return False
        
        # Vérification du heartbeat
        time_since_update = (datetime.now() - self.last_update).total_seconds()
        if time_since_update > self.heartbeat_interval:
            logger.warning(f"⚠️ Pas de mise à jour depuis {time_since_update}s")
            return False
        
        return True