#!/usr/bin/env python3
"""
Script de debug pour identifier pourquoi les SL/TP retardés ne sont pas placés
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from datetime import datetime

def debug_delayed_sltp_status():
    """Debug complet du système SL/TP retardé"""
    print("🔍 DIAGNOSTIC SL/TP RETARDÉ")
    print("=" * 50)
    
    # 1. Vérifier la configuration
    print("\n1️⃣ VÉRIFICATION CONFIGURATION:")
    print("-" * 30)
    
    try:
        delayed_config = getattr(config, 'DELAYED_SLTP_CONFIG', None)
        if delayed_config:
            print(f"✅ DELAYED_SLTP_CONFIG trouvé:")
            print(f"   ENABLED: {delayed_config.get('ENABLED', 'NON DÉFINI')}")
            print(f"   PRICE_OFFSET_PERCENT: {delayed_config.get('PRICE_OFFSET_PERCENT', 'NON DÉFINI')}")
            print(f"   CHECK_INTERVAL_SECONDS: {delayed_config.get('CHECK_INTERVAL_SECONDS', 'NON DÉFINI')}")
        else:
            print("❌ DELAYED_SLTP_CONFIG manquant dans config.py")
            return
        
        trading_config = getattr(config, 'TRADING_CONFIG', None)
        if trading_config:
            print(f"\n✅ TRADING_CONFIG trouvé:")
            print(f"   ENABLED: {trading_config.get('ENABLED', 'NON DÉFINI')}")
            print(f"   USE_DELAYED_SLTP: {trading_config.get('USE_DELAYED_SLTP', 'NON DÉFINI')}")
        else:
            print("❌ TRADING_CONFIG manquant dans config.py")
            return
            
    except Exception as e:
        print(f"❌ Erreur lecture config: {e}")
        return
    
    # 2. Vérifier les imports
    print("\n2️⃣ VÉRIFICATION IMPORTS:")
    print("-" * 30)
    
    try:
        from delayed_sltp_manager import DelayedSLTPManager
        print("✅ DelayedSLTPManager importé avec succès")
    except ImportError as e:
        print(f"❌ Erreur import DelayedSLTPManager: {e}")
        return
    
    try:
        from trade_executor import TradeExecutor
        print("✅ TradeExecutor importé avec succès")
    except ImportError as e:
        print(f"❌ Erreur import TradeExecutor: {e}")
        return
    
    # 3. Vérifier si le bot utilise le système
    print("\n3️⃣ VÉRIFICATION INTÉGRATION BOT:")
    print("-" * 30)
    
    try:
        from trading_bot import HeikinAshiRSIBot
        print("✅ HeikinAshiRSIBot importé avec succès")
        
        # Vérifier les méthodes modifiées
        bot_methods = dir(HeikinAshiRSIBot)
        if 'execute_automatic_trade' in bot_methods:
            print("✅ execute_automatic_trade présent")
        else:
            print("❌ execute_automatic_trade manquant")
        
    except ImportError as e:
        print(f"❌ Erreur import HeikinAshiRSIBot: {e}")
        return
    
    # 4. Test création DelayedSLTPManager
    print("\n4️⃣ TEST CRÉATION GESTIONNAIRE:")
    print("-" * 30)
    
    try:
        class MockExecutor:
            def __init__(self):
                self.position_manager = type('obj', (object,), {'format_price': lambda self, x: round(x, 2)})()
            def get_current_price(self): return 43200.0
            def place_stop_loss_order(self, *args): return "sl_test"
            def place_take_profit_order(self, *args): return "tp_test"
        
        mock_executor = MockExecutor()
        manager = DelayedSLTPManager(mock_executor, None)  # type: ignore
        print("✅ DelayedSLTPManager créé avec succès")
        
        # Test des méthodes principales
        status = manager.get_pending_trades_status()
        print(f"✅ get_pending_trades_status() fonctionne: {status['total_pending']} trades")
        
    except Exception as e:
        print(f"❌ Erreur création DelayedSLTPManager: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n5️⃣ POINTS DE VÉRIFICATION POUR LE BOT:")
    print("-" * 30)
    print("Pour diagnostiquer votre problème, vérifiez dans les logs:")
    print()
    print("🔍 LOGS À RECHERCHER:")
    print("1. Au démarrage du bot:")
    print('   ✅ "🕐 MODE SL/TP RETARDÉ ACTIVÉ"')
    print('   ✅ "✅ Gestion SL/TP retardée activée"')
    print('   ✅ "🟢 Gestionnaire actif"')
    print()
    print("2. Lors d'un signal de trade:")
    print('   ✅ "🕐 Mode SL/TP RETARDÉ activé"')
    print('   ✅ "📅 Trade XXX enregistré pour SL/TP retardé"')
    print('   ✅ "👁️ Monitoring SL/TP retardé démarré"')
    print()
    print("3. À la fermeture de bougie (5 min plus tard):")
    print('   ✅ "🕐 TRAITEMENT TRADE RETARDÉ: XXX"')
    print('   ✅ "📊 Prix actuel: XXX"')
    print('   ✅ "🎯 Calcul SL ajusté:"')
    print('   ✅ "📋 Placement ordres retardés"')
    print()
    print("❌ LOGS PROBLÉMATIQUES:")
    print('   ❌ "⚠️ Erreur enregistrement trade retardé"')
    print('   ❌ "❌ Gestionnaire SL/TP retardé non disponible"')
    print('   ❌ "❌ Impossible de récupérer le prix actuel"')
    print('   ❌ "❌ Échec placement ordres retardés"')

def check_bot_configuration():
    """Vérification spécifique de la configuration du bot"""
    print("\n6️⃣ COMMANDES DEBUG POUR LE BOT:")
    print("-" * 30)
    print("Si votre bot tourne, vous pouvez tester ces commandes:")
    print()
    print("🎮 COMMANDES INTERACTIVES:")
    print("1. Dans la console Python où tourne le bot:")
    print("   >>> bot.handle_admin_commands('status_delayed')")
    print("   >>> bot.handle_admin_commands('list_delayed')")
    print()
    print("2. Vérifier l'état du trade_executor:")
    print("   >>> bot.trade_executor.delayed_sltp_manager")
    print("   >>> bot.trade_executor.get_complete_trading_status()")
    print()
    print("3. Forcer un traitement de test:")
    print("   >>> bot.trade_executor.force_process_delayed_trade('TRADE_ID')")

def generate_debug_config():
    """Génère une configuration de debug"""
    print("\n7️⃣ CONFIGURATION DEBUG RECOMMANDÉE:")
    print("-" * 30)
    print("Ajoutez ceci dans votre config.py pour plus de logs:")
    print()
    config_debug = '''
# Configuration SL/TP retardé avec logs détaillés
DELAYED_SLTP_CONFIG = {
    'ENABLED': True,
    'PRICE_OFFSET_PERCENT': 0.01,
    'CHECK_INTERVAL_SECONDS': 5,  # Plus fréquent pour debug
    'LOG_DETAILED_CALCULATIONS': True,
    'LOG_CANDLE_CLOSE_EVENTS': True,  # ACTIVER pour debug
    'LOG_PRICE_COMPARISONS': True,
    'LOG_OFFSET_APPLICATIONS': True,
}

# S'assurer que le trading utilise le mode retardé
TRADING_CONFIG = {
    # ... votre config existante ...
    'USE_DELAYED_SLTP': True,  # IMPORTANT!
    'ENABLED': True,
}

# Logs plus détaillés
LOG_SETTINGS = {
    # ... votre config existante ...
    'SHOW_WEBSOCKET_DEBUG': False,
    'SHOW_DATAFRAME_UPDATES': True,  # Voir les fermetures de bougies
    'SHOW_SIGNAL_ANALYSIS': True,
}
'''
    print(config_debug)

if __name__ == "__main__":
    debug_delayed_sltp_status()
    check_bot_configuration()
    generate_debug_config()
    
    print("\n🔧 ÉTAPES DE RÉSOLUTION:")
    print("=" * 30)
    print("1. Vérifiez que tous les ✅ sont présents ci-dessus")
    print("2. Redémarrez le bot avec la config debug")
    print("3. Cherchez les logs spécifiques dans la console")
    print("4. Si un trade est ouvert, utilisez les commandes debug")
    print("5. Partagez les logs exacts du problème")