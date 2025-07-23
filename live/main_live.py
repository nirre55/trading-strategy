# main_live.py
"""
Point d'entrée principal pour le trading bot live
"""
import os
import sys
import logging
import time
import argparse
from datetime import datetime
from pathlib import Path

# Ajout du chemin des modules
sys.path.append(str(Path(__file__).parent))

from config_live import (
    validate_config, ENVIRONMENT, LOGGING_CONFIG,
    API_CONFIG, TRADING_CONFIG, FILTERS_CONFIG
)
from live_engine import LiveTradingEngine, create_and_run_engine

def setup_logging():
    """Configure le système de logging"""
    # Création du dossier logs
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Configuration du logger
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Logger racine
    logging.basicConfig(
        level=getattr(logging, ENVIRONMENT["log_level"]),
        format=log_format,
        handlers=[]
    )
    
    # Handler pour fichier
    if LOGGING_CONFIG["log_to_file"]:
        file_handler = logging.FileHandler(
            logs_dir / LOGGING_CONFIG["log_filename"],
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(file_handler)
    
    # Handler pour console
    if LOGGING_CONFIG["log_to_console"]:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(console_handler)
    
    # Réduction des logs externes
    logging.getLogger('websocket').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)

def check_environment():
    """Vérifie l'environnement et les prérequis"""
    logger = logging.getLogger(__name__)
    
    # Validation de la configuration
    config_errors = validate_config()
    if config_errors:
        logger.error("❌ Erreurs de configuration:")
        for error in config_errors:
            logger.error(f"  - {error}")
        return False
    
    # Vérification du mode testnet
    if not API_CONFIG["testnet"]:
        logger.warning("⚠️ MODE LIVE ACTIVÉ - ARGENT RÉEL EN JEU !")
        response = input("Confirmer le trading en mode LIVE (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Arrêt par l'utilisateur")
            return False
    else:
        logger.info("🧪 Mode TESTNET activé")
    
    # Vérification du mode auto trading
    if ENVIRONMENT["auto_trade"]:
        logger.warning("🤖 MODE AUTO TRADING ACTIVÉ")
        response = input("Confirmer le trading automatique (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Passage en mode surveillance seulement")
            ENVIRONMENT["auto_trade"] = False
    else:
        logger.info("👁️ Mode surveillance seulement")
    
    return True

def print_startup_banner():
    """Affiche la bannière de démarrage"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                      TRADING BOT LIVE                       ║
║                                                              ║
║  ⚠️  ATTENTION: Trading automatisé avec argent réel        ║
║  📊 Surveillez constamment les performances                 ║
║  🛑 Prêt à arrêter manuellement si nécessaire              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def print_config_summary():
    """Affiche un résumé de la configuration"""
    logger = logging.getLogger(__name__)
    
    logger.info("📋 CONFIGURATION ACTIVE:")
    logger.info(f"  Symbole: {TRADING_CONFIG['symbol']}")
    logger.info(f"  Timeframe: {TRADING_CONFIG['timeframe']}")
    logger.info(f"  Risque max: {TRADING_CONFIG['max_balance_risk']*100}%")
    logger.info(f"  Position min/max: {TRADING_CONFIG['min_position_size']}/{TRADING_CONFIG['max_position_size']} USDT")
    logger.info(f"  TP Ratio: {TRADING_CONFIG['tp_ratio']}")
    
    logger.info("🔧 FILTRES ACTIVÉS:")
    active_filters = [name for name, active in FILTERS_CONFIG.items() if active]
    for filter_name in active_filters:
        logger.info(f"  ✅ {filter_name}")

def interactive_mode():
    """Mode interactif pour contrôler le bot"""
    logger = logging.getLogger(__name__)
    
    print("\n" + "="*60)
    print("MODE INTERACTIF - Commandes disponibles:")
    print("  status   - Afficher le statut")
    print("  trades   - Lister les trades actifs")
    print("  stats    - Statistiques de performance")
    print("  close    - Fermer un trade manuellement")
    print("  emergency- Override d'urgence")
    print("  reset    - Reset signaux pending")
    print("  stop     - Arrêter le bot")
    print("  help     - Afficher cette aide")
    print("="*60)
    
    return True

def run_interactive_session(engine: LiveTradingEngine):
    """Lance une session interactive pour contrôler le bot"""
    logger = logging.getLogger(__name__)
    
    try:
        while engine.running:
            try:
                command = input("\n> ").strip().lower()
                
                if command == "status":
                    print(engine.get_status_report())
                
                elif command == "trades":
                    summary = engine.order_manager.get_active_trades_summary()
                    print(f"Trades actifs: {summary}")
                
                elif command == "stats":
                    perf = engine.order_manager.get_performance_stats()
                    print(f"Performance: {perf}")
                
                elif command == "close":
                    trade_id = input("ID du trade à fermer: ").strip()
                    if engine.manual_close_trade(trade_id):
                        print(f"✅ Trade {trade_id} fermé")
                    else:
                        print(f"❌ Impossible de fermer {trade_id}")
                
                elif command == "emergency":
                    reason = input("Raison de l'override: ").strip()
                    if engine.manual_override_emergency(reason):
                        print("✅ Override d'urgence activé")
                    else:
                        print("❌ Pas en mode d'urgence")
                
                elif command == "reset":
                    engine.manual_signal_reset()
                    print("✅ Signaux réinitialisés")
                
                elif command == "stop":
                    confirm = input("Confirmer l'arrêt (yes/no): ")
                    if confirm.lower() == 'yes':
                        engine.stop("Arrêt manuel")
                        break
                
                elif command == "help":
                    interactive_mode()
                
                elif command == "":
                    continue
                
                else:
                    print(f"Commande inconnue: {command}")
                    print("Tapez 'help' pour l'aide")
            
            except KeyboardInterrupt:
                print("\nArrêt par Ctrl+C...")
                engine.stop("Interruption clavier")
                break
            
            except EOFError:
                print("\nFin de session")
                engine.stop("Fin de session")
                break
    
    except Exception as e:
        logger.error(f"❌ Erreur session interactive: {e}")
        engine.stop("Erreur session interactive")

def main():
    """Fonction principale"""
    # Configuration des arguments
    parser = argparse.ArgumentParser(description="Trading Bot Live")
    parser.add_argument('--no-interactive', action='store_true', 
                       help='Mode non-interactif')
    parser.add_argument('--auto-trade', action='store_true',
                       help='Force le mode auto trading')
    parser.add_argument('--testnet', action='store_true',
                       help='Force le mode testnet')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Bannière de démarrage
        print_startup_banner()
        
        # Override des configs via args
        if args.auto_trade:
            ENVIRONMENT["auto_trade"] = True
        if args.testnet:
            API_CONFIG["testnet"] = True
        
        # Vérifications d'environnement
        if not check_environment():
            sys.exit(1)
        
        # Affichage de la config
        print_config_summary()
        
        # Création et démarrage du moteur
        logger.info("🚀 Création du moteur de trading...")
        engine = create_and_run_engine()
        
        if not engine:
            logger.error("❌ Échec de création du moteur")
            sys.exit(1)
        
        logger.info("✅ Bot démarré avec succès !")
        
        # Mode interactif ou autonome
        if not args.no_interactive:
            interactive_mode()
            run_interactive_session(engine)
        else:
            logger.info("Mode autonome - Ctrl+C pour arrêter")
            try:
                while engine.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Arrêt par Ctrl+C")
                engine.stop("Interruption clavier")
    
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        sys.exit(1)
    
    finally:
        logger.info("👋 Arrêt du programme")

if __name__ == "__main__":
    main()