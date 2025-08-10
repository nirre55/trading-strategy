#!/usr/bin/env python3
"""
Test direct d'un trade avec SL/TP retardé - SANS SIGNAL
Ouvre un trade directement et vérifie que le système fonctionne en 1m
"""
import sys
import os
import time
from datetime import datetime, timedelta

# Ajouter le répertoire du bot au path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from position_manager import PositionManager
from trade_executor import TradeExecutor
from binance_client import BinanceClient
from trading_logger import trading_logger

class DirectTradeTest:
    """Test direct d'un trade avec SL/TP retardé"""
    
    def __init__(self):
        print("🧪 INITIALISATION TEST DIRECT TRADE")
        print("=" * 50)
        
        # Forcer timeframe 1m pour test rapide
        original_timeframe = config.ASSET_CONFIG.get('TIMEFRAME', '5m')
        config.ASSET_CONFIG['TIMEFRAME'] = '1m'
        
        print(f"⏰ Timeframe forcé à: 1m (était {original_timeframe})")
        print(f"🎯 Test sera en temps réel - SL/TP placés après 1 minute")
        
        try:
            # Initialiser les modules de trading
            self.position_manager = PositionManager()
            self.trade_executor = TradeExecutor()
            self.binance_client = BinanceClient()
            
            print("✅ Modules de trading initialisés")
            
            # Vérifier gestionnaire SL/TP retardé
            if hasattr(self.trade_executor, 'delayed_sltp_manager') and self.trade_executor.delayed_sltp_manager:
                print("✅ Gestionnaire SL/TP retardé disponible")
            else:
                print("❌ Gestionnaire SL/TP retardé NON disponible")
                print("Vérifiez que DELAYED_SLTP_CONFIG['ENABLED'] = True")
                return
            
        except Exception as e:
            print(f"❌ Erreur initialisation: {e}")
            raise
    
    def create_test_candles_data(self):
        """Crée des données de bougies de test pour le calcul SL"""
        print("\n📊 Création données de test...")
        
        # Récupérer le prix actuel
        current_price = self.trade_executor.get_current_price()
        if not current_price:
            print("❌ Impossible de récupérer le prix actuel")
            return None
        
        print(f"💰 Prix actuel: {current_price}")
        
        # Créer 10 bougies fictives autour du prix actuel
        candles_data = []
        base_price = current_price
        
        for i in range(10):
            # Variation aléatoire de ±0.1%
            variation = (i % 3 - 1) * 0.001  # -0.1%, 0%, +0.1%
            
            low = base_price * (1 + variation - 0.0005)
            high = base_price * (1 + variation + 0.0005)
            open_price = base_price * (1 + variation * 0.5)
            close_price = base_price * (1 + variation)
            
            candles_data.append({
                'high': high,
                'low': low,
                'open': open_price,
                'close': close_price,
                'timestamp': datetime.now() - timedelta(minutes=10-i)
            })
        
        print(f"✅ {len(candles_data)} bougies de test créées")
        return candles_data
    
    def test_delayed_trade_execution(self, side="LONG"):
        """Test complet d'un trade avec SL/TP retardé"""
        print(f"\n🚀 TEST TRADE {side} AVEC SL/TP RETARDÉ")
        print("=" * 50)
        
        # 1. Préparer les données
        candles_data = self.create_test_candles_data()
        if not candles_data:
            return False
        
        # 2. Timestamp de la bougie d'entrée (maintenant)
        entry_candle_time = datetime.now()
        print(f"⏰ Bougie d'entrée: {entry_candle_time}")
        print(f"🕐 SL/TP attendus à: {entry_candle_time + timedelta(minutes=1)}")
        
        # 3. Signal de test
        test_signal_data = {
            'type': side,
            'valid': True,
            'source': 'TEST_DIRECT',
            'long': {'valid': side == 'LONG', 'reason': 'Test direct'},
            'short': {'valid': side == 'SHORT', 'reason': 'Test direct'}
        }
        
        # 4. Exécuter le trade avec SL/TP retardé
        print(f"\n📋 Exécution trade {side}...")
        
        try:
            trade_result = self.trade_executor.execute_complete_trade_with_delayed_sltp(
                side=side,
                candles_data=candles_data,
                current_candle_time=entry_candle_time,
                signal_data=test_signal_data
            )
            
            if trade_result:
                print(f"✅ Trade créé avec succès!")
                print(f"   ID: {trade_result['trade_id']}")
                print(f"   Prix entrée: {trade_result['entry_price']}")
                print(f"   SL calculé: {trade_result['stop_loss_price']}")
                print(f"   TP calculé: {trade_result['take_profit_price']}")
                print(f"   Mode retardé: {trade_result.get('delayed_sltp', False)}")
                
                return trade_result
            else:
                print("❌ Échec création trade")
                return None
                
        except Exception as e:
            print(f"❌ Erreur exécution trade: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def monitor_delayed_status(self, trade_result, max_wait_minutes=2):
        """Monitor le statut du trade retardé"""
        print(f"\n👁️ MONITORING TRADE RETARDÉ")
        print("=" * 50)
        
        trade_id = trade_result['trade_id']
        start_time = datetime.now()
        
        print(f"🔍 Surveillance du trade: {trade_id}")
        print(f"⏳ Attente maximum: {max_wait_minutes} minutes")
        
        while (datetime.now() - start_time).total_seconds() < (max_wait_minutes * 60):
            try:
                # Vérifier le statut
                if hasattr(self.trade_executor, 'delayed_sltp_manager'):
                    status = self.trade_executor.delayed_sltp_manager.get_pending_trades_status()
                    
                    print(f"\n📊 Statut à {datetime.now().strftime('%H:%M:%S')}:")
                    print(f"   Total trades: {status['total_pending']}")
                    print(f"   En attente: {status['waiting_for_candle_close']}")
                    print(f"   Prêts: {status['ready_for_processing']}")
                    print(f"   Terminés: {status['completed']}")
                    
                    # Vérifier le trade spécifique
                    if trade_id in status['trades']:
                        trade_info = status['trades'][trade_id]
                        print(f"   📍 {trade_id}: {trade_info['status']}")
                        
                        if trade_info['sl_tp_placed']:
                            print(f"✅ SL/TP PLACÉS AVEC SUCCÈS!")
                            return True
                        elif trade_info['status'] == 'ready':
                            print(f"🔄 Trade prêt - Forçage du traitement...")
                            self.trade_executor.force_process_delayed_trade(trade_id)
                    else:
                        print(f"⚠️ Trade {trade_id} non trouvé dans les trades retardés")
                
                # Attendre 10 secondes avant prochaine vérification
                time.sleep(10)
                
            except Exception as e:
                print(f"❌ Erreur monitoring: {e}")
                time.sleep(10)
        
        print(f"⏰ Timeout atteint ({max_wait_minutes} minutes)")
        return False
    
    def cleanup_test_trade(self, trade_result):
        """Nettoie le trade de test"""
        print(f"\n🧹 NETTOYAGE TRADE DE TEST")
        print("=" * 30)
        
        try:
            trade_id = trade_result['trade_id']
            
            # Annuler les ordres SL/TP s'ils existent
            if trade_id in self.trade_executor.active_trades:
                trade_info = self.trade_executor.active_trades[trade_id]
                
                if trade_info.get('stop_loss_order_id'):
                    self.trade_executor.cancel_order(trade_info['stop_loss_order_id'])
                    print(f"🚫 SL annulé: {trade_info['stop_loss_order_id']}")
                
                if trade_info.get('take_profit_order_id'):
                    self.trade_executor.cancel_order(trade_info['take_profit_order_id'])
                    print(f"🚫 TP annulé: {trade_info['take_profit_order_id']}")
                
                # Fermer la position manuellement
                entry_side = trade_info['entry_side']
                close_side = 'SELL' if entry_side == 'BUY' else 'BUY'
                quantity = trade_info['quantity']
                
                print(f"🔄 Fermeture position: {close_side} {quantity}")
                
                # Ordre market pour fermer
                close_order = self.trade_executor.client.futures_create_order(
                    symbol=config.ASSET_CONFIG['SYMBOL'],
                    side=close_side,
                    type='MARKET',
                    quantity=quantity
                )
                
                print(f"✅ Position fermée: {close_order['orderId']}")
                
                # Retirer du tracking
                del self.trade_executor.active_trades[trade_id]
                
            print("✅ Nettoyage terminé")
            
        except Exception as e:
            print(f"⚠️ Erreur nettoyage: {e}")
            print("⚠️ Vérifiez manuellement vos positions sur Binance!")
    
    def run_complete_test(self, side="LONG"):
        """Lance un test complet"""
        print(f"\n🎯 TEST COMPLET - TRADE {side} AVEC SL/TP RETARDÉ")
        print("=" * 60)
        
        # 1. Exécuter le trade
        trade_result = self.test_delayed_trade_execution(side)
        if not trade_result:
            print("❌ Test échoué - Impossible de créer le trade")
            return False
        
        # 2. Surveiller le processus retardé
        success = self.monitor_delayed_status(trade_result, max_wait_minutes=2)
        
        # 3. Nettoyer (IMPORTANT pour éviter positions ouvertes)
        cleanup_choice = input(f"\n🤔 Nettoyer le trade de test? (y/n): ").strip().lower()
        if cleanup_choice == 'y':
            self.cleanup_test_trade(trade_result)
        else:
            print("⚠️ ATTENTION: Trade de test laissé ouvert!")
            print("⚠️ Surveillez manuellement vos positions!")
        
        return success

def run_interactive_test():
    """Mode de test interactif"""
    print("🎮 TEST DIRECT TRADE - MODE INTERACTIF")
    print("=" * 50)
    
    try:
        tester = DirectTradeTest()
        
        while True:
            print("\n🎯 OPTIONS DISPONIBLES:")
            print("  1 - Test LONG avec SL/TP retardé")
            print("  2 - Test SHORT avec SL/TP retardé")
            print("  3 - Vérifier statut trades retardés")
            print("  4 - Test positions actuelles")
            print("  quit - Quitter")
            
            choice = input("\nChoisir une option: ").strip().lower()
            
            if choice == "quit":
                break
            elif choice == "1":
                tester.run_complete_test("LONG")
            elif choice == "2":
                tester.run_complete_test("SHORT")
            elif choice == "3":
                if hasattr(tester.trade_executor, 'delayed_sltp_manager'):
                    status = tester.trade_executor.delayed_sltp_manager.get_pending_trades_status()
                    print(f"\n📊 Statut trades retardés:")
                    print(f"   Total: {status['total_pending']}")
                    for trade_id, info in status['trades'].items():
                        print(f"   - {trade_id}: {info['side']} ({info['status']})")
            elif choice == "4":
                positions = tester.position_manager.get_current_positions()
                print(f"\n📊 Positions actuelles: {len(positions)}")
                for pos in positions:
                    print(f"   {pos['side']}: {pos['size']} @ {pos['entry_price']}")
            else:
                print("❌ Option invalide")
    
    except Exception as e:
        print(f"❌ Erreur test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🧪 TESTEUR DIRECT TRADE SL/TP RETARDÉ")
    print("=" * 50)
    print("⚠️ ATTENTION: Ce test utilise de VRAIS ordres sur Binance!")
    print("⚠️ Assurez-vous d'avoir des fonds et surveillez vos positions!")
    
    confirm = input("\n🤔 Continuer avec le test RÉEL? (y/n): ").strip().lower()
    if confirm != 'y':
        print("👋 Test annulé")
        sys.exit(0)
    
    run_interactive_test()
    print("\n👋 Test terminé")