# test_simple.py
"""
Test de connexion basique sans tous les indicateurs
"""
import os
from binance_client import BinanceFuturesClient

def test_connection():
    """Test simple de connexion"""
    print("🧪 Test de connexion Binance...")
    
    # Configuration
    api_key = "0Ln7SbE79ve6E46KZWsLM61Axgx1Aoazm1uMYMOWaXFfxme7x39HoDzo3mJNK2NG"
    api_secret = "E8PnpZfY5xbNDULJKPp6ASLS1Oq91x4bvigqkQ904AUVGDD5drscmppyTGF1C0aK"

    if not api_key or not api_secret:
        print("❌ Clés API manquantes")
        return False
    
    # Client
    client = BinanceFuturesClient(api_key, api_secret, testnet=False)
    
    # Test solde
    balance, error = client.get_account_balance()
    if error:
        print(f"❌ Erreur solde: {error}")
        return False
    
    print(f"✅ Solde: {balance} USDT")
    
    # Test prix
    price, error = client.get_current_price("BTCUSDT")
    if error:
        print(f"❌ Erreur prix: {error}")
        return False
    
    print(f"✅ Prix BTC: {price} USDT")
    
    # Test klines
    print("📊 Test récupération données...")
    klines, error = client.get_klines("BTCUSDT", "5m", 10)
    if error:
        print(f"❌ Erreur klines: {error}")
        return False
    
    print(f"✅ {len(klines)} bougies récupérées")
    
    # Test statut
    status = client.get_connection_status()
    print(f"📡 Statut: {status}")
    
    return True

if __name__ == "__main__":
    success = test_connection()
    if success:
        print("\n🎉 Tous les tests passés !")
    else:
        print("\n❌ Échec des tests")