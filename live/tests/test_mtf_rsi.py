import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import pandas as pd
import numpy as np
from data_manager import RealTimeDataManager

def test_mtf_rsi():
    """Test du nouveau RSI MTF"""
    print("🧪 Test RSI Multi-Timeframe...")
    
    # Données de test (100 bougies 5min)
    dates = pd.date_range('2025-01-01 10:00', periods=100, freq='5min')
    test_data = pd.DataFrame({
        'timestamp': dates,
        'open': np.random.uniform(40000, 42000, 100),
        'high': np.random.uniform(41000, 43000, 100), 
        'low': np.random.uniform(39000, 41000, 100),
        'close': np.random.uniform(40000, 42000, 100),
        'volume': np.random.uniform(100, 1000, 100)
    })
    test_data.set_index('timestamp', inplace=True)
    
    # Test du calcul
    class TestDataManager(RealTimeDataManager):
        def __init__(self):
            pass
    
    dm = TestDataManager()
    
    try:
        rsi_mtf = dm._calculate_mtf_rsi_live(test_data, 14)
        print(f"✅ RSI MTF calculé: {len(rsi_mtf)} valeurs")
        print(f"✅ Dernière valeur: {rsi_mtf.iloc[-1]:.1f}")
        print(f"✅ Première valeur: {rsi_mtf.iloc[50]:.1f}")  # Éviter les NaN du début
        
        # Vérification forward fill
        unique_values = rsi_mtf.dropna().nunique()
        total_values = len(rsi_mtf.dropna())
        print(f"✅ Valeurs uniques: {unique_values}/{total_values} (normal si < 50%)")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_mtf_rsi()
    print("🎉 Test réussi !" if success else "❌ Test échoué")