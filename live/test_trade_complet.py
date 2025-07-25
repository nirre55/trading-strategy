# test_trade_complet.py
"""
Test complet d'un trade BTCUSDC avec SL et TP
⚠️ ATTENTION: Ce test utilise de l'argent réel !
"""
import time
import sys
from pathlib import Path

# Ajout du chemin des modules
sys.path.append(str(Path(__file__).parent))

from binance_client import BinanceFuturesClient
from risk_manager import LiveRiskManager, PositionSize
from order_manager import LiveOrderManager
from config_live import TRADING_CONFIG, SAFETY_LIMITS

def load_api_keys():
    """Charge les clés API depuis .env"""
    try:
        with open('.env', 'r') as f:
            keys = {}
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    keys[key] = value
            return keys.get('BINANCE_API_KEY'), keys.get('BINANCE_API_SECRET')
    except FileNotFoundError:
        print("❌ Fichier .env non trouvé")
        return None, None

def test_trade_complet():
    """Test complet d'un trade avec SL/TP"""
    
    print("🧪 TEST COMPLET DE TRADING BTCUSDC")
    print("⚠️  ATTENTION: Utilise de l'argent réel !")
    print("="*60)
    
    # Confirmation utilisateur
    confirm = input("Confirmer le test avec argent réel (yes/no): ")
    if confirm.lower() != 'yes':
        print("Test annulé par l'utilisateur")
        return
    
    # Direction du trade
    print("\nChoisissez la direction du trade:")
    print("1. LONG (acheter)")
    print("2. SHORT (vendre)")
    direction_choice = input("Votre choix (1 ou 2): ")
    
    if direction_choice == "1":
        direction = "LONG"
        side = "BUY"
    elif direction_choice == "2":
        direction = "SHORT"
        side = "SELL"
    else:
        print("❌ Choix invalide")
        return
    
    try:
        # 1. Connexion Binance
        print("\n📡 1. Connexion à Binance...")
        api_key, api_secret = load_api_keys()
        if not api_key or not api_secret:
            print("❌ Clés API manquantes")
            return
        
        client = BinanceFuturesClient(api_key, api_secret, testnet=False)
        
        # 2. Vérification du solde
        print("💰 2. Vérification du solde...")
        balance, error = client.get_account_balance("USDC")
        if error:
            print(f"❌ Erreur solde: {error}")
            return
        
        print(f"✅ Solde disponible: {balance:.2f} USDC")
        
        if balance < 15:
            print("❌ Solde insuffisant pour le test (minimum 15 USDC)")
            return
        
        # 3. Prix actuel
        print("📊 3. Récupération prix actuel...")
        current_price, error = client.get_current_price("BTCUSDC")
        if error:
            print(f"❌ Erreur prix: {error}")
            return
        
        print(f"✅ Prix BTCUSDC: {current_price:.1f} USDC")
        
        # 4. Calcul SL et TP
        print("🧮 4. Calcul SL et TP...")
        
        # Risque fixe de 2 USDC
        risk_amount = 2.0
        
        if direction == "LONG":
            # SL 1% en dessous, TP 0.5% au dessus (ratio 1:2)
            stop_loss = current_price * 0.99  # -1%
            take_profit = current_price * 1.005  # +0.5%
        else:  # SHORT
            # SL 1% au dessus, TP 0.5% en dessous
            stop_loss = current_price * 1.01  # +1%
            take_profit = current_price * 0.995  # -0.5%
        
        # Calcul de la quantité
        sl_distance = abs(current_price - stop_loss)
        quantity = risk_amount / sl_distance
        position_value = quantity * current_price
        
        print(f"✅ Entry: {current_price:.1f} USDC")
        print(f"✅ Stop Loss: {stop_loss:.1f} USDC")
        print(f"✅ Take Profit: {take_profit:.1f} USDC")
        print(f"✅ Quantité: {quantity:.6f} BTC")
        print(f"✅ Valeur position: {position_value:.2f} USDC")
        print(f"✅ Risque: {risk_amount:.2f} USDC")
        
        # Confirmation finale
        print(f"\n📋 RÉSUMÉ DU TRADE {direction}:")
        print(f"Direction: {direction}")
        print(f"Quantité: {quantity:.6f} BTC")
        print(f"Valeur: {position_value:.2f} USDC")
        print(f"Risque max: {risk_amount:.2f} USDC")
        print(f"Gain potentiel: {risk_amount/2:.2f} USDC")
        
        final_confirm = input("\nConfirmer l'exécution du trade (yes/no): ")
        if final_confirm.lower() != 'yes':
            print("Trade annulé")
            return
        
        # 5. Ordre d'entrée (Market)
        print("\n🚀 5. Placement ordre d'entrée...")
        entry_result, error = client.place_market_order("BTCUSDC", side, quantity)
        if error:
            print(f"❌ Erreur ordre d'entrée: {error}")
            return
        
        print(f"✅ Ordre d'entrée exécuté: {entry_result.get('orderId')}")
        executed_price = float(entry_result.get('avgPrice', current_price))
        print(f"✅ Prix d'exécution: {executed_price:.1f} USDC")
        
        # 6. Ordre Stop Loss
        print("🛑 6. Placement Stop Loss...")
        close_side = "SELL" if direction == "LONG" else "BUY"
        
        sl_result, error = client.place_stop_order("BTCUSDC", close_side, quantity, stop_loss)
        if error:
            print(f"❌ Erreur Stop Loss: {error}")
            print("⚠️ ATTENTION: Position ouverte sans SL ! Fermer manuellement.")
        else:
            print(f"✅ Stop Loss placé: {sl_result.get('orderId')}")
        
        # 7. Ordre Take Profit
        print("🎯 7. Placement Take Profit...")
        tp_result, error = client.place_limit_order("BTCUSDC", close_side, quantity, take_profit)
        if error:
            print(f"❌ Erreur Take Profit: {error}")
            print("⚠️ ATTENTION: Position ouverte sans TP ! Fermer manuellement.")
        else:
            print(f"✅ Take Profit placé: {tp_result.get('orderId')}")
        
        # 8. Résumé final
        print("\n🎉 TRADE CRÉÉ AVEC SUCCÈS !")
        print("="*60)
        print(f"Direction: {direction}")
        print(f"Quantité: {quantity:.6f} BTC")
        print(f"Prix d'entrée: {executed_price:.1f} USDC")
        print(f"Stop Loss: {stop_loss:.1f} USDC")
        print(f"Take Profit: {take_profit:.1f} USDC")
        
        if 'sl_result' in locals() and sl_result:
            print(f"SL Order ID: {sl_result.get('orderId')}")
        if 'tp_result' in locals() and tp_result:
            print(f"TP Order ID: {tp_result.get('orderId')}")
        
        print("\n🔍 Surveillez votre position sur Binance !")
        print("⚠️ Le trade sera automatiquement fermé par SL ou TP")
        
        # 9. Surveillance basique (optionnelle)
        monitor = input("\nVoulez-vous surveiller la position ? (yes/no): ")
        if monitor.lower() == 'yes':
            print("\n📊 Surveillance de la position...")
            print("Appuyez sur Ctrl+C pour arrêter la surveillance")
            
            try:
                while True:
                    current_price, _ = client.get_current_price("BTCUSDC")
                    if current_price:
                        if direction == "LONG":
                            pnl = (current_price - executed_price) * quantity
                        else:
                            pnl = (executed_price - current_price) * quantity
                        
                        print(f"Prix: {current_price:.1f} USDC | PnL: {pnl:+.2f} USDC", end='\r')
                    
                    time.sleep(5)
                    
            except KeyboardInterrupt:
                print("\n📊 Surveillance arrêtée")
        
        print("\n✅ Test terminé avec succès !")
        return True
        
    except Exception as e:
        print(f"❌ Erreur durant le test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_positions_existantes():
    """Vérifie les positions existantes"""
    print("\n🔍 Vérification des positions existantes...")
    
    # api_key, api_secret = load_api_keys()
    # if not api_key:
    #     return
    api_key="0Ln7SbE79ve6E46KZWsLM61Axgx1Aoazm1uMYMOWaXFfxme7x39HoDzo3mJNK2NG"
    api_secret="E8PnpZfY5xbNDULJKPp6ASLS1Oq91x4bvigqkQ904AUVGDD5drscmppyTGF1C0aK"
    
    client = BinanceFuturesClient(api_key, api_secret, testnet=False)
    
    # Vérification position
    position, error = client.get_position_info("BTCUSDC")
    if error:
        print(f"❌ Erreur position: {error}")
        return
    
    position_size = float(position.get('positionAmt', 0))
    if position_size != 0:
        print(f"⚠️ Position existante détectée: {position_size:.6f} BTC")
        print(f"PnL non réalisé: {position.get('unrealizedProfit', 0)} USDC")
    else:
        print("✅ Aucune position ouverte")
    
    # Vérification ordres ouverts
    orders, error = client.get_open_orders("BTCUSDC")
    if not error and orders:
        print(f"📋 {len(orders)} ordre(s) ouvert(s):")
        for order in orders:
            print(f"  - {order['side']} {order['type']} @ {order.get('stopPrice', order.get('price', 'Market'))}")
    else:
        print("✅ Aucun ordre ouvert")

if __name__ == "__main__":
    print("🧪 TEST DE TRADING BTCUSDC")
    print("1. Test trade complet")
    print("2. Vérifier positions existantes")
    
    choice = input("\nVotre choix (1 ou 2): ")
    
    if choice == "1":
        test_trade_complet()
    elif choice == "2":
        test_positions_existantes()
    else:
        print("Choix invalide")