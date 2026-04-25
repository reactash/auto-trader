from datetime import datetime

import pytz

from analysis.screener import get_top_candidates
from analysis.sentiment import analyze_stock_sentiment
from analysis.technical import calculate_indicators, detect_orb_signal, detect_vwap_signal
from config.settings import settings
from data.market_data import get_historical_bars
from engine.models import get_open_trades, get_todays_pnl
from strategy.risk_manager import (
    calculate_position_size,
    check_daily_loss_limit,
    check_profit_target,
    get_stop_loss,
    get_take_profit,
    should_trail_stop,
)
from utils.logger import logger

ET = pytz.timezone("US/Eastern")


class ORBVWAPStrategy:
    """Opening Range Breakout + VWAP crossover intraday strategy."""

    def __init__(self):
        self.candidates: list[dict] = []
        self.orb_ranges: dict[str, dict] = {}  # symbol -> {high, low}
        self.daily_pnl: float = 0.0

    def pre_market_scan(self) -> list[dict]:
        """Run before market open. Screen and rank stocks."""
        logger.info("Running pre-market scan...")
        self.candidates = get_top_candidates()
        logger.info(f"Pre-market scan complete: {len(self.candidates)} candidates")
        return self.candidates

    def record_opening_range(self, symbol: str) -> dict | None:
        """
        Record the opening range (first 15-min high/low) for a symbol.
        Call this after the first 15 minutes of trading.
        """
        df = get_historical_bars(symbol, "1Min", days_back=1)
        if df.empty:
            return None

        # Filter to today's data only
        now = datetime.now(ET)
        today = now.date()
        df.index = df.index.tz_convert(ET) if df.index.tz else df.index.tz_localize("UTC").tz_convert(ET)
        today_data = df[df.index.date == today]

        if len(today_data) < settings.ORB_PERIOD_MINUTES:
            return None

        orb_data = today_data.iloc[:settings.ORB_PERIOD_MINUTES]
        orb_range = {
            "high": orb_data["high"].max(),
            "low": orb_data["low"].min(),
            "recorded_at": now.isoformat(),
        }
        self.orb_ranges[symbol] = orb_range
        logger.info(f"ORB for {symbol}: High=${orb_range['high']:.2f}, Low=${orb_range['low']:.2f}")
        return orb_range

    def check_entry_signal(self, symbol: str, capital: float) -> dict | None:
        """
        Check if a symbol has an entry signal.
        Combines ORB breakout + VWAP confirmation + sentiment.

        Returns signal dict or None.
        """
        # Get intraday data (5-min candles for today)
        df = get_historical_bars(symbol, "5Min", days_back=1)
        if df.empty or len(df) < 5:
            return None

        df = calculate_indicators(df)

        # Check ORB signal
        orb_signal = detect_orb_signal(df, settings.ORB_PERIOD_MINUTES // 5)

        # Check VWAP signal
        vwap_signal = detect_vwap_signal(df)

        # Need at least one signal
        if not orb_signal and not vwap_signal:
            return None

        # Determine direction — both signals must agree if both present
        if orb_signal and vwap_signal:
            if orb_signal["signal"] != vwap_signal["signal"]:
                return None
            side = orb_signal["signal"]
            reason = f"ORB + VWAP {side}"
        elif orb_signal:
            side = orb_signal["signal"]
            reason = f"ORB breakout {side}"
        else:
            side = vwap_signal["signal"]
            reason = f"VWAP crossover {side}"

        # Get latest price and ATR
        latest = df.iloc[-1]
        entry_price = latest["close"]
        atr = latest.get("atr")

        if atr is None or atr <= 0:
            # Fallback: use 1% of price as ATR estimate
            atr = entry_price * 0.01

        # Calculate stop loss and take profit
        stop_loss = get_stop_loss(entry_price, atr, side)
        take_profit = get_take_profit(entry_price, stop_loss, side)

        # Position sizing
        qty = calculate_position_size(capital, entry_price, stop_loss)
        if qty <= 0:
            return None

        signal = {
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "atr": atr,
            "reason": reason,
        }

        logger.info(
            f"SIGNAL: {side.upper()} {qty} {symbol} @ ${entry_price:.2f} | "
            f"SL: ${stop_loss:.2f} | TP: ${take_profit:.2f} | {reason}"
        )
        return signal

    def check_exit_signal(self, trade: dict, capital: float) -> dict | None:
        """
        Check if an open position should be exited.
        Exit conditions: stop loss, take profit, trailing stop, time-based, daily limit.
        """
        symbol = trade["symbol"]
        side = trade["side"]
        entry_price = trade["entry_price"]
        stop_loss = trade["stop_loss"]
        take_profit = trade["take_profit"]

        # Get current price
        df = get_historical_bars(symbol, "5Min", days_back=1)
        if df.empty:
            return None

        df = calculate_indicators(df)
        latest = df.iloc[-1]
        current_price = latest["close"]
        atr = latest.get("atr", entry_price * 0.01)

        # 1. Stop loss hit
        if side == "buy" and current_price <= stop_loss:
            return {"action": "exit", "price": current_price, "reason": "stop_loss"}
        if side == "sell" and current_price >= stop_loss:
            return {"action": "exit", "price": current_price, "reason": "stop_loss"}

        # 2. Take profit hit
        if side == "buy" and current_price >= take_profit:
            return {"action": "exit", "price": current_price, "reason": "take_profit"}
        if side == "sell" and current_price <= take_profit:
            return {"action": "exit", "price": current_price, "reason": "take_profit"}

        # 3. Trailing stop
        new_stop = should_trail_stop(current_price, entry_price, stop_loss, atr, side)
        if new_stop is not None:
            return {"action": "update_stop", "new_stop": new_stop, "price": current_price}

        # 4. Daily loss limit
        daily_pnl = get_todays_pnl()
        if check_daily_loss_limit(daily_pnl, capital):
            return {"action": "exit", "price": current_price, "reason": "daily_loss_limit"}

        # 5. Daily profit target
        if check_profit_target(daily_pnl, capital):
            return {"action": "exit", "price": current_price, "reason": "profit_target_reached"}

        # 6. Time-based exit (15 min before close = 3:45 PM ET)
        now = datetime.now(ET)
        if now.hour == 15 and now.minute >= 45:
            return {"action": "exit", "price": current_price, "reason": "end_of_day"}

        return None

    def generate_signals(self, capital: float) -> list[dict]:
        """Generate entry signals for all candidates."""
        signals = []
        open_trades = get_open_trades()
        open_symbols = {t["symbol"] for t in open_trades}

        # Check position limit
        if len(open_trades) >= settings.MAX_POSITIONS:
            logger.info(f"Max positions ({settings.MAX_POSITIONS}) reached, no new entries")
            return []

        # Check daily limits
        daily_pnl = get_todays_pnl()
        if check_daily_loss_limit(daily_pnl, capital):
            return []
        if check_profit_target(daily_pnl, capital):
            return []

        for candidate in self.candidates:
            symbol = candidate["symbol"]
            if symbol in open_symbols:
                continue

            signal = self.check_entry_signal(symbol, capital)
            if signal:
                signals.append(signal)

            # Stop if we'd exceed max positions
            if len(open_trades) + len(signals) >= settings.MAX_POSITIONS:
                break

        return signals
