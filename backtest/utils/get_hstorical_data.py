import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta

# Configuration
symbol = 'BTC/USDT'
timeframe = '5m'

# Constantes pour les dates (année, mois, jour)
START_YEAR = 2020
START_MONTH = 1
START_DAY = 1
END_YEAR = 2025
END_MONTH = 7
END_DAY = 21

# Création des dates à partir des constantes
start_date = datetime(START_YEAR, START_MONTH, START_DAY)
end_date = datetime(END_YEAR, END_MONTH, END_DAY)

# Conversion au format attendu par l'API
since = ccxt.binance().parse8601(start_date.isoformat() + 'Z')
end_date = ccxt.binance().parse8601(end_date.isoformat() + 'Z')

exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'futures'}
})

all_candles = []

print(f"Downloading candles from {start_date} to {end_date}, please wait...")

while since < end_date:
    try:
        candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1500)
        if not candles:
            break

        all_candles += candles
        since = candles[-1][0] + 1
        print(f"Fetched up to {datetime.utcfromtimestamp(since/1000)}")
        time.sleep(exchange.rateLimit / 1000)
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)

df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

# Sauvegarde dans un fichier avec les dates dans le nom
output_filename = f"{symbol.replace('/', '')}_{timeframe}_{START_YEAR}_{START_MONTH}_{START_DAY}_to_{END_YEAR}_{END_MONTH}_{END_DAY}.csv"
df.to_csv(output_filename, index=False)
print(f"✅ Données enregistrées dans {output_filename}")