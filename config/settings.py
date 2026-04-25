from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Alpaca API
    ALPACA_API_KEY: str = Field(default="", description="Alpaca API key")
    ALPACA_SECRET_KEY: str = Field(default="", description="Alpaca secret key")
    ALPACA_BASE_URL: str = Field(
        default="https://paper-api.alpaca.markets",
        description="Alpaca base URL (paper trading)",
    )

    # Trading parameters
    INITIAL_CAPITAL: float = Field(default=10000.0, description="Starting capital in USD")
    MAX_RISK_PER_TRADE: float = Field(default=0.02, description="Max risk per trade (2%)")
    MAX_DAILY_LOSS: float = Field(default=0.03, description="Max daily loss before stopping (3%)")
    MAX_POSITIONS: int = Field(default=5, description="Max concurrent positions")
    PROFIT_TARGET: float = Field(default=0.02, description="Daily profit target (2%)")
    RISK_REWARD_RATIO: float = Field(default=1.5, description="Minimum risk-reward ratio")
    TRAILING_STOP_ATR_MULTIPLIER: float = Field(default=0.5, description="Trailing stop = 0.5x ATR")

    # Strategy parameters
    ORB_PERIOD_MINUTES: int = Field(default=15, description="Opening range breakout period")
    SCAN_INTERVAL_MINUTES: int = Field(default=5, description="How often to check signals")
    VOLUME_SURGE_THRESHOLD: float = Field(default=1.5, description="Volume must be 1.5x avg")

    # Stock universe
    STOCK_UNIVERSE: str = Field(default="sp500", description="sp500 or custom")
    CUSTOM_SYMBOLS: list[str] = Field(
        default=["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "AMD", "NFLX", "SPY"],
        description="Custom symbol list if STOCK_UNIVERSE=custom",
    )
    MAX_CANDIDATES: int = Field(default=10, description="Max stocks to screen per day")

    # Database
    DB_PATH: str = Field(default="trader.db", description="SQLite database path")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Log level")
    LOG_DIR: str = Field(default="logs", description="Log directory")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
