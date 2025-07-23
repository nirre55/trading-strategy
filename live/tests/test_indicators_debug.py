# test_indicators_debug.py
import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Ajout du chemin backtest
backtest_path = Path(__file__).parent.parent / "backtest"
sys.path.insert(0, str(backtest_path))

def test_indicators():
    print("🧪 Test des indicateurs...")
    
    try:
        # Import
        from indicators import (
            calculate_rsi, compute_heikin_ashi, 
            compute_trend_indicators, calculate_mtf_rsi
        )
        print("✅ Import OK")
        
        # Données de test simples
        data = {
            'timestamp': pd.date_range('2025-01-01', periods=100, freq='5min'),
            'open': np.random.uniform(40000, 42000, 100),
            'high': np.random.uniform(41000, 43000, 100),
            'low': np.random.uniform(39000, 41000, 100),
            'close': np.random.uniform(40000, 42000, 100),
            'volume': np.random.uniform(100, 1000, 100)
        }
        
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        print(f"✅ DataFrame créé: {len(df)} lignes")
        
        # Test 1: Trend indicators
        print("🔄 Test trend indicators...")
        df_test = compute_trend_indicators(df.copy(), ema_period=50, slope_lookback=5)
        print(f"✅ EMA calculée: {df_test['EMA'].iloc[-1]:.2f}")
        
        # Test 2: Heikin Ashi
        print("🔄 Test Heikin Ashi...")
        df_test = compute_heikin_ashi(df_test)
        print(f"✅ HA calculé: Close={df_test['HA_close'].iloc[-1]:.2f}")
        
        # Test 3: RSI
        print("🔄 Test RSI...")
        rsi_5 = calculate_rsi(df_test['HA_close'], 5)
        rsi_14 = calculate_rsi(df_test['HA_close'], 14)
        print(f"✅ RSI calculés: RSI5={rsi_5.iloc[-1]:.1f}, RSI14={rsi_14.iloc[-1]:.1f}")
        
        print("🎉 Tous les tests réussis !")
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_indicators()