import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD, EMAIndicator, SMAIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import VolumeWeightedAveragePrice

from utils.logger import logger


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all technical indicators to a DataFrame with OHLCV columns."""
    if df.empty:
        return df

    df = df.copy()

    # Ensure column names are lowercase
    df.columns = [c.lower() for c in df.columns]

    # RSI (14)
    rsi = RSIIndicator(close=df["close"], window=14)
    df["rsi"] = rsi.rsi()

    # MACD
    macd = MACD(close=df["close"])
    df["MACD_12_26_9"] = macd.macd()
    df["MACDs_12_26_9"] = macd.macd_signal()
    df["MACDh_12_26_9"] = macd.macd_diff()

    # EMA (9 and 21)
    df["ema_9"] = EMAIndicator(close=df["close"], window=9).ema_indicator()
    df["ema_21"] = EMAIndicator(close=df["close"], window=21).ema_indicator()

    # VWAP (requires high, low, close, volume)
    if all(col in df.columns for col in ["high", "low", "close", "volume"]):
        try:
            vwap = VolumeWeightedAveragePrice(
                high=df["high"], low=df["low"], close=df["close"], volume=df["volume"]
            )
            df["vwap"] = vwap.volume_weighted_average_price()
        except Exception:
            pass

    # ATR (14)
    try:
        atr = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=14)
        df["atr"] = atr.average_true_range()
    except Exception:
        pass

    # Bollinger Bands
    try:
        bb = BollingerBands(close=df["close"], window=20)
        df["BBL_20_2.0"] = bb.bollinger_lband()
        df["BBM_20_2.0"] = bb.bollinger_mavg()
        df["BBU_20_2.0"] = bb.bollinger_hband()
    except Exception:
        pass

    # Volume SMA (20-day average)
    df["vol_sma_20"] = SMAIndicator(close=df["volume"].astype(float), window=20).sma_indicator()

    logger.debug(f"Calculated indicators, columns: {list(df.columns)}")
    return df


def detect_orb_signal(df: pd.DataFrame, orb_period: int = 15) -> dict | None:
    """
    Detect Opening Range Breakout.
    Uses the first `orb_period` candles to define the range,
    then checks if the latest candle breaks above/below.

    Returns: {"signal": "buy"/"sell", "orb_high": float, "orb_low": float} or None
    """
    if len(df) < orb_period + 1:
        return None

    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    # First N candles define the opening range
    orb_data = df.iloc[:orb_period]
    orb_high = orb_data["high"].max()
    orb_low = orb_data["low"].min()

    # Latest candle
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > orb_period + 1 else None

    # Breakout above ORB high
    if latest["close"] > orb_high and (prev is None or prev["close"] <= orb_high):
        volume_ok = True
        if "vol_sma_20" in df.columns and pd.notna(latest.get("vol_sma_20")):
            volume_ok = latest["volume"] > latest["vol_sma_20"] * 1.2
        if volume_ok:
            return {"signal": "buy", "orb_high": orb_high, "orb_low": orb_low}

    # Breakdown below ORB low
    if latest["close"] < orb_low and (prev is None or prev["close"] >= orb_low):
        volume_ok = True
        if "vol_sma_20" in df.columns and pd.notna(latest.get("vol_sma_20")):
            volume_ok = latest["volume"] > latest["vol_sma_20"] * 1.2
        if volume_ok:
            return {"signal": "sell", "orb_high": orb_high, "orb_low": orb_low}

    return None


def detect_vwap_signal(df: pd.DataFrame) -> dict | None:
    """
    Detect VWAP crossover signal.
    Buy: price crosses above VWAP with volume confirmation.
    Sell: price crosses below VWAP with volume confirmation.
    """
    if len(df) < 3 or "vwap" not in df.columns:
        return None

    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    if pd.isna(latest.get("vwap")) or pd.isna(prev.get("vwap")):
        return None

    # Volume confirmation
    volume_ok = True
    if "vol_sma_20" in df.columns and pd.notna(latest.get("vol_sma_20")):
        volume_ok = latest["volume"] > latest["vol_sma_20"]

    # Bullish: price crosses above VWAP
    if prev["close"] <= prev["vwap"] and latest["close"] > latest["vwap"] and volume_ok:
        return {"signal": "buy", "vwap": latest["vwap"]}

    # Bearish: price crosses below VWAP
    if prev["close"] >= prev["vwap"] and latest["close"] < latest["vwap"] and volume_ok:
        return {"signal": "sell", "vwap": latest["vwap"]}

    return None


def get_support_resistance(df: pd.DataFrame) -> dict:
    """Calculate simple pivot point support/resistance levels."""
    if df.empty:
        return {}

    df.columns = [c.lower() for c in df.columns]
    last = df.iloc[-1]
    h, l, c = last["high"], last["low"], last["close"]

    pivot = (h + l + c) / 3
    return {
        "pivot": pivot,
        "r1": 2 * pivot - l,
        "r2": pivot + (h - l),
        "s1": 2 * pivot - h,
        "s2": pivot - (h - l),
    }
