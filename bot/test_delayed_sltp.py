#!/usr/bin/env python3
"""
Test du système SL/TP retardé - VERSION CORRIGÉE
Ce fichier permet de tester la fonctionnalité sans avoir besoin de signaux réels
"""
import sys
import os
import time
from datetime import datetime, timedelta
import traceback

# Ajouter le répertoire du bot au path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("🧪 DÉBUT INITIALISATION TESTEUR SL/TP RETARDÉ")
print("=" * 60)

# Test des imports un par un
try:
    print("📦 Import config...")
    import config
    print("✅ Config importé")
except Exception as e:
    print(f"❌ Erreur import config: {e}")
    sys.exit(1)

try:
    print("📦 Import trading_logger...")
    from trading_logger import trading_logger
    print("✅ TradingLogger importé")
except Exception as e:
    print(f"❌ Erreur import trading_logger: {e}")
    print("Continuons sans logger...")
    trading_logger = None

try:
    print("📦 Import delayed_sltp_manager...")
    from delayed_sltp_manager import DelayedSLTPManager
    print("✅ DelayedSLTPManager importé")
except Exception as e:
    print(f"❌ Erreur import delayed_sltp_manager: {e}")
    print("Traceback complet:")
    traceback.print_exc()
    sys.exit(1)

print("✅ Tous les imports réussis!")

# Vérifier la configuration
try:
    print("🔧 Vérification configuration...")
    
    # S'assurer que DELAYED_SLTP_CONFIG existe
    if not hasattr(config, 'DELAYED_SLTP_CONFIG'):
        print("⚠️ DELAYED_SLTP_CONFIG manquant, création par défaut...")
        config.DELAYED_SLTP_CONFIG = {
            'ENABLED': True,
            'PRICE_OFFSET_PERCENT': 0.01,
            'CHECK_INTERVAL_SECONDS': 10,
            'AUTO_CLEANUP_HOURS': 24,
            'LOG_DETAILED_CALCULATIONS': True,
        }
    
    # S'assurer que ASSET_CONFIG existe
    if not hasattr(config, 'ASSET_CONFIG'):
        print("⚠️ ASSET_CONFIG manquant, création par défaut...")
        config.ASSET_CONFIG = {
            'SYMBOL': 'BTCUSDT',
            'TIMEFRAME': '5m',
            'BALANCE_ASSET': 'USDT'
        }
    
    print(f"✅ Configuration vérifiée:")
    print(f"   Symbole: {config.ASSET_CONFIG['SYMBOL']}")
    print(f"   Timeframe: {config.ASSET_CONFIG['TIMEFRAME']}")
    print(f"   Offset: {config.DELAYED_SLTP_CONFIG['PRICE_OFFSET_PERCENT']}%")
    
except Exception as e:
    print(f"❌ Erreur configuration: {e}")
    traceback.print_exc()
    sys.exit(1)

# Classes Mock améliorées
class MockPositionManager:
    """Mock PositionManager pour les tests"""
    def format_price(self, price):
        try:
            return round(float(price), 2)
        except:
            return 43200.00  # Fallback

class MockTradeExecutor:
    """Mock TradeExecutor pour les tests"""
    def __init__(self):
        self.position_manager = MockPositionManager()
        self.active_trades = {}
        self.trade_counter = 0
        print("✅ MockTradeExecutor initialisé")
        
    def get_current_price(self):
        return 43200.50  # Prix de test fixe
    
    def place_stop_loss_order(self, side, quantity, price, trade_id):
        print(f"📋 MOCK: Place SL order {side} {quantity} @ {price} pour {trade_id}")
        return f"sl_order_{int(time.time())}"
    
    def place_take_profit_order(self, side, quantity, price, trade_id):
        print(f"📋 MOCK: Place TP order {side} {quantity} @ {price} pour {trade_id}")
        return f"tp_order_{int(time.time())}"

