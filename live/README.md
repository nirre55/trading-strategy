# 🤖 Trading Bot Live - Guide d'utilisation

Un système de trading automatisé basé sur votre stratégie RSI + Heikin Ashi validée en backtest.

## ⚠️ AVERTISSEMENTS IMPORTANTS

🚨 **RISQUES FINANCIERS RÉELS**

- Ce bot trade avec de l'argent réel
- Des pertes totales sont possibles
- Surveillez constamment les performances
- Commencez TOUJOURS par le testnet

🛡️ **SÉCURITÉ**

- Ne jamais laisser tourner sans surveillance
- Vérifiez les limites de risque
- Testez d'abord sur testnet pendant des semaines
- Gardez des positions petites au début

## 📁 Structure du Projet

```
live_trading/
├── config_live.py          # Configuration principale
├── binance_client.py        # Client API Binance
├── data_manager.py          # Données temps réel
├── signal_detector.py       # Détection signaux
├── risk_manager.py          # Gestion du risque
├── order_manager.py         # Gestion des ordres
├── monitoring.py            # Surveillance & notifications
├── live_engine.py          # Moteur principal
├── main_live.py            # Point d'entrée
└── README_LIVE.md          # Ce guide
```

## 🚀 Installation

### 1. Prérequis

```bash
pip install python-binance websocket-client requests pandas numpy
```

### 2. Configuration des variables d'environnement

Créez un fichier `.env` ou définissez les variables :

```bash
# API Binance
export BINANCE_API_KEY="your_api_key_here"
export BINANCE_API_SECRET="your_api_secret_here"

# Telegram (optionnel)
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"

# Discord (optionnel)
export DISCORD_WEBHOOK="your_webhook_url"

# Email (optionnel)
export EMAIL_USER="your_email@gmail.com"
export EMAIL_PASSWORD="your_app_password"
export EMAIL_TO="destination@gmail.com"
```

### 3. Configuration Binance API

1. Connectez-vous à Binance
2. Allez dans **Account > API Management**
3. Créez une nouvelle API Key
4. **IMPORTANT** : Activez seulement **Futures Trading**
5. **NE PAS** activer **Enable Withdrawals**
6. Configurez les restrictions IP si possible

## ⚙️ Configuration

Modifiez `config_live.py` selon vos besoins :

### Configuration de base

```python
TRADING_CONFIG = {
    "symbol": "BTCUSDT",                 # Paire à trader
    "max_balance_risk": 0.02,            # 2% du solde max par trade
    "min_position_size": 10,             # Position min en USDT
    "max_position_size": 100,            # Position max en USDT
    "tp_ratio": 0.5,                     # Ratio TP/SL de votre backtest
}
```

### Filtres (reprend votre config backtest)

```python
FILTERS_CONFIG = {
    "filter_ha": True,                   # Heikin Ashi
    "filter_trend": False,               # Tendance EMA
    "filter_mtf_rsi": True,             # RSI multi-timeframe
}
```

### Limites de sécurité

```python
SAFETY_LIMITS = {
    "max_daily_trades": 50,              # Max trades par jour
    "max_daily_loss": 100,               # Max perte en USDT/jour
    "max_consecutive_losses": 5,         # Max pertes consécutives
    "emergency_stop_loss": 500,          # Arrêt total du bot
}
```

## 🎯 Modes d'utilisation

### Mode Testnet (RECOMMANDÉ pour débuter)

```bash
python main_live.py --testnet
```

### Mode Surveillance (sans trading)

```bash
python main_live.py
# Choisir "no" pour auto trading
```

### Mode Trading Automatique

```bash
python main_live.py --auto-trade
# ⚠️ ARGENT RÉEL EN JEU !
```

## 🎮 Commandes Interactives

Une fois le bot lancé, utilisez ces commandes :

```
> status    # Statut général du bot
> trades    # Liste des trades actifs
> stats     # Statistiques de performance
> close     # Fermer un trade manuellement
> emergency # Override d'urgence
> reset     # Reset signaux pending
> stop      # Arrêter le bot
> help      # Aide
```

