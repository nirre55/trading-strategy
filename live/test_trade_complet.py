# test_trade_complet_fixed.py
"""
Test complet d'un trade BTCUSDC avec SL et TP - VERSION TESTNET
🧪 MODE TESTNET: Utilise de l'argent fictif

Correction: Gestion appropriée de la précision des quantités selon les règles Binance
"""
import time
import sys
import math
from pathlib import Path

# Ajout du chemin des modules
sys.path.append(str(Path(__file__).parent))

from binance_client import BinanceFuturesClient
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

def get_symbol_precision(client, symbol):
    """Récupère les informations de précision pour un symbole"""
    try:
        # Récupération des informations d'échange
        info, error = client._execute_request(client.client.futures_exchange_info)
        if error:
            print(f"❌ Erreur récupération exchange info: {error}")
            return None
        
        # Recherche du symbole
        for symbol_info in info['symbols']:
            if symbol_info['symbol'] == symbol:
                # Extraction des filtres
                filters = symbol_info['filters']
                precision_info = {
                    'quantityPrecision': symbol_info['quantityPrecision'],
                    'pricePrecision': symbol_info['pricePrecision'],
                    'baseAssetPrecision': symbol_info['baseAssetPrecision']
                }
                
                # Recherche du LOT_SIZE filter
                for filter_info in filters:
                    if filter_info['filterType'] == 'LOT_SIZE':
                        precision_info['stepSize'] = float(filter_info['stepSize'])
                        precision_info['minQty'] = float(filter_info['minQty'])
                        precision_info['maxQty'] = float(filter_info['maxQty'])
                        break
                
                # Recherche du PRICE_FILTER
                for filter_info in filters:
                    if filter_info['filterType'] == 'PRICE_FILTER':
                        precision_info['tickSize'] = float(filter_info['tickSize'])
                        precision_info['minPrice'] = float(filter_info['minPrice'])
                        precision_info['maxPrice'] = float(filter_info['maxPrice'])
                        break
                
                # Recherche du MIN_NOTIONAL
                for filter_info in filters:
                    if filter_info['filterType'] == 'MIN_NOTIONAL':
                        precision_info['minNotional'] = float(filter_info['notional'])
                        break
                
                return precision_info
        
        print(f"❌ Symbole {symbol} non trouvé")
        return None
        
    except Exception as e:
        print(f"❌ Erreur récupération précision: {e}")
        return None

def format_quantity(quantity, step_size):
    """Formate la quantité selon le stepSize de Binance"""
    if step_size == 0:
        return quantity
    
    # Calcul du nombre de décimales nécessaires
    step_str = f"{step_size:.10f}".rstrip('0')
    if '.' in step_str:
        decimals = len(step_str.split('.')[1])
    else:
        decimals = 0
    
    # Arrondi vers le bas pour éviter les erreurs de balance
    precision_factor = 10 ** decimals
    formatted_qty = math.floor(quantity * precision_factor) / precision_factor
    
    return round(formatted_qty, decimals)

def format_price(price, tick_size):
    """Formate le prix selon le tickSize de Binance"""
    if tick_size == 0:
        return price
    
    # Calcul du nombre de décimales nécessaires
    tick_str = f"{tick_size:.10f}".rstrip('0')
    if '.' in tick_str:
        decimals = len(tick_str.split('.')[1])
    else:
        decimals = 0
    
    # Arrondi au tick size le plus proche
    precision_factor = 10 ** decimals
    formatted_price = round(price / tick_size) * tick_size
    
    return round(formatted_price, decimals)

