#!/usr/bin/env python3
"""
Test de validation de la distance SL et du cleanup
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta, timezone
import config
from delayed_sltp_manager import DelayedSLTPManager

class MockExecutor:
    def __init__(self):
        self.position_manager = type('obj', (object,), {
            'format_price': lambda self, x: round(float(x), 3)
        })()
    def get_current_price(self): return 21.550

def test_sl_distance():
    """Test la distance minimale SL"""
    print("🧪 TEST DISTANCE SL")
    print("="*50)
    
    mock = MockExecutor()
    manager = DelayedSLTPManager(mock, None)
    
    # Test 1: SL trop proche (devrait ajuster)
    print("\n📍 Test 1: SL trop proche du prix")
    trade_info = {'original_sl_price': 21.549}  # Seulement 0.001 de différence
    trade_result = {'side': 'LONG', 'entry_price': 21.560}
    
    adjusted = manager._calculate_adjusted_sl_price(trade_info, 21.550, trade_result)
    print(f"   Résultat: {adjusted}")
    
    if adjusted and adjusted < 21.550:
        print("   ✅ SL ajusté correctement")
    else:
        print("   ❌ SL non ajusté!")
    
    # Test 2: SL dépassé (prix < SL pour LONG)
    print("\n📍 Test 2: SL dépassé")
    trade_info = {'original_sl_price': 21.560}  # SL au-dessus du prix actuel!
    
    adjusted = manager._calculate_adjusted_sl_price(trade_info, 21.550, trade_result)
    print(f"   Résultat: {adjusted}")
    
    if adjusted and adjusted < 21.550:
        print("   ✅ SL ajusté avec offset")
    else:
        print("   ❌ SL non ajusté!")

def test_cleanup():
    """Test le cleanup corrigé"""
    print("\n🧪 TEST CLEANUP")
    print("="*50)
    
    mock = MockExecutor()
    manager = DelayedSLTPManager(mock, None)
    
    # Ajouter un trade avec registration_time_utc
    now_utc = datetime.now(timezone.utc)
    old_time = now_utc - timedelta(hours=3)  # 3h dans le passé
    
    manager.pending_trades['test_cleanup'] = {
        'trade_result': {'trade_id': 'test_cleanup'},
        'registration_time_utc': old_time,
        'sl_tp_placed': True,
        'placement_time': old_time
    }
    
    print(f"📍 Trade ajouté avec timestamp {old_time}")
    
    # Tester cleanup
    manager._cleanup_completed_trades()
    
    if 'test_cleanup' not in manager.pending_trades:
        print("✅ Trade nettoyé correctement")
    else:
        print("❌ Trade non nettoyé")

if __name__ == "__main__":
    test_sl_distance()
    test_cleanup()
    print("\n✅ Tests terminés")