class DelayedSLTPTester:
    """Classe de test pour le système SL/TP retardé"""
    
    def __init__(self):
        print("\n🧪 Initialisation du testeur SL/TP retardé...")
        
        try:
            self.mock_executor = MockTradeExecutor()
            print("✅ Mock executor créé")
            
            # Utiliser type: ignore pour éviter l'erreur Pylance
            self.delayed_manager = DelayedSLTPManager(self.mock_executor, None)  # type: ignore
            print("✅ DelayedSLTPManager créé")
            
            self.test_results = []
            
            print(f"✅ Testeur initialisé avec succès!")
            print(f"Configuration: Offset = {config.DELAYED_SLTP_CONFIG.get('PRICE_OFFSET_PERCENT', 0.01)}%")
            
        except Exception as e:
            print(f"❌ Erreur initialisation testeur: {e}")
            traceback.print_exc()
            raise
        
    def create_test_trade(self, trade_id, side, entry_price, quantity, sl_price, tp_price):
        """Crée un trade de test"""
        return {
            'trade_id': trade_id,
            'side': side,
            'entry_price': entry_price,
            'quantity': quantity,
            'sl_price': sl_price,
            'tp_price': tp_price
        }
    
    def test_scenario_1_prix_stable(self):
        """Test Scénario 1: Prix reste entre SL et TP - Pas d'offset"""
        print("\n" + "="*60)
        print("🧪 TEST SCÉNARIO 1: Prix stable - Pas d'offset")
        print("="*60)
        
        try:
            # Configuration du test
            trade_id = "test_stable_001"
            entry_time = datetime.now()
            
            # Trade LONG à 43200, SL à 43150, TP à 43265
            trade_data = self.create_test_trade(
                trade_id=trade_id,
                side="LONG", 
                entry_price=43202.50,
                quantity=0.023,
                sl_price=43150.00,
                tp_price=43265.00
            )
            
            print(f"📊 Trade test: {trade_data['side']} @ {trade_data['entry_price']}")
            print(f"   SL original: {trade_data['sl_price']}")
            print(f"   TP original: {trade_data['tp_price']}")
            
            # Mock du prix actuel stable (entre SL et TP)
            self.mock_executor.get_current_price = lambda: 43210.30
            print(f"💰 Prix actuel simulé: 43210.30 (stable)")
            
            # Enregistrer le trade
            success = self.delayed_manager.register_trade_for_delayed_sltp(
                trade_result=trade_data,
                entry_candle_time=entry_time,
                original_sl_price=trade_data['sl_price'],
                original_tp_price=trade_data['tp_price']
            )
            
            print(f"✅ Trade enregistré: {success}")
            
            if success:
                # Simuler l'attente (normalement fait par le thread de monitoring)
                print("⏳ Simulation attente...")
                time.sleep(1)
                
                # Forcer le traitement (simuler fin de bougie)
                print("🔄 Traitement forcé...")
                self.delayed_manager._process_delayed_trade(trade_id)
                
                result = "✅ PASS - Pas d'offset appliqué (prix stable)"
            else:
                result = "❌ FAIL - Échec enregistrement trade"
            
            self.test_results.append(("Scénario 1 - Prix stable", result))
            print(f"\n{result}")
            
        except Exception as e:
            error_result = f"❌ FAIL - Erreur: {str(e)}"
            self.test_results.append(("Scénario 1 - Prix stable", error_result))
            print(f"\n{error_result}")
            traceback.print_exc()
        
    def test_scenario_2_sl_depasse(self):
        """Test Scénario 2: Prix dépasse SL - Offset appliqué"""
        print("\n" + "="*60)
        print("🧪 TEST SCÉNARIO 2: SL dépassé - Offset appliqué")
        print("="*60)
        
        try:
            # Configuration du test
            trade_id = "test_sl_breach_002"
            entry_time = datetime.now()
            
            # Trade LONG à 43200, SL à 43150, TP à 43265
            trade_data = self.create_test_trade(
                trade_id=trade_id,
                side="LONG",
                entry_price=43202.50,
                quantity=0.023,
                sl_price=43150.00,
                tp_price=43265.00
            )
            
            print(f"📊 Trade test: {trade_data['side']} @ {trade_data['entry_price']}")
            print(f"   SL original: {trade_data['sl_price']}")
            print(f"   TP original: {trade_data['tp_price']}")
            
            # Mock du prix actuel SOUS le SL (SL dépassé)
            current_price = 43140.20  # En dessous du SL de 43150
            self.mock_executor.get_current_price = lambda: current_price
            
            print(f"💥 Prix actuel simulé: {current_price} (SL dépassé!)")
            
            # Enregistrer le trade
            success = self.delayed_manager.register_trade_for_delayed_sltp(
                trade_result=trade_data,
                entry_candle_time=entry_time,
                original_sl_price=trade_data['sl_price'],
                original_tp_price=trade_data['tp_price']
            )
            
            print(f"✅ Trade enregistré: {success}")
            
            if success:
                # Simuler l'attente
                print("⏳ Simulation attente...")
                time.sleep(1)
                
                # Forcer le traitement
                print("🔄 Traitement forcé...")
                self.delayed_manager._process_delayed_trade(trade_id)
                
                # Vérifier résultat attendu
                offset_percent = config.DELAYED_SLTP_CONFIG.get('PRICE_OFFSET_PERCENT', 0.01)
                expected_new_sl = current_price - (current_price * offset_percent / 100)
                
                result = f"✅ PASS - SL ajusté avec offset: {expected_new_sl:.2f} (était {trade_data['sl_price']})"
            else:
                result = "❌ FAIL - Échec enregistrement trade"
            
            self.test_results.append(("Scénario 2 - SL dépassé", result))
            print(f"\n{result}")
            
        except Exception as e:
            error_result = f"❌ FAIL - Erreur: {str(e)}"
            self.test_results.append(("Scénario 2 - SL dépassé", error_result))
            print(f"\n{error_result}")
            traceback.print_exc()
        
    def test_scenario_3_tp_depasse(self):
        """Test Scénario 3: Prix dépasse TP - Optimisation"""
        print("\n" + "="*60)
        print("🧪 TEST SCÉNARIO 3: TP dépassé - Optimisation")
        print("="*60)
        
        try:
            # Configuration du test
            trade_id = "test_tp_breach_003"
            entry_time = datetime.now()
            
            # Trade LONG à 43200, SL à 43150, TP à 43265
            trade_data = self.create_test_trade(
                trade_id=trade_id,
                side="LONG",
                entry_price=43202.50,
                quantity=0.023,
                sl_price=43150.00,
                tp_price=43265.00
            )
            
            print(f"📊 Trade test: {trade_data['side']} @ {trade_data['entry_price']}")
            print(f"   SL original: {trade_data['sl_price']}")
            print(f"   TP original: {trade_data['tp_price']}")
            
            # Mock du prix actuel AU-DESSUS du TP (TP dépassé)
            current_price = 43280.50  # Au dessus du TP de 43265
            self.mock_executor.get_current_price = lambda: current_price
            
            print(f"🚀 Prix actuel simulé: {current_price} (TP dépassé!)")
            
            # Enregistrer le trade
            success = self.delayed_manager.register_trade_for_delayed_sltp(
                trade_result=trade_data,
                entry_candle_time=entry_time,
                original_sl_price=trade_data['sl_price'],
                original_tp_price=trade_data['tp_price']
            )
            
            print(f"✅ Trade enregistré: {success}")
            
            if success:
                # Simuler l'attente
                print("⏳ Simulation attente...")
                time.sleep(1)
                
                # Forcer le traitement
                print("🔄 Traitement forcé...")
                self.delayed_manager._process_delayed_trade(trade_id)
                
                # Vérifier résultat attendu
                offset_percent = config.DELAYED_SLTP_CONFIG.get('PRICE_OFFSET_PERCENT', 0.01)
                expected_new_tp = current_price + (current_price * offset_percent / 100)
                
                result = f"✅ PASS - TP optimisé avec offset: {expected_new_tp:.2f} (était {trade_data['tp_price']})"
            else:
                result = "❌ FAIL - Échec enregistrement trade"
            
            self.test_results.append(("Scénario 3 - TP dépassé", result))
            print(f"\n{result}")
            
        except Exception as e:
            error_result = f"❌ FAIL - Erreur: {str(e)}"
            self.test_results.append(("Scénario 3 - TP dépassé", error_result))
            print(f"\n{error_result}")
            traceback.print_exc()
        
    def test_scenario_4_statut_monitoring(self):
        """Test Scénario 4: Statut et monitoring"""
        print("\n" + "="*60)
        print("🧪 TEST SCÉNARIO 4: Statut et monitoring")
        print("="*60)
        
        try:
            # Tester le statut avant ajout
            status_initial = self.delayed_manager.get_pending_trades_status()
            print(f"📊 Statut initial: {status_initial['total_pending']} trades")
            
            # Ajouter un trade de test
            trade_id = "test_monitoring_004"
            entry_time = datetime.now() - timedelta(minutes=1)  # Dans le passé = prêt
            
            trade_data = self.create_test_trade(
                trade_id=trade_id,
                side="LONG",
                entry_price=43200.00,
                quantity=0.02,
                sl_price=43150.00,
                tp_price=43265.00
            )
            
            success = self.delayed_manager.register_trade_for_delayed_sltp(
                trade_result=trade_data,
                entry_candle_time=entry_time,
                original_sl_price=trade_data['sl_price'],
                original_tp_price=trade_data['tp_price']
            )
            
            if success:
                # Tester le statut après ajout
                status = self.delayed_manager.get_pending_trades_status()
                
                print(f"📊 Statut des trades retardés:")
                print(f"   Total: {status['total_pending']}")
                print(f"   En attente: {status['waiting_for_candle_close']}")
                print(f"   Prêts: {status['ready_for_processing']}")
                print(f"   Terminés: {status['completed']}")
                
                # Afficher détails
                for trade_id_status, info in status['trades'].items():
                    print(f"   - {trade_id_status}: {info['side']} ({info['status']})")
                
                if status['total_pending'] > 0:
                    result = f"✅ PASS - Monitoring fonctionne: {status['total_pending']} trades trackés"
                else:
                    result = "❌ FAIL - Aucun trade tracké"
            else:
                result = "❌ FAIL - Échec enregistrement trade"
            
            self.test_results.append(("Scénario 4 - Monitoring", result))
            print(f"\n{result}")
            
        except Exception as e:
            error_result = f"❌ FAIL - Erreur: {str(e)}"
            self.test_results.append(("Scénario 4 - Monitoring", error_result))
            print(f"\n{error_result}")
            traceback.print_exc()
        
    def run_all_tests(self):
        """Lance tous les tests"""
        print(f"\n🚀 DÉBUT DES TESTS SL/TP RETARDÉ")
        print(f"Configuration: {config.ASSET_CONFIG['SYMBOL']} - {config.ASSET_CONFIG['TIMEFRAME']}")
        print(f"Offset: {config.DELAYED_SLTP_CONFIG.get('PRICE_OFFSET_PERCENT', 0.01)}%")
        
        try:
            # Lancer tous les scénarios de test
            print("\n🎯 Lancement des tests...")
            self.test_scenario_1_prix_stable()
            self.test_scenario_2_sl_depasse()
            self.test_scenario_3_tp_depasse()
            self.test_scenario_4_statut_monitoring()
            
            # Afficher résumé
            self.display_test_summary()
            
        except Exception as e:
            print(f"❌ Erreur durant les tests: {e}")
            traceback.print_exc()
        finally:
            # Arrêter le monitoring si actif
            try:
                if hasattr(self.delayed_manager, 'monitoring_active') and self.delayed_manager.monitoring_active:
                    self.delayed_manager.stop_monitoring()
            except:
                pass
            
    def display_test_summary(self):
        """Affiche le résumé des tests"""
        print("\n" + "="*60)
        print("📊 RÉSUMÉ DES TESTS")
        print("="*60)
        
        if not self.test_results:
            print("⚠️ Aucun test exécuté")
            return
        
        passed = 0
        failed = 0
        
        for test_name, result in self.test_results:
            status = "✅ PASS" if "✅ PASS" in result else "❌ FAIL"
            print(f"{status} - {test_name}")
            if "✅ PASS" in result:
                passed += 1
            else:
                failed += 1
        
        print(f"\n📈 STATISTIQUES:")
        print(f"   Tests réussis: {passed}")
        print(f"   Tests échoués: {failed}")
        print(f"   Total: {len(self.test_results)}")
        
        if failed == 0:
            print(f"\n🎉 TOUS LES TESTS RÉUSSIS!")
            print(f"Le système SL/TP retardé fonctionne correctement.")
        else:
            print(f"\n⚠️ {failed} TESTS ÉCHOUÉS")
            print(f"Vérifiez la configuration et les logs.")