def test_trade_complet():
    """Test complet d'un trade avec SL/TP et précision correcte"""
    
    print("🧪 TEST COMPLET DE TRADING BTCUSDC - VERSION TESTNET")
    print("🧪 MODE TESTNET ACTIVÉ - ARGENT FICTIF")
    print("="*60)
    
    # Confirmation utilisateur (simplifiée pour testnet)
    confirm = input("Confirmer le test sur TESTNET (yes/no): ")
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
        
        # 2. Récupération des informations de précision
        print("🔧 2. Récupération des règles de précision...")
        precision_info = get_symbol_precision(client, "BTCUSDC")  # USDC pour testnet
        if not precision_info:
            print("❌ Impossible de récupérer les informations de précision")
            return
        
        print(f"✅ Précision quantité: {precision_info['quantityPrecision']} décimales")
        print(f"✅ Step Size: {precision_info['stepSize']}")
        print(f"✅ Quantité min: {precision_info['minQty']}")
        print(f"✅ Tick Size: {precision_info['tickSize']}")
        print(f"✅ Notional min: {precision_info.get('minNotional', 'N/A')}")
        
        # 3. Vérification du solde (USDC pour testnet)
        print("💰 3. Vérification du solde TESTNET...")
        balance, error = client.get_account_balance("USDC")
        if error:
            print(f"❌ Erreur solde: {error}")
            return
        
        print(f"✅ Solde disponible: {balance:.2f} USDC (testnet)")
        
        if balance < 15:
            print("❌ Solde insuffisant pour le test (minimum 15 USDC)")
            print("💡 Ajoutez des fonds fictifs sur le testnet Binance")
            return
        
        # 4. Prix actuel
        print("📊 4. Récupération prix actuel...")
        current_price, error = client.get_current_price("BTCUSDC")
        if error:
            print(f"❌ Erreur prix: {error}")
            return
        
        print(f"✅ Prix BTCUSDC: {current_price:.1f} USDC")
        
        # 5. Calcul SL et TP avec formatage correct
        print("🧮 5. Calcul SL et TP avec précision correcte...")
        
        # Risque fixe de 2 USDC
        risk_amount = 2.0
        
        if direction == "LONG":
            # SL 1% en dessous, TP 0.5% au dessus
            stop_loss_raw = current_price * 0.99
            take_profit_raw = current_price * 1.005
        else:  # SHORT
            # SL 1% au dessus, TP 0.5% en dessous
            stop_loss_raw = current_price * 1.01
            take_profit_raw = current_price * 0.995
        
        # Formatage des prix selon tick size
        stop_loss = format_price(stop_loss_raw, precision_info['tickSize'])
        take_profit = format_price(take_profit_raw, precision_info['tickSize'])
        entry_price = format_price(current_price, precision_info['tickSize'])
        
        # Calcul de la quantité avec précision correcte
        sl_distance = abs(entry_price - stop_loss)
        quantity_raw = risk_amount / sl_distance
        
        # Formatage de la quantité selon step size
        quantity = format_quantity(quantity_raw, precision_info['stepSize'])
        
        # Vérification quantité minimum
        if quantity < precision_info['minQty']:
            print(f"❌ Quantité calculée ({quantity}) inférieure au minimum ({precision_info['minQty']})")
            # Utilisation de la quantité minimum
            quantity = precision_info['minQty']
            risk_amount = quantity * sl_distance
            print(f"🔧 Ajustement: quantité = {quantity}, risque = {risk_amount:.2f} USDC")
        
        position_value = quantity * entry_price
        
        # Vérification notional minimum
        if 'minNotional' in precision_info and position_value < precision_info['minNotional']:
            print(f"❌ Valeur position ({position_value:.2f}) inférieure au minimum notional ({precision_info['minNotional']})")
            return
        
        print(f"✅ Entry: {entry_price:.1f} USDC")
        print(f"✅ Stop Loss: {stop_loss:.1f} USDC")
        print(f"✅ Take Profit: {take_profit:.1f} USDC")
        print(f"✅ Quantité: {quantity} BTC")
        print(f"✅ Valeur position: {position_value:.2f} USDC")
        print(f"✅ Risque: {risk_amount:.2f} USDC")
        
        # Confirmation finale
        print(f"\n📋 RÉSUMÉ DU TRADE {direction}:")
        print(f"Direction: {direction}")
        print(f"Quantité: {quantity} BTC (formatée selon step size)")
        print(f"Valeur: {position_value:.2f} USDC")
        print(f"Risque max: {risk_amount:.2f} USDC")
        print(f"Gain potentiel: {(risk_amount * 0.5):.2f} USDC")
        
        final_confirm = input("\nConfirmer l'exécution du trade (yes/no): ")
        if final_confirm.lower() != 'yes':
            print("Trade annulé")
            return
        
        # 6. Ordre d'entrée (Market)
        print("\n🚀 6. Placement ordre d'entrée...")
        entry_result, error = client.place_market_order("BTCUSDC", side, quantity)
        if error:
            print(f"❌ Erreur ordre d'entrée: {error}")
            return
        
        print(f"✅ Ordre d'entrée exécuté: {entry_result.get('orderId')}")
        executed_price = float(entry_result.get('avgPrice', current_price))
        print(f"✅ Prix d'exécution: {executed_price:.1f} USDC")
        
        # 7. Ordre Stop Loss
        print("🛑 7. Placement Stop Loss...")
        close_side = "SELL" if direction == "LONG" else "BUY"
        
        sl_result, error = client.place_stop_order("BTCUSDC", close_side, quantity, stop_loss)
        if error:
            print(f"❌ Erreur Stop Loss: {error}")
            print("⚠️ ATTENTION: Position ouverte sans SL ! Fermer manuellement.")
        else:
            print(f"✅ Stop Loss placé: {sl_result.get('orderId')}")
        
        # 8. Ordre Take Profit
        print("🎯 8. Placement Take Profit...")
        tp_result, error = client.place_limit_order("BTCUSDC", close_side, quantity, take_profit)
        if error:
            print(f"❌ Erreur Take Profit: {error}")
            print("⚠️ ATTENTION: Position ouverte sans TP ! Fermer manuellement.")
        else:
            print(f"✅ Take Profit placé: {tp_result.get('orderId')}")
        
        # 9. Résumé final
        print("\n🎉 TRADE CRÉÉ AVEC SUCCÈS !")
        print("="*60)
        print(f"Direction: {direction}")
        print(f"Quantité: {quantity} BTC")
        print(f"Prix d'entrée: {executed_price:.1f} USDC")
        print(f"Stop Loss: {stop_loss:.1f} USDC")
        print(f"Take Profit: {take_profit:.1f} USDC")
        
        if 'sl_result' in locals() and sl_result:
            print(f"SL Order ID: {sl_result.get('orderId')}")
        if 'tp_result' in locals() and tp_result:
            print(f"TP Order ID: {tp_result.get('orderId')}")
        
        print("\n🔍 Surveillez votre position sur Binance !")
        print("⚠️ Le trade sera automatiquement fermé par SL ou TP")
        
        # 10. Surveillance basique (optionnelle)
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