## 📊 Surveillance

### Notifications Telegram

1. Créez un bot avec @BotFather
2. Récupérez le token
3. Démarrez une conversation et récupérez votre chat_id
4. Configurez dans les variables d'environnement

### Tableaux de bord

Le bot affiche en temps réel :

- 💰 Balance et PnL
- 📊 Trades actifs
- 🔧 Santé des connexions
- ⚠️ Alertes de risque

## 🛡️ Sécurité & Bonnes Pratiques

### Phase de Test (OBLIGATOIRE)

1. **Semaine 1-2** : Testnet uniquement
2. **Semaine 3-4** : Mode surveillance sur live
3. **Semaine 5+** : Trading avec micro-positions ($10-20)

### Surveillance Continue

- ✅ Vérifiez le bot toutes les heures
- ✅ Surveillez les notifications Telegram
- ✅ Vérifiez la balance régulièrement
- ✅ Analysez les performances quotidiennes

### Limites Recommandées (Début)

```python
# Configuration conservative pour débuter
TRADING_CONFIG = {
    "max_balance_risk": 0.01,      # 1% max par trade
    "min_position_size": 10,       # 10 USDT min
    "max_position_size": 50,       # 50 USDT max
}

SAFETY_LIMITS = {
    "max_daily_trades": 10,        # 10 trades max/jour
    "max_daily_loss": 50,          # 50 USDT max perte/jour
    "max_consecutive_losses": 3,   # 3 pertes consécutives max
}
```

## 🔧 Dépannage

### Erreurs Courantes

#### "API Key invalide"

- Vérifiez les variables d'environnement
- Vérifiez les permissions Futures Trading
- Testez d'abord sur testnet

#### "Insufficient balance"

- Vérifiez le solde du compte
- Réduisez la taille des positions
- Vérifiez les frais disponibles

#### "WebSocket déconnecté"

- Problème réseau temporaire
- Le bot tente la reconnexion automatique
- Redémarrez si le problème persiste

### Logs et Debugging

```bash
# Logs détaillés
tail -f logs/live_bot_*.log

# Mode debug
# Modifiez ENVIRONMENT["log_level"] = "DEBUG" dans config_live.py
```

## 📈 Optimisation des Performances

### Ajustement des Paramètres

Basé sur vos résultats live, ajustez :

1. **TP Ratio** : Si trop de SL touchés, augmentez le tp_ratio
2. **Filtres** : Si trop de faux signaux, activez plus de filtres
3. **Position Size** : Augmentez progressivement selon les résultats

### Métriques à Surveiller

- **Winrate** : Doit rester proche de votre backtest
- **Profit Factor** : Gains moyens / Pertes moyennes
- **Drawdown** : Perte maximale depuis un pic
- **Sharpe Ratio** : Rendement ajusté du risque

## 🆘 Situations d'Urgence

### Arrêt d'Urgence Automatique

Le bot s'arrête automatiquement si :

- Perte totale > limite définie
- Connexion API perdue
- Trop de pertes consécutives

### Arrêt Manuel

```bash
# Dans l'interface interactive
> stop

# Ou Ctrl+C dans le terminal
```

### Override d'Urgence

Si le bot est bloqué en mode urgence :

```bash
> emergency
# Saisissez une raison valide
```

## 📞 Support et Communauté

### En cas de Problème

1. Consultez les logs en détail
2. Vérifiez la configuration
3. Testez sur testnet d'abord
4. Commencez avec des positions très petites

### Améliorations Futures

- Support multi-paires
- Interface web
- Backtesting en temps réel
- Machine learning pour l'optimisation

## ⚖️ Avertissement Légal

Ce logiciel est fourni "tel quel" sans garantie. Le trading automatisé comporte des risques financiers importants. L'utilisateur est seul responsable de ses décisions de trading et de ses pertes potentielles.

---

🎯 **Commencez TOUJOURS par le testnet et surveillez constamment !**
