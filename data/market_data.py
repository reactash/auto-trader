from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.enums import DataFeed
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from config.settings import settings
from utils.logger import logger

# Alpaca data client (no keys needed for market data)
_data_client = None


def _get_data_client() -> StockHistoricalDataClient:
    global _data_client
    if _data_client is None:
        _data_client = StockHistoricalDataClient(
            settings.ALPACA_API_KEY,
            settings.ALPACA_SECRET_KEY,
        )
    return _data_client


TIMEFRAME_MAP = {
    "1Min": TimeFrame(1, TimeFrameUnit.Minute),
    "5Min": TimeFrame(5, TimeFrameUnit.Minute),
    "15Min": TimeFrame(15, TimeFrameUnit.Minute),
    "1Hour": TimeFrame(1, TimeFrameUnit.Hour),
    "1Day": TimeFrame(1, TimeFrameUnit.Day),
}


def get_historical_bars(
    symbol: str,
    timeframe: str = "1Day",
    days_back: int = 30,
    start: datetime | None = None,
    end: datetime | None = None,
) -> pd.DataFrame:
    """Fetch historical OHLCV bars from Alpaca."""
    client = _get_data_client()

    if start is None:
        start = datetime.now() - timedelta(days=days_back)
    if end is None:
        end = datetime.now()

    tf = TIMEFRAME_MAP.get(timeframe, TimeFrame(1, TimeFrameUnit.Day))

    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=tf,
        start=start,
        end=end,
        feed=DataFeed.IEX,
    )

    try:
        bars = client.get_stock_bars(request)
        df = bars.df
        if isinstance(df.index, pd.MultiIndex):
            df = df.droplevel(0)
        df.index = pd.to_datetime(df.index)
        logger.debug(f"Fetched {len(df)} bars for {symbol} ({timeframe})")
        return df
    except Exception as e:
        logger.error(f"Failed to fetch bars for {symbol}: {e}")
        return pd.DataFrame()


def get_multiple_bars(
    symbols: list[str],
    timeframe: str = "1Day",
    days_back: int = 30,
) -> dict[str, pd.DataFrame]:
    """Fetch historical bars for multiple symbols."""
    client = _get_data_client()
    start = datetime.now() - timedelta(days=days_back)
    tf = TIMEFRAME_MAP.get(timeframe, TimeFrame(1, TimeFrameUnit.Day))

    request = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=tf,
        start=start,
        end=datetime.now(),
        feed=DataFeed.IEX,
    )

    try:
        bars = client.get_stock_bars(request)
        result = {}
        for symbol in symbols:
            try:
                df = bars[symbol]
                df = pd.DataFrame([{
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                    "timestamp": bar.timestamp,
                } for bar in df])
                if not df.empty:
                    df.set_index("timestamp", inplace=True)
                    df.index = pd.to_datetime(df.index)
                result[symbol] = df
            except (KeyError, Exception):
                result[symbol] = pd.DataFrame()
        logger.debug(f"Fetched bars for {len(result)} symbols")
        return result
    except Exception as e:
        logger.error(f"Failed to fetch multiple bars: {e}")
        return {}


def get_latest_quote(symbol: str) -> dict | None:
    """Get the latest quote for a symbol."""
    client = _get_data_client()
    request = StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX)

    try:
        quotes = client.get_stock_latest_quote(request)
        quote = quotes[symbol]
        return {
            "symbol": symbol,
            "ask_price": float(quote.ask_price),
            "bid_price": float(quote.bid_price),
            "ask_size": quote.ask_size,
            "bid_size": quote.bid_size,
            "timestamp": quote.timestamp,
        }
    except Exception as e:
        logger.error(f"Failed to fetch quote for {symbol}: {e}")
        return None


def get_sp500_symbols() -> list[str]:
    """Fetch current S&P 500 symbol list from Wikipedia via pandas."""
    try:
        table = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        df = table[0]
        symbols = df["Symbol"].str.replace(".", "-", regex=False).tolist()
        logger.info(f"Fetched {len(symbols)} S&P 500 symbols")
        return symbols
    except Exception as e:
        logger.error(f"Failed to fetch S&P 500 list: {e}")
        return settings.CUSTOM_SYMBOLS


def get_stock_universe() -> list[str]:
    """Get the stock universe based on settings."""
    if settings.STOCK_UNIVERSE == "sp500":
        return get_sp500_symbols()
    return settings.CUSTOM_SYMBOLS
