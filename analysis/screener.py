import pandas as pd

from analysis.sentiment import analyze_stock_sentiment
from analysis.technical import calculate_indicators
from config.settings import settings
from data.market_data import get_historical_bars, get_stock_universe
from utils.logger import logger


def screen_stocks(symbols: list[str] | None = None) -> list[dict]:
    """
    Screen stocks and score them based on:
    - Volume surge (> 1.5x 20-day average)
    - RSI in favorable range (40-70 for longs)
    - EMA momentum (9 EMA > 21 EMA)
    - News sentiment score

    Returns sorted list of candidates with scores.
    """
    if symbols is None:
        symbols = get_stock_universe()

    candidates = []

    for symbol in symbols:
        try:
            df = get_historical_bars(symbol, "1Day", days_back=30)
            if df.empty or len(df) < 20:
                continue

            df = calculate_indicators(df)
            latest = df.iloc[-1]

            score = 0.0
            reasons = []

            # Volume surge check
            if pd.notna(latest.get("vol_sma_20")) and latest["vol_sma_20"] > 0:
                vol_ratio = latest["volume"] / latest["vol_sma_20"]
                if vol_ratio > settings.VOLUME_SURGE_THRESHOLD:
                    score += 25
                    reasons.append(f"Volume surge {vol_ratio:.1f}x")

            # RSI check (40-70 is favorable for long entry)
            rsi = latest.get("rsi")
            if pd.notna(rsi):
                if 40 <= rsi <= 70:
                    score += 20
                    reasons.append(f"RSI {rsi:.1f} (favorable)")
                elif rsi < 30:
                    score += 15
                    reasons.append(f"RSI {rsi:.1f} (oversold bounce)")

            # EMA momentum (9 EMA > 21 EMA = bullish)
            ema_9 = latest.get("ema_9")
            ema_21 = latest.get("ema_21")
            if pd.notna(ema_9) and pd.notna(ema_21):
                if ema_9 > ema_21:
                    score += 20
                    reasons.append("Bullish EMA crossover")

            # Gap analysis (today's open vs yesterday's close)
            if len(df) >= 2:
                prev_close = df.iloc[-2]["close"]
                today_open = latest["open"]
                gap_pct = ((today_open - prev_close) / prev_close) * 100
                if abs(gap_pct) > 1.0:
                    score += 15
                    direction = "up" if gap_pct > 0 else "down"
                    reasons.append(f"Gap {direction} {abs(gap_pct):.1f}%")

            # News sentiment (slower, so only for stocks that already score well)
            if score >= 30:
                sentiment = analyze_stock_sentiment(symbol, save_to_db=True)
                if sentiment > 0.1:
                    score += 20
                    reasons.append(f"Positive news ({sentiment:.2f})")
                elif sentiment < -0.1:
                    score -= 10
                    reasons.append(f"Negative news ({sentiment:.2f})")

            if score > 0:
                candidates.append({
                    "symbol": symbol,
                    "score": score,
                    "reasons": reasons,
                    "price": latest["close"],
                    "volume": latest["volume"],
                    "rsi": rsi if pd.notna(rsi) else None,
                    "atr": latest.get("atr") if pd.notna(latest.get("atr")) else None,
                })

        except Exception as e:
            logger.error(f"Screening failed for {symbol}: {e}")
            continue

    # Sort by score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)
    logger.info(f"Screened {len(symbols)} stocks, found {len(candidates)} candidates")
    return candidates


def get_top_candidates(n: int | None = None) -> list[dict]:
    """Get top N stock candidates for today."""
    if n is None:
        n = settings.MAX_CANDIDATES
    candidates = screen_stocks()
    top = candidates[:n]
    if top:
        logger.info(f"Top {len(top)} candidates: {[c['symbol'] for c in top]}")
    return top
