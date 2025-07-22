import ccxt
import pandas as pd

# === Paramètres ===
symbol = 'BTC/USDT'
timeframe = '5m'
limit = 500

# === Initialisation Binance Spot ===
binance = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

# === Récupération des données OHLCV ===
def fetch_ohlcv(symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
    ohlcv = binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

# === Calcul des bougies Heikin Ashi ===
def compute_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    ha_df = df.copy()
    ha_df['HA_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    ha_open = [(df['open'].iloc[0] + df['close'].iloc[0]) / 2]
    for i in range(1, len(df)):
        ha_open.append((ha_open[i - 1] + ha_df['HA_close'].iloc[i - 1]) / 2)
    ha_df['HA_open'] = ha_open
    ha_df['HA_high'] = ha_df[['HA_open', 'HA_close', 'high']].max(axis=1)
    ha_df['HA_low'] = ha_df[['HA_open', 'HA_close', 'low']].min(axis=1)
    return ha_df

# === RSI (Wilder's RMA) ===
def calculate_rsi_wilder(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# === Détection des signaux ===
def detect_signals(df: pd.DataFrame):
    signals = []
    pending_long = False
    pending_short = False

    for i in range(1, len(df) - 1):
        row = df.iloc[i]
        next_row = df.iloc[i + 1]
        timestamp = df.index[i + 1]

        # === Étape 1 : détection condition RSI ===
        if (
            row['RSI_HA_5'] < 30 and
            row['RSI_HA_14'] < 30 and
            row['RSI_HA_21'] < 30
        ):
            pending_long = True

        elif (
            row['RSI_HA_5'] > 70 and
            row['RSI_HA_14'] > 70 and
            row['RSI_HA_21'] > 70
        ):
            pending_short = True

        # === Étape 2 : confirmation Heikin Ashi ===
        if pending_long and row['HA_close'] > row['HA_open']:
            entry = next_row['open']
            sl = row['HA_low'] * (1 - 0.001)
            tp = entry + (entry - sl) * 1.2
            signals.append((timestamp, 'LONG', round(entry, 2), round(sl, 2), round(tp, 2)))
            pending_long = False  # reset après signal

        if pending_short and row['HA_close'] < row['HA_open']:
            entry = next_row['open']
            sl = row['HA_high'] * (1 + 0.001)
            tp = entry - (sl - entry) * 1.2
            signals.append((timestamp, 'SHORT', round(entry, 2), round(sl, 2), round(tp, 2)))
            pending_short = False  # reset après signal

    return signals


# === Programme principal ===
def main():
    df = fetch_ohlcv(symbol, timeframe, limit)
    ha_df = compute_heikin_ashi(df)

    # RSI sur Heikin Ashi
    ha_df['RSI_HA_5'] = calculate_rsi_wilder(ha_df['HA_close'], 5).round(2)
    ha_df['RSI_HA_14'] = calculate_rsi_wilder(ha_df['HA_close'], 14).round(2)
    ha_df['RSI_HA_21'] = calculate_rsi_wilder(ha_df['HA_close'], 21).round(2)

    # Recherche des signaux
    signals = detect_signals(ha_df)

    for signal in signals[-10:]:
        timestamp, direction, entry, sl, tp = signal
        print(f"[{timestamp}] SIGNAL {direction} -> Entry: {entry}, SL: {sl}, TP: {tp}")

if __name__ == "__main__":
    main()
