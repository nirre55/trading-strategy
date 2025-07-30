"""
Gestionnaire WebSocket pour Binance Futures
"""
import websocket
import json
import threading
import time
from datetime import datetime
import config

class BinanceWebSocketHandler:
    def __init__(self, symbol, timeframe, on_kline_callback):
        self.symbol = symbol.lower()
        self.timeframe = timeframe
        self.on_kline_callback = on_kline_callback
        self.ws = None
        self.is_running = False
        
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
                
                # Appeler le callback avec les données de la bougie
                self.on_kline_callback(kline_data)
                
        except json.JSONDecodeError as e:
            print(f"Erreur lors du décodage JSON: {e}")
        except Exception as e:
            print(f"Erreur lors du traitement du message: {e}")
    
    def on_error(self, ws, error):
        """Callback appelé en cas d'erreur"""
        print(f"Erreur WebSocket: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        """Callback appelé lors de la fermeture de la connexion"""
        print("Connexion WebSocket fermée")
        self.is_running = False
    
    def on_open(self, ws):
        """Callback appelé lors de l'ouverture de la connexion"""
        print(f"Connexion WebSocket ouverte pour {self.symbol.upper()} {self.timeframe}")
        self.is_running = True
    
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
        if self.ws:
            self.ws.close()
        self.is_running = False
    
    def wait_for_connection(self, timeout=10):
        """Attend que la connexion soit établie"""
        start_time = time.time()
        while not self.is_running and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        return self.is_running