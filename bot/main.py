#!/usr/bin/env python3
"""
Point d'entrée principal du bot Heikin Ashi RSI
"""
from trading_bot import HeikinAshiRSIBot

if __name__ == "__main__":
    try:    
        print("🚀 Démarrage du bot Heikin Ashi RSI...")
        bot = HeikinAshiRSIBot()
        bot.start()
        
    except ImportError as e:
        print(f"❌ Erreur d'import: {e}")
        print("Assurez-vous d'avoir installé les dépendances avec: pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ Erreur lors du démarrage: {e}")
    finally:
        print("👋 Bot arrêté")