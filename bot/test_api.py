#!/usr/bin/env python3
"""Test rapide des API Keys Binance Futures"""

import os
from binance.client import Client

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

def test_binance_connection():
    try:
        print("🔍 Test connexion Binance Futures...")
        
        # Charger les clés
        api_key = load_api_credentials_from_env("BINANCE_API_KEY")
        api_secret = load_api_credentials_from_env("BINANCE_API_SECRET")
        
        print(f"✅ API Key chargée: {api_key[:10]}...{api_key[-4:]}")
        
        # Client Futures
        client = Client(api_key, api_secret)
        client.API_URL = 'https://fapi.binance.com'
        
        # Test 1: Heure serveur
        print("\n📡 Test 1: Connexion serveur...")
        server_time = client.futures_time()
        print(f"✅ Heure serveur: {server_time}")
        
        # Test 2: Info compte
        print("\n💰 Test 2: Information compte...")
        account = client.futures_account()
        total_balance = sum(float(asset['walletBalance']) for asset in account['assets'] if float(asset['walletBalance']) > 0)
        print(f"✅ Balance totale: {total_balance:.2f} USDT")
        
        # Test 3: Positions
        print("\n📊 Test 3: Positions...")
        positions = client.futures_position_information()
        active_positions = [p for p in positions if float(p['positionAmt']) != 0]
        print(f"✅ Positions actives: {len(active_positions)}")
        
        # Test 4: Info symbole
        print("\n🎯 Test 4: Info symbole BTCUSDT...")
        exchange_info = client.futures_exchange_info()
        btc_info = next((s for s in exchange_info['symbols'] if s['symbol'] == 'BTCUSDT'), None)
        if btc_info:
            print(f"✅ BTCUSDT status: {btc_info['status']}")
        else:
            print("❌ BTCUSDT non trouvé")
        
        print("\n🎉 TOUS LES TESTS RÉUSSIS!")
        print("✅ Connexion API Binance Futures opérationnelle")
        
    except Exception as e:
        print(f"\n❌ ÉCHEC TEST: {e}")
        print("\n🔧 Solutions possibles:")
        print("1. Vérifiez vos clés API dans le fichier .env")
        print("2. Assurez-vous que les permissions Futures Trading sont activées")
        print("3. Vérifiez que votre IP est autorisée dans Binance")
        print("4. Attendez quelques minutes si rate limiting")

if __name__ == "__main__":
    test_binance_connection()