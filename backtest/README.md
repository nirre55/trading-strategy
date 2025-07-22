# Système de Backtest Trading

Un système de backtest modulaire et extensible pour tester des stratégies de trading sur données historiques.

## 🏗️ Architecture

Le système est divisé en modules spécialisés :

### 📁 Structure des fichiers

```
├── config.py           # Configuration centralisée
├── data_loader.py      # Chargement et validation des données
├── indicators.py       # Calcul des indicateurs techniques
├── signals.py          # Génération des signaux de trading
├── filters.py          # Filtres de validation des trades
├── trade_simulator.py  # Simulation d'exécution des trades
├── backtest_engine.py  # Moteur principal de backtest
├── stats.py           # Calcul et affichage des statistiques
├── main.py            # Programme principal
├── requirements.txt   # Dépendances Python
└── README.md         # Cette documentation
```

## 🚀 Installation

1. Installez les dépendances :

```bash
pip install -r requirements.txt
```

2. Configurez le chemin de vos données dans `main.py`

3. Lancez le backtest :

```bash
python main.py
```

## ⚙️ Configuration

### Paramètres principaux (`config.py`)

```python
CONFIG = {
    # Capital & gestion du risque
    "capital_initial": 1000,
    "risk_par_trade": 10,
    "gain_multiplier": 1.2,

    # Martingale
    "martingale_enabled": True,
    "martingale_type": "normal",   # "normal", "reverse", "none"
    "martingale_multiplier": 2.0,
    "win_streak_max": 5,

    # RSI
    "rsi_periods": [5, 14, 21],
    "rsi_mtf_period": 14,
    "rsi_mtf_tf": "15min",

    # EMA
    "ema_period": 200,
    "ema_slope_lookback": 5,

    # SL/TP
    "sl_buffer_pct": 0.001,
    "tp_ratio": 1.2
}
```

### Filtres (`config.py`)

```python
FILTERS = {
    "filter_ha": True,          # Filtre Heikin Ashi
    "filter_trend": False,      # Filtre de tendance EMA
    "filter_mtf_rsi": False     # Filtre RSI multi-timeframe
}
```

## 📊 Stratégie de Trading

### Signal de base (obligatoire)

- **LONG** : RSI_5 < 30 ET RSI_14 < 30 ET RSI_21 < 30 (surVENTE)
- **SHORT** : RSI_5 > 70 ET RSI_14 > 70 ET RSI_21 > 70 (surACHAT)

### Logique d'attente persistante

1. **Détection RSI** : Quand les 3 RSI sont en surVENTE/surACHAT → signal pending
2. **Attente persistante** : Le signal reste actif même si les valeurs RSI changent
3. **Confirmation HA** : Attendre la prochaine bougie verte (LONG) ou rouge (SHORT) Heikin Ashi
4. **Exécution** : Trade exécuté + reset du signal pending

### Filtres optionnels (pour améliorer le winrate)

1. **Heikin Ashi** : Confirmation de direction (filter_ha)
2. **Tendance EMA** : Prix au-dessus/en-dessous de l'EMA 200 (filter_trend)
3. **RSI Multi-TF** : Confirmation sur timeframe supérieur (filter_mtf_rsi)

Ces filtres s'ajoutent aux conditions de base et permettent d'augmenter le taux de réussite en filtrant les signaux de moins bonne qualité.

### Gestion des positions

- **Stop Loss** : Basé sur HA_low/HA_high + buffer
- **Take Profit** : Ratio configurable du risque
- **Martingale** : Support normal et inverse

## 🎯 Utilisation

### Backtest complet

```bash
python main.py
```

### Test rapide (1000 lignes)

```bash
python main.py test
```

### Optimisation des paramètres

```bash
python main.py optimize
```

## 📈 Sorties

Le système génère :

1. **Statistiques console** : Résultats en temps réel
2. **trades_result.csv** : Détail de tous les trades
3. **performance_report.txt** : Rapport complet

### Métriques calculées

- Nombre total de trades
- Taux de réussite (winrate)
- Séries de gains/pertes maximales
- Drawdown maximum
- Profit total et moyenne par trade
- Ratios de performance (Sharpe, Calmar)

## 🔧 Personnalisation

### Ajouter un nouvel indicateur

Dans `indicators.py` :

```python
def mon_indicateur(df, period=20):
    return df['close'].rolling(period).mean()

# Dans add_all_indicators()
df['MON_INDIC'] = mon_indicateur(df)
```

### Ajouter un nouveau filtre

Dans `filters.py` :

```python
@staticmethod
def mon_filtre(row, direction):
    if direction == 'long':
        return row['MON_INDIC'] > row['close']
    return row['MON_INDIC'] < row['close']
```

### Modifier la logique de signal

Dans `signals.py`, modifiez `rsi_condition()` ou ajoutez de nouvelles conditions.

## 📋 Format des données

Le fichier CSV doit contenir :

```
timestamp,open,high,low,close,volume
2020-01-01 00:00:00,7200.0,7250.0,7180.0,7230.0,1000.0
```

- **timestamp** : Date/heure au format ISO
- **open, high, low, close** : Prix OHLC
- **volume** : Volume (optionnel)

## ⚠️ Notes importantes

1. **Données réalistes** : Utilisez des données de qualité avec spreads réels
2. **Slippage** : Le système ne simule pas le slippage
3. **Frais** : Les frais de transaction ne sont pas inclus
4. **Liquidité** : Assume une liquidité parfaite

## 🐛 Debugging

Pour déboguer :

1. Activez les prints dans `trade_simulator.py`
2. Réduisez l'échantillon de données
3. Vérifiez la cohérence des niveaux SL/TP
4. Validez les données avec `DataLoader.validate_data()`

## 🤝 Contribution

Pour contribuer :

1. Forkez le projet
2. Créez une branche feature
3. Ajoutez des tests
4. Soumettez une pull request
