from dataclasses import dataclass

@dataclass
class TradingConfig:
    SYMBOL: str = "BTCUSDC"
    TIMEFRAME: str = "5m"
    ATR_PERIOD: int = 14
    OFFSET_INIT_PCT: float = 0.001  # 0.1%
    POSITION_SIZE_USDT: float = 2
    LEVERAGE: int = 100
    STOP_LIMIT_OFFSET_MULTIPLIER: float = 0.0001
    MAX_ORDERS_PER_SIDE: int = 5
    RETRY_INTERVAL: int = 5
    MAX_RETRIES: int = 3
    TP_ATR_MULTIPLIER: float = 2.0
    CHECK_INTERVAL: int = 2  # Intervalle de vérification en secondes