# Bot Heikin Ashi RSI - Binance Futures

Ce bot se connecte aux WebSockets de Binance Futures pour analyser en temps réel les bougies Heikin Ashi et calculer les RSI avec différentes périodes.

## 🚀 Fonctionnalités

- ✅ Connexion WebSocket temps réel aux données Binance Futures
- ✅ Calcul des bougies Heikin Ashi
- ✅ Calcul des RSI sur multiple périodes (5, 14, 21 par défaut)
- ✅ Affichage coloré des résultats dans la console
- ✅ Configuration flexible via fichier config
- ✅ Architecture modulaire et extensible
- ✅ Gestion propre des erreurs et arrêt gracieux

## 📁 Structure du projet

```
├── main.py              # Point d'entrée principal
├── config.py            # Configuration (symbole, timeframe, périodes RSI)
├── trading_bot.py       # Bot principal
├── websocket_handler.py # Gestionnaire WebSocket Binance
├── binance_client.py    # Client API Binance
├── indicators.py        # Calculs des indicateurs (Heikin Ashi, RSI)
├── requirements.txt     # Dépendances Python
└── README.md           # Cette documentation
```

## 🛠️ Installation

1. **Cloner ou télécharger les fichiers**

2. **Installer les dépendances**

```bash
pip install -r requirements.txt
```

3. **Configurer le bot**
   Modifiez le fichier `config.py` selon vos besoins :

```python
SYMBOL = "BTCUSDT"        # Symbole à analyser
TIMEFRAME = "1m"          # Timeframe des bougies
RSI_PERIODS = [5, 14, 21] # Périodes des RSI
```

## 🎯 Utilisation

**Démarrer le bot :**

```bash
python main.py
```

**Arrêter le bot :**
Appuyez sur `Ctrl+C` pour un arrêt propre.

## 📊 Affichage des résultats

À chaque fermeture de bougie, le bot affiche :

```
============================================================
[2024-01-28 15:30:00] BTCUSDT - 1m
============================================================
Heikin Ashi:
  Open:  43250.500000
  High:  43275.800000
  Low:   43240.200000
  Close: 43260.750000
  Couleur: GREEN

RSI sur Heikin Ashi:
  RSI_5: 65.23
  RSI_14: 58.47
  RSI_21: 55.12
```

## 🎨 Code couleur

- **🟢 Vert** : Bougie haussière, RSI en survente (≤30)
- **🔴 Rouge** : Bougie baissière, RSI en surachat (≥70)
- **🟡 Jaune** : Bougie doji, RSI neutre

## ⚙️ Configuration avancée

### Timeframes supportés

- `1m`, `3m`, `5m`, `15m`, `30m`
- `1h`, `2h`, `4h`, `6h`, `8h`, `12h`
- `1d`, `3d`, `1w`, `1M`

### Paramètres du fichier config.py

```python
# Symbole et timeframe
SYMBOL = "BTCUSDT"           # Paire à analyser
TIMEFRAME = "1m"             # Intervalle des bougies

# Périodes RSI
RSI_PERIODS = [5, 14, 21]    # Périodes pour le calcul des RSI

# Données historiques
INITIAL_KLINES_LIMIT = 500   # Nombre de bougies historiques

# Debug
SHOW_DEBUG = False           # Affichage des messages de débogage
```

## 🔧 Fonctions principales

### Calcul Heikin Ashi

```python
def compute_heikin_ashi(df):
    """Calcule les valeurs Heikin Ashi"""
    # Votre implémentation fournie
```

### Calcul RSI

```python
def calculate_rsi(series, period):
    """Calcule le RSI pour une série de prix donnée"""
    # Votre implémentation fournie avec EMA
```

## 📈 Exemple de sortie temps réel

Le bot affiche en continu les mises à jour des indicateurs :

- Prix Heikin Ashi (Open, High, Low, Close)
- Couleur de la bougie fermée
- Valeurs RSI pour chaque période configurée
- Codes couleur selon les niveaux de surachat/survente

## ⚠️ Notes importantes

- Le bot fonctionne uniquement sur les **Binance Futures**
- Aucune API key requise (données publiques uniquement)
- Les calculs se basent sur les bougies **fermées** uniquement
- Optimisé pour une utilisation mémoire efficace

## 🛟 Dépannage

**Erreur de connexion WebSocket :**

- Vérifiez votre connexion internet
- Le symbole doit exister sur Binance Futures

**Import Error :**

- Installez les dépendances : `pip install -r requirements.txt`

**Données manquantes :**

- Augmentez `INITIAL_KLINES_LIMIT` dans config.py
