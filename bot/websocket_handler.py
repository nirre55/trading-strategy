"""
Gestionnaire WebSocket pour Binance Futures - Version avec reconnexion automatique
"""
import websocket
import json
import threading
import time
from datetime import datetime
from typing import Optional, TYPE_CHECKING
import config

if TYPE_CHECKING:
    from connection_manager import ConnectionManager

class BinanceWebSocketHandler:
    def __init__(self, symbol, timeframe, on_kline_callback):
        self.symbol = symbol.lower()
        self.timeframe = timeframe
        self.on_kline_callback = on_kline_callback
        self.ws = None
        self.is_running = False
        self.connection_manager: Optional['ConnectionManager'] = None  # Sera défini par ConnectionManager
        self.ws_thread = None
        
    def create_websocket_url(self):
        """Crée l'URL WebSocket pour le stream de klines"""
        stream_name = f"{self.symbol}@kline_{self.timeframe}"
        return f"{config.WEBSOCKET_URL}{stream_name}"
    
    def on_message(self, ws, message):
        """Callback appelé lors de la réception d'un message"""
        try:
            data = json.loads(message)
            if 'k' in data:
                kline_data = data['k']
                if config.LOG_SETTINGS['SHOW_WEBSOCKET_DEBUG']:
                    print(f"Données reçues: {kline_data['s']} - {kline_data['i']}")
                
                # Notifier ConnectionManager de la réception de données
                if self.connection_manager:
                    self.connection_manager.websocket_data_received_callback()
                
                # Appeler le callback avec les données de la bougie
                self.on_kline_callback(kline_data)
                
        except json.JSONDecodeError as e:
            print(f"Erreur lors du décodage JSON: {e}")
        except Exception as e:
            print(f"Erreur lors du traitement du message: {e}")
    
    def on_error(self, ws, error):
        """Callback appelé en cas d'erreur"""
        print(f"Erreur WebSocket: {error}")
        # Ne pas arrêter is_running ici - laisser ConnectionManager gérer
    
    def on_close(self, ws, close_status_code, close_msg):
        """Callback appelé lors de la fermeture de la connexion"""
        print(f"Connexion WebSocket fermée (code: {close_status_code})")
        
        # IMPORTANT: Ne plus mettre is_running = False ici
        # Laisser ConnectionManager gérer la reconnexion
        
        # Notifier ConnectionManager de la déconnexion
        if self.connection_manager:
            self.connection_manager.websocket_disconnected_callback()
        else:
            # Fallback si pas de ConnectionManager (ancien comportement)
            self.is_running = False
    
    def on_open(self, ws):
        """Callback appelé lors de l'ouverture de la connexion"""
        print(f"Connexion WebSocket ouverte pour {self.symbol.upper()} {self.timeframe}")
        self.is_running = True
        
        # Notifier ConnectionManager de la connexion
        if self.connection_manager:
            self.connection_manager.websocket_connected_callback()
    
    def start(self):
        """Démarre la connexion WebSocket"""
        url = self.create_websocket_url()
        print(f"Connexion à: {url}")
        
        websocket.enableTrace(config.LOG_SETTINGS['SHOW_WEBSOCKET_DEBUG'])
        self.ws = websocket.WebSocketApp(
            url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        # Démarrer dans un thread séparé
        self.ws_thread = threading.Thread(target=self.ws.run_forever)
        self.ws_thread.daemon = True
        self.ws_thread.start()
    
    def stop(self):
        """Arrête la connexion WebSocket"""
        print("🛑 Arrêt WebSocket demandé...")
        
        # Marquer comme arrêté
        self.is_running = False
        
        # Fermer connexion WebSocket
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                print(f"Erreur lors fermeture WebSocket: {e}")
        
        # Attendre fin du thread
        if self.ws_thread and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=5)
            if self.ws_thread.is_alive():
                print("⚠️ Thread WebSocket n'a pas pu être arrêté proprement")
        
        print("✅ WebSocket arrêté")
    
    def wait_for_connection(self, timeout=10):
        """Attend que la connexion soit établie"""
        start_time = time.time()
        while not self.is_running and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        return self.is_running
    
    def get_connection_status(self):
        """Retourne le statut de la connexion"""
        return {
            'is_running': self.is_running,
            'has_websocket': self.ws is not None,
            'thread_alive': self.ws_thread is not None and self.ws_thread.is_alive(),
            'symbol': self.symbol,
            'timeframe': self.timeframe
        }
    
    def force_reconnection(self):
        """Force une reconnexion (utilisé par ConnectionManager)"""
        print("🔄 Force reconnexion WebSocket...")
        
        # Arrêter proprement l'ancienne connexion
        self.stop()
        
        # Petit délai pour nettoyer
        time.sleep(1)
        
        # Redémarrer
        self.start()
    
    def is_healthy(self):
        """Vérifie si la connexion est en bonne santé"""
        return (
            self.is_running and 
            self.ws is not None and 
            self.ws_thread is not None and 
            self.ws_thread.is_alive()
        )