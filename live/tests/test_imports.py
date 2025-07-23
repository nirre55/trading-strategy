# test_imports.py
import sys
from pathlib import Path

# Test du chemin
current_dir = Path(__file__).parent
backtest_path = current_dir.parent / "backtest"

print(f"Dossier actuel: {current_dir}")
print(f"Chemin backtest: {backtest_path}")
print(f"Fichier indicators existe: {(backtest_path / 'indicators.py').exists()}")
print(f"Fichier signals existe: {(backtest_path / 'signals.py').exists()}")

# Test import
sys.path.insert(0, str(backtest_path))

try:
    from indicators import calculate_rsi, compute_heikin_ashi
    print("✅ Import indicators OK")
except ImportError as e:
    print(f"❌ Erreur import indicators: {e}")

try:
    from signals import rsi_condition, ha_confirmation
    print("✅ Import signals OK")
except ImportError as e:
    print(f"❌ Erreur import signals: {e}")