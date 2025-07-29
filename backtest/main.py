# main.py
"""
Programme principal de backtest
"""
from config import CONFIG, FILTERS
from data_loader import DataLoader
from backtest_engine import run_backtest
from stats import print_stats, export_trades_to_csv, create_performance_report

def main():
    """
    Fonction principale du programme de backtest
    """
    # Configuration du fichier de données
    file_path = r"C:\Users\Oulmi\OneDrive\Bureau\DEV\trading-strategy\backtest\BTCUSDT_1m_2025_7_21_to_2025_7_28.csv"
    
    try:
        print("🚀 Démarrage du backtest...")
        print("=" * 50)
        
        # 1. Chargement et préparation des données
        print("📂 Chargement des données...")
        loader = DataLoader(CONFIG)
        df = loader.load_and_prepare(file_path)
        
        # 2. Validation des données (optionnel)
        validation_report = loader.validate_data(df)
        loader.print_validation_report(validation_report)
        
        # 3. Affichage de la configuration
        print_configuration()
        
        # 4. Lancement du backtest
        print("\n🎯 Lancement du backtest...")
        trades, logs, max_drawdown = run_backtest(df, CONFIG, FILTERS)
        
        # 5. Affichage des résultats
        print("\n📊 RÉSULTATS DU BACKTEST")
        print("=" * 50)
        print_stats(trades, max_drawdown, logs)
        
        # 6. Export des résultats
        if logs:
            export_trades_to_csv(logs)
            create_performance_report(trades, logs, max_drawdown)
        
        print("\n✅ Backtest terminé avec succès !")
        
    except Exception as e:
        print(f"❌ Erreur lors du backtest: {str(e)}")
        import traceback
        traceback.print_exc()

def print_configuration():
    """Affiche la configuration actuelle"""
    print("\n⚙️ CONFIGURATION ACTIVE")
    print("-" * 30)
    print(f"Capital initial: ${CONFIG['capital_initial']}")
    print(f"Risque par trade: ${CONFIG['risk_par_trade']}")
    print(f"Martingale: {CONFIG['martingale_enabled']} ({CONFIG['martingale_type']})")
    print(f"RSI periods: {CONFIG['rsi_periods']}")
    print(f"SL buffer: {CONFIG['sl_buffer_pct']*100}%")
    print(f"TP ratio: {CONFIG['tp_ratio']}")
    
    print("\n🔧 FILTRES ACTIVÉS")
    print("-" * 30)
    active_filters = [name for name, active in FILTERS.items() if active]
    if active_filters:
        for filter_name in active_filters:
            print(f"✅ {filter_name}")
    else:
        print("❌ Aucun filtre activé")

def run_quick_test():
    """
    Lance un test rapide sur un échantillon de données
    """
    print("🧪 Test rapide...")
    
    file_path = r"C:\Users\Oulmi\OneDrive\Bureau\DEV\trading-strategy\backtest\BTCUSDT_5m_2020_1_1_to_2025_7_21.csv"
    
    try:
        loader = DataLoader(CONFIG)
        df = loader.load_and_prepare(file_path)
        
        # Prendre seulement les 1000 premières lignes pour un test rapide
        df_sample = df.head(1000)
        print(f"Test sur {len(df_sample)} lignes (échantillon)")
        
        trades, logs, max_drawdown = run_backtest(df_sample, CONFIG, FILTERS)
        print_stats(trades, max_drawdown, logs)
        
    except Exception as e:
        print(f"❌ Erreur lors du test: {str(e)}")

def run_optimization():
    """
    Lance une optimisation simple des paramètres
    """
    print("🔧 Optimisation des paramètres...")
    
    file_path = r"C:\Users\Oulmi\OneDrive\Bureau\DEV\trading-strategy\backtest\BTCUSDT_5m_2020_1_1_to_2025_7_21.csv"
    
    # Paramètres à tester
    rsi_levels = [
        ([5, 14, 21], [20, 25, 25]),  # RSI periods et seuils long
        ([5, 14, 21], [25, 30, 30]),
        ([5, 14, 21], [30, 35, 35])
    ]
    
    tp_ratios = [1.0, 1.2, 1.5, 2.0]
    
    best_result = None
    best_winrate = 0
    
    try:
        loader = DataLoader(CONFIG)
        df = loader.load_and_prepare(file_path)
        
        # Test rapide sur échantillon
        df_sample = df.head(5000)
        
        for periods, thresholds in rsi_levels:
            for tp_ratio in tp_ratios:
                # Modification temporaire de la config
                test_config = CONFIG.copy()
                test_config['rsi_periods'] = periods
                test_config['tp_ratio'] = tp_ratio
                
                trades, logs, max_drawdown = run_backtest(df_sample, test_config, FILTERS)
                
                if trades:
                    wins = sum(1 for t in trades if t == 'win')
                    winrate = (wins / len(trades)) * 100
                    
                    print(f"RSI {thresholds}, TP {tp_ratio}: {len(trades)} trades, {winrate:.1f}% winrate")
                    
                    if winrate > best_winrate:
                        best_winrate = winrate
                        best_result = (periods, tp_ratio, winrate, len(trades))
        
        if best_result:
            print(f"\n🏆 Meilleur résultat:")
            print(f"RSI periods: {best_result[0]}")
            print(f"TP ratio: {best_result[1]}")
            print(f"Winrate: {best_result[2]:.1f}%")
            print(f"Total trades: {best_result[3]}")
    
    except Exception as e:
        print(f"❌ Erreur lors de l'optimisation: {str(e)}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            run_quick_test()
        elif sys.argv[1] == "optimize":
            run_optimization()
        else:
            print("Usage: python main.py [test|optimize]")
    else:
        main()