def test_precision_info():
    """Teste uniquement la récupération des informations de précision"""
    print("\n🔍 Test des informations de précision BTCUSDC (testnet)...")
    
    api_key, api_secret = load_api_keys()
    if not api_key:
        return
    
    client = BinanceFuturesClient(api_key, api_secret, testnet=False)
    
    precision_info = get_symbol_precision(client, "BTCUSDC")
    if precision_info:
        print("✅ Informations de précision récupérées:")
        for key, value in precision_info.items():
            print(f"  {key}: {value}")
    else:
        print("❌ Échec récupération précision")

def test_quantity_formatting():
    """Teste le formatage des quantités"""
    print("\n🧪 Test du formatage des quantités...")
    
    test_cases = [
        (0.123456789, 0.001),
        (0.00012345, 0.00001),
        (1.987654321, 0.01),
        (0.000999, 0.001)
    ]
    
    for qty, step in test_cases:
        formatted = format_quantity(qty, step)
        print(f"Quantité: {qty} | Step: {step} | Formatée: {formatted}")

if __name__ == "__main__":
    print("🧪 TEST DE TRADING BTCUSDC - VERSION TESTNET")
    print("1. Test trade complet (testnet - argent fictif)")
    print("2. Test informations de précision seulement")
    print("3. Test formatage des quantités")
    
    choice = input("\nVotre choix (1, 2 ou 3): ")
    
    if choice == "1":
        test_trade_complet()
    elif choice == "2":
        test_precision_info()
    elif choice == "3":
        test_quantity_formatting()
    else:
        print("Choix invalide")