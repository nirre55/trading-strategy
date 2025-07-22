import pandas as pd

# Bloc de configuration centralisé
CONFIG = {
    # Capital & gestion du risque
    "capital_initial": 1000,
    "risk_par_trade": 10,
    "gain_multiplier": 1.2,

    # Martingale
    "martingale_enabled": True,
    "martingale_type": "normal",   # Options: "normal", "reverse", "none"
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

# Configuration centralisée pour activer/désactiver les filtres
FILTERS = {
    "filter_ha": True,
    "filter_trend": True,
    "filter_mtf_rsi": False
}

# === Charger le fichier CSV ===
def load_csv(filepath):
    df = pd.read_csv(filepath, parse_dates=["timestamp"])
    df.set_index("timestamp", inplace=True)
    return df

def calculate_rsi(series, period):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def compute_heikin_ashi(df):
    ha = df.copy()
    ha['HA_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    ha_open = [(df['open'].iloc[0] + df['close'].iloc[0]) / 2]
    for i in range(1, len(df)):
        ha_open.append((ha_open[i - 1] + ha['HA_close'].iloc[i - 1]) / 2)
    ha['HA_open'] = ha_open
    ha['HA_high'] = ha[['HA_open', 'HA_close', 'high']].max(axis=1)
    ha['HA_low'] = ha[['HA_open', 'HA_close', 'low']].min(axis=1)
    return ha

def rsi_condition(row, direction):
    if direction == 'long':
        return row['RSI_5'] < 30 and row['RSI_14'] < 30 and row['RSI_21'] < 30
    elif direction == 'short':
        return row['RSI_5'] > 70 and row['RSI_14'] > 70 and row['RSI_21'] > 70
    return False

def ha_confirmation(row, direction):
    if direction == 'long':
        return row['HA_close'] > row['HA_open']
    elif direction == 'short':
        return row['HA_close'] < row['HA_open']
    return False

def trend_filter(row, direction):
    if direction == 'long':
        return row['close'] > row['EMA'] and row['EMA_slope'] > 0
    elif direction == 'short':
        return row['close'] < row['EMA'] and row['EMA_slope'] < 0
    return False

def compute_trend_indicators(df, ema_period=200, slope_lookback=5):
    df['EMA'] = df['close'].ewm(span=ema_period, adjust=False).mean()
    df['EMA_slope'] = (df['EMA'] - df['EMA'].shift(slope_lookback)) / slope_lookback
    return df

def calculate_mtf_rsi(df_5m, period=14, higher_tf="15min"):
    df_mtf = df_5m[['close']].resample(higher_tf).agg({'close': 'last'})
    rsi_mtf = calculate_rsi(df_mtf['close'], period)
    rsi_mtf_expanded = rsi_mtf.reindex(df_5m.index, method='ffill')
    return rsi_mtf_expanded

def multi_tf_rsi_filter(row, direction):
    if direction == 'long':
        return row['RSI_mtf'] > 50
    elif direction == 'short':
        return row['RSI_mtf'] < 50
    return False

# FONCTION CORRIGÉE - simulate_trade
def simulate_trade(df, start_index, entry, sl, tp, long=True):
    """
    Simule un trade à partir de start_index
    CORRECTION : Vérification des niveaux SL/TP par rapport au prix d'entrée
    """
    # Vérification de cohérence des niveaux
    if long:
        if sl >= entry:
            print(f"ERREUR LONG: SL ({sl:.2f}) >= Entry ({entry:.2f})")
            return 'error', None
        if tp <= entry:
            print(f"ERREUR LONG: TP ({tp:.2f}) <= Entry ({entry:.2f})")
            return 'error', None
    else:
        if sl <= entry:
            print(f"ERREUR SHORT: SL ({sl:.2f}) <= Entry ({entry:.2f})")
            return 'error', None
        if tp >= entry:
            print(f"ERREUR SHORT: TP ({tp:.2f}) >= Entry ({entry:.2f})")
            return 'error', None
    
    for j in range(start_index + 1, len(df)):
        row = df.iloc[j]
        timestamp_close = df.index[j]
        o, h, l, c = row['open'], row['high'], row['low'], row['close']

        if long:
            # Ordre de priorité : d'abord vérifier le SL, puis le TP
            if l <= sl:
                return 'loss', timestamp_close
            elif h >= tp:
                return 'win', timestamp_close
        else:
            # Pour short : d'abord vérifier le SL, puis le TP
            if h >= sl:
                return 'loss', timestamp_close
            elif l <= tp:
                return 'win', timestamp_close

    return 'open', None

# FONCTION CORRIGÉE - run_backtest
def run_backtest(df):
    trades = []
    logs = []

    capital = CONFIG["capital_initial"]
    size = CONFIG["risk_par_trade"]
    win_streak = 0
    loss_streak = 0
    max_drawdown = 0
    peak_capital = capital

    pending_long = False
    pending_short = False

    for i in range(1, len(df) - 1):
        row = df.iloc[i]
        next_row = df.iloc[i + 1]
        timestamp = df.index[i + 1]

        # Reset des signaux pending si conditions RSI ne sont plus respectées
        if pending_long and not rsi_condition(row, 'long'):
            pending_long = False
        if pending_short and not rsi_condition(row, 'short'):
            pending_short = False

        # Détection des nouveaux signaux RSI
        if rsi_condition(row, 'long') and not pending_long:
            pending_long = True
        elif rsi_condition(row, 'short') and not pending_short:
            pending_short = True

        # EXÉCUTION LONG
        if (
            pending_long
            and (not FILTERS["filter_ha"] or ha_confirmation(row, 'long'))
            and (not FILTERS["filter_trend"] or trend_filter(row, 'long'))
            and (not FILTERS["filter_mtf_rsi"] or multi_tf_rsi_filter(row, 'long'))
        ):
            entry = next_row['open']
            # Utiliser les prix Heikin Ashi pour les niveaux SL/TP (stratégie valide)
            sl = row['HA_low'] * (1 - CONFIG["sl_buffer_pct"])
            tp = entry + (entry - sl) * CONFIG["tp_ratio"]
            
            result, timestamp_close = simulate_trade(df, i + 1, entry, sl, tp, long=True)
            
            if result == 'error':
                pending_long = False
                continue

            pnl = size * CONFIG["gain_multiplier"] if result == 'win' else -size
            capital += pnl
            peak_capital = max(peak_capital, capital)
            max_drawdown = max(max_drawdown, peak_capital - capital)

            # Gestion Martingale
            if result == 'win':
                win_streak += 1
                loss_streak = 0
                if CONFIG["martingale_enabled"] and CONFIG["martingale_type"] == "reverse":
                    size = size * CONFIG["martingale_multiplier"] if win_streak < CONFIG["win_streak_max"] else CONFIG["risk_par_trade"]
                else:
                    size = CONFIG["risk_par_trade"]
            else:
                win_streak = 0
                loss_streak += 1
                if CONFIG["martingale_enabled"] and CONFIG["martingale_type"] == "normal":
                    size *= CONFIG["martingale_multiplier"]
                else:
                    size = CONFIG["risk_par_trade"]

            # CORRECTION: Encoder le résultat correctement
            trades.append('win' if result == 'win' else 'loss')
            logs.append({
                "timestamp": timestamp,
                "direction": "LONG",
                "entry_price": round(entry, 2),
                "sl": round(sl, 2),
                "tp": round(tp, 2),
                "result": result,
                "timestamp_close": timestamp_close,
                "capital": round(capital, 2)
            })
            pending_long = False

        # EXÉCUTION SHORT
        if (
            pending_short
            and (not FILTERS["filter_ha"] or ha_confirmation(row, 'short'))
            and (not FILTERS["filter_trend"] or trend_filter(row, 'short'))
            and (not FILTERS["filter_mtf_rsi"] or multi_tf_rsi_filter(row, 'short'))
        ):
            entry = next_row['open']
            # CORRECTION: Utiliser les prix réels, pas les prix Heikin Ashi pour SL/TP
            sl = row['high'] * (1 + CONFIG["sl_buffer_pct"])  # Utiliser 'high' au lieu de 'HA_high'
            tp = entry - (sl - entry) * CONFIG["tp_ratio"]
            
            result, timestamp_close = simulate_trade(df, i + 1, entry, sl, tp, long=False)
            
            if result == 'error':
                pending_short = False
                continue

            pnl = size * CONFIG["gain_multiplier"] if result == 'win' else -size
            capital += pnl
            peak_capital = max(peak_capital, capital)
            max_drawdown = max(max_drawdown, peak_capital - capital)

            # Gestion Martingale
            if result == 'win':
                win_streak += 1
                loss_streak = 0
                if CONFIG["martingale_enabled"] and CONFIG["martingale_type"] == "reverse":
                    size = size * CONFIG["martingale_multiplier"] if win_streak < CONFIG["win_streak_max"] else CONFIG["risk_par_trade"]
                else:
                    size = CONFIG["risk_par_trade"]
            else:
                win_streak = 0
                loss_streak += 1
                if CONFIG["martingale_enabled"] and CONFIG["martingale_type"] == "normal":
                    size *= CONFIG["martingale_multiplier"]
                else:
                    size = CONFIG["risk_par_trade"]

            # CORRECTION: Encoder le résultat correctement
            trades.append('win' if result == 'win' else 'loss')
            logs.append({
                "timestamp": timestamp,
                "direction": "SHORT",
                "entry_price": round(entry, 2),
                "sl": round(sl, 2),
                "tp": round(tp, 2),
                "result": result,
                "timestamp_close": timestamp_close,
                "capital": round(capital, 2)
            })
            pending_short = False

    return trades, logs, max_drawdown

# FONCTION CORRIGÉE - print_stats
def print_stats(trades, max_drawdown=None):
    total = len(trades)
    # CORRECTION: Compter les chaînes 'win' au lieu des entiers 1
    wins = sum(1 for t in trades if t == 'win')
    losses = total - wins
    winrate = (wins / total * 100) if total > 0 else 0

    max_win_streak = 0
    max_loss_streak = 0
    current_win_streak = 0
    current_loss_streak = 0

    for result in trades:
        if result == 'win':  # CORRECTION: Utiliser 'win' au lieu de 1
            current_win_streak += 1
            current_loss_streak = 0
        else:
            current_loss_streak += 1
            current_win_streak = 0
        max_win_streak = max(max_win_streak, current_win_streak)
        max_loss_streak = max(max_loss_streak, current_loss_streak)

    print(f"📊 Total Trades: {total}")
    print(f"✅ Wins: {wins}")
    print(f"❌ Losses: {losses}")
    print(f"📈 Winrate: {winrate:.2f}%")
    print(f"🔥 Max Win Streak: {max_win_streak}")
    print(f"💥 Max Loss Streak: {max_loss_streak}")
    if max_drawdown is not None:
        print(f"🔻 Max Drawdown: ${max_drawdown:.2f}")

def export_trades_to_csv(logs, filename="trades_result.csv"):
    df = pd.DataFrame(logs)
    df.to_csv(filename, index=False)
    print(f"\n✅ Fichier exporté : {filename}")

def main():
    file_path = r"C:\Users\Oulmi\OneDrive\Bureau\DEV\trading-strategy\backtest\BTCUSDT_5m_2020_1_1_to_2025_7_21.csv"
    df = load_csv(file_path)

    df = compute_trend_indicators(df)
    df = compute_heikin_ashi(df)

    df['RSI_5'] = calculate_rsi(df['HA_close'], CONFIG["rsi_periods"][0]).round(2)
    df['RSI_14'] = calculate_rsi(df['HA_close'], CONFIG["rsi_periods"][1]).round(2)
    df['RSI_21'] = calculate_rsi(df['HA_close'], CONFIG["rsi_periods"][2]).round(2)
    df['RSI_mtf'] = calculate_mtf_rsi(df).round(2)

    df.dropna(inplace=True)

    print("Lancement du backtest...")
    trades, logs, max_drawdown = run_backtest(df)
    print_stats(trades, max_drawdown)

    export_trades_to_csv(logs)

if __name__ == "__main__":
    main()