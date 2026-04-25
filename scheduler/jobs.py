from datetime import datetime

import pytz

from analysis.sentiment import get_market_sentiment
from config.settings import settings
from engine.models import (
    get_open_trades,
    get_todays_trades,
    init_db,
    log_daily_pnl,
    log_trade_close,
)
from engine.trader import AlpacaTrader
from strategy.intraday import ORBVWAPStrategy
from utils.logger import logger

ET = pytz.timezone("America/New_York")

# Global state
_trader: AlpacaTrader | None = None
_strategy: ORBVWAPStrategy | None = None


def _get_trader() -> AlpacaTrader:
    global _trader
    if _trader is None:
        _trader = AlpacaTrader()
    return _trader


def _get_strategy() -> ORBVWAPStrategy:
    global _strategy
    if _strategy is None:
        _strategy = ORBVWAPStrategy()
    return _strategy


def pre_market_job():
    """8:00 AM ET — Fetch news, sentiment, screen stocks."""
    logger.info("=" * 60)
    logger.info("PRE-MARKET JOB STARTED")
    logger.info("=" * 60)

    init_db()
    strategy = _get_strategy()

    # Get market sentiment
    market_mood = get_market_sentiment()
    logger.info(f"Market sentiment: {market_mood:.3f}")

    # Screen stocks
    candidates = strategy.pre_market_scan()
    for c in candidates[:10]:
        logger.info(f"  {c['symbol']}: score={c['score']:.0f} | {', '.join(c['reasons'])}")

    logger.info(f"Pre-market scan complete: {len(candidates)} candidates")


def market_open_job():
    """9:30 AM ET — Record opening ranges for candidates."""
    logger.info("=" * 60)
    logger.info("MARKET OPEN — Recording opening ranges")
    logger.info("=" * 60)

    strategy = _get_strategy()

    # Record ORB for each candidate
    for candidate in strategy.candidates[:settings.MAX_CANDIDATES]:
        symbol = candidate["symbol"]
        orb = strategy.record_opening_range(symbol)
        if orb:
            logger.info(f"  {symbol}: ORB High=${orb['high']:.2f}, Low=${orb['low']:.2f}")


def trading_loop_job():
    """Every 5 min (9:45 AM - 3:45 PM ET) — Check signals, manage positions."""
    now = datetime.now(ET)
    logger.info(f"Trading loop @ {now.strftime('%H:%M:%S ET')}")

    trader = _get_trader()
    strategy = _get_strategy()

    account = trader.get_account()
    capital = account["portfolio_value"]

    # Check exits for open positions
    open_trades = get_open_trades()
    for trade in open_trades:
        exit_signal = strategy.check_exit_signal(trade, capital)
        if exit_signal is None:
            continue

        if exit_signal["action"] == "exit":
            trader.close_position(
                trade["symbol"],
                trade_id=trade["id"],
                reason=exit_signal["reason"],
            )
        elif exit_signal["action"] == "update_stop":
            # Update stop loss in our DB (Alpaca doesn't track our custom stops)
            from engine.models import _get_connection
            conn = _get_connection()
            conn.execute(
                "UPDATE trade_log SET stop_loss = ? WHERE id = ?",
                (exit_signal["new_stop"], trade["id"]),
            )
            conn.commit()
            logger.info(f"Stop updated for {trade['symbol']}: ${exit_signal['new_stop']:.2f}")

    # Check for new entry signals
    signals = strategy.generate_signals(capital)
    for signal in signals:
        result = trader.place_order(
            symbol=signal["symbol"],
            qty=signal["qty"],
            side=signal["side"],
            stop_loss=signal["stop_loss"],
            take_profit=signal["take_profit"],
        )
        if result:
            logger.info(f"Order executed: {result}")


def market_close_job():
    """3:45 PM ET — Square off all positions."""
    logger.info("=" * 60)
    logger.info("MARKET CLOSE — Squaring off all positions")
    logger.info("=" * 60)

    trader = _get_trader()
    closed = trader.close_all_positions(reason="end_of_day")
    logger.info(f"Closed {closed} positions at end of day")


def daily_report_job():
    """4:00 PM ET — Calculate and log daily P&L."""
    logger.info("=" * 60)
    logger.info("DAILY REPORT")
    logger.info("=" * 60)

    trader = _get_trader()
    account = trader.get_account()

    todays_trades = get_todays_trades()
    closed_trades = [t for t in todays_trades if t["status"] == "closed"]

    wins = sum(1 for t in closed_trades if (t.get("pnl") or 0) > 0)
    losses = sum(1 for t in closed_trades if (t.get("pnl") or 0) < 0)
    total_pnl = sum(t.get("pnl") or 0 for t in closed_trades)

    today = datetime.now(ET).strftime("%Y-%m-%d")
    log_daily_pnl(
        date=today,
        starting_balance=account["portfolio_value"] - total_pnl,
        ending_balance=account["portfolio_value"],
        total_pnl=total_pnl,
        num_trades=len(closed_trades),
        wins=wins,
        losses=losses,
    )

    logger.info(f"  Date: {today}")
    logger.info(f"  Portfolio: ${account['portfolio_value']:.2f}")
    logger.info(f"  Daily P&L: ${total_pnl:.2f}")
    logger.info(f"  Trades: {len(closed_trades)} (W:{wins} / L:{losses})")
    logger.info(f"  Win Rate: {(wins/len(closed_trades)*100) if closed_trades else 0:.1f}%")
    logger.info("=" * 60)

    # Reset strategy state for next day
    global _strategy
    _strategy = None