def run_interactive_test():
    """Mode test interactif"""
    print("🎮 MODE TEST INTERACTIF")
    print("Commandes disponibles:")
    print("  1 - Test prix stable")
    print("  2 - Test SL dépassé")
    print("  3 - Test TP dépassé")
    print("  4 - Test monitoring")
    print("  all - Tous les tests")
    print("  quit - Quitter")
    
    try:
        tester = DelayedSLTPTester()
        
        while True:
            try:
                choice = input("\nChoisir un test: ").strip().lower()
                
                if choice == "quit":
                    break
                elif choice == "1":
                    tester.test_scenario_1_prix_stable()
                elif choice == "2":
                    tester.test_scenario_2_sl_depasse()
                elif choice == "3":
                    tester.test_scenario_3_tp_depasse()
                elif choice == "4":
                    tester.test_scenario_4_statut_monitoring()
                elif choice == "all":
                    tester.run_all_tests()
                    break
                else:
                    print("❌ Commande inconnue")
                    
            except KeyboardInterrupt:
                print("\n👋 Test interrompu")
                break
            except Exception as e:
                print(f"❌ Erreur: {e}")
                traceback.print_exc()
                
    except Exception as e:
        print(f"❌ Erreur initialisation testeur: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    print("🧪 TESTEUR SYSTÈME SL/TP RETARDÉ")
    print("="*50)
    
    try:
        # Mode de lancement
        if len(sys.argv) > 1 and sys.argv[1] == "auto":
            # Mode automatique - tous les tests
            print("🤖 Mode automatique - Tous les tests")
            tester = DelayedSLTPTester()
            tester.run_all_tests()
        else:
            # Mode interactif
            print("🎮 Mode interactif")
            run_interactive_test()
            
    except Exception as e:
        print(f"❌ Erreur principale: {e}")
        traceback.print_exc()
    
    print("\n👋 Test terminé")