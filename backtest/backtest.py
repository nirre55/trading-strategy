import pandas as pd
from datetime import datetime


tp_ratio = 1.2 # Ratio pour le Take Profit

# === Charger le fichier CSV ===
def load_csv(filepath):
    df = pd.read_csv(filepath, parse_dates=["timestamp"])
    df.set_index("timestamp", inplace=True)
    return df

# === Export CSV des trades ===
def export_trades_to_csv(trade_logs, filename="C:\\Users\\Oulmi\\OneDrive\\Bureau\\DEV\\trading-strategy\\backtest\\trades_result.csv"):
    df = pd.DataFrame(trade_logs)
    df.to_csv(filename, index=False)
    print(f"\n✅ Fichier exporté : {filename}")

# === Heikin Ashi ===
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

# === RSI (Wilder's RMA) ===
def calculate_rsi(series, period):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# === Simulation de trade jusqu’à TP ou SL ===
def simulate_trade(df, start_index, entry, sl, tp, long=True):
    for j in range(start_index + 1, len(df)):
        row = df.iloc[j]
        timestamp_close = df.index[j]
        low = row['low']
        high = row['high']
        if long:
            if low <= sl:
                return 'loss', timestamp_close
            elif high >= tp:
                return 'win', timestamp_close
        else:
            if high >= sl:
                return 'loss', timestamp_close
            elif low <= tp:
                return 'win', timestamp_close
    return 'open', None  # jamais fermé


# === Backtest logique avec log de trades ===
def run_backtest(df):
    trades = []
    logs = []
    pending_long = False
    pending_short = False

    for i in range(1, len(df) - 1):
        row = df.iloc[i]
        next_row = df.iloc[i + 1]
        timestamp = df.index[i + 1]

        if row['RSI_5'] < 30 and row['RSI_14'] < 30 and row['RSI_21'] < 30:
            pending_long = True

        elif row['RSI_5'] > 70 and row['RSI_14'] > 70 and row['RSI_21'] > 70:
            pending_short = True

        if pending_long and row['HA_close'] > row['HA_open']:
            entry = next_row['open']
            sl = row['HA_low'] * (1 - 0.001)
            tp = entry + (entry - sl) * 1.2
            result, timestamp_close = simulate_trade(df, i + 1, entry, sl, tp, long=True)
            trades.append(result)
            logs.append({
                "timestamp": timestamp,
                "direction": "LONG",
                "entry_price": round(entry, 2),
                "sl": round(sl, 2),
                "tp": round(tp, 2),
                "result": result,
                "timestamp_close": timestamp_close
            })
            pending_long = False

        if pending_short and row['HA_close'] < row['HA_open']:
            entry = next_row['open']
            sl = row['HA_high'] * (1 + 0.001)
            tp = entry - (sl - entry) * 1.2
            result, timestamp_close = simulate_trade(df, i + 1, entry, sl, tp, long=False)
            trades.append(result)
            logs.append({
                "timestamp": timestamp,
                "direction": "SHORT",
                "entry_price": round(entry, 2),
                "sl": round(sl, 2),
                "tp": round(tp, 2),
                "result": result,
                "timestamp_close": timestamp_close
            })
            pending_short = False

    return trades, logs



# === Statistiques ===
def print_stats(trades):
    closed_trades = [t for t in trades if t in ('win', 'loss')]
    wins = closed_trades.count('win')
    losses = closed_trades.count('loss')
    total = len(closed_trades)
    winrate = (wins / total * 100) if total > 0 else 0

    max_win_streak = max_loss_streak = 0
    current_win = current_loss = 0
    for t in closed_trades:
        if t == 'win':
            current_win += 1
            current_loss = 0
        else:
            current_loss += 1
            current_win = 0
        max_win_streak = max(max_win_streak, current_win)
        max_loss_streak = max(max_loss_streak, current_loss)

    print("\n=== Résultats Backtest ===")
    print(f"Total Trades   : {total}")
    print(f"Wins           : {wins}")
    print(f"Losses         : {losses}")
    print(f"Winrate (%)    : {winrate:.2f}")
    print(f"Max Win Streak : {max_win_streak}")
    print(f"Max Loss Streak: {max_loss_streak}")

def main():
    file_path = r"C:\Users\Oulmi\OneDrive\Bureau\DEV\trading-strategy\backtest\BTCUSDT_5m_2025_6_30_to_2025_7_21.csv"
    df = load_csv(file_path)
    df = compute_heikin_ashi(df)
    df['RSI_5'] = calculate_rsi(df['HA_close'], 5).round(2)
    df['RSI_14'] = calculate_rsi(df['HA_close'], 14).round(2)
    df['RSI_21'] = calculate_rsi(df['HA_close'], 21).round(2)
    df.dropna(inplace=True)

    print("Lancement du backtest...")
    trades, logs = run_backtest(df)
    print_stats(trades)
    export_trades_to_csv(logs)


if __name__ == "__main__":
    main()
