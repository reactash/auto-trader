import signal
import sys
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import settings
from engine.models import init_db
from scheduler.jobs import (
    daily_report_job,
    market_close_job,
    market_open_job,
    pre_market_job,
    trading_loop_job,
)
from utils.logger import logger


def create_scheduler() -> BackgroundScheduler:
    """Create and configure the APScheduler with all trading jobs."""
    scheduler = BackgroundScheduler(timezone="US/Eastern")

    # Pre-market: 8:00 AM ET, Mon-Fri
    scheduler.add_job(
        pre_market_job,
        CronTrigger(hour=8, minute=0, day_of_week="mon-fri", timezone="US/Eastern"),
        id="pre_market",
        name="Pre-Market Scan",
        misfire_grace_time=300,
    )

    # Market open: 9:45 AM ET (after 15-min ORB period), Mon-Fri
    scheduler.add_job(
        market_open_job,
        CronTrigger(hour=9, minute=45, day_of_week="mon-fri", timezone="US/Eastern"),
        id="market_open",
        name="Market Open - Record ORB",
        misfire_grace_time=300,
    )

    # Trading loop: every 5 min from 9:50 AM to 3:40 PM ET, Mon-Fri
    scheduler.add_job(
        trading_loop_job,
        CronTrigger(
            minute=f"*/{settings.SCAN_INTERVAL_MINUTES}",
            hour="9-15",
            day_of_week="mon-fri",
            timezone="US/Eastern",
        ),
        id="trading_loop",
        name="Trading Loop",
        misfire_grace_time=120,
    )

    # Market close: 3:45 PM ET, Mon-Fri
    scheduler.add_job(
        market_close_job,
        CronTrigger(hour=15, minute=45, day_of_week="mon-fri", timezone="US/Eastern"),
        id="market_close",
        name="Market Close - Square Off",
        misfire_grace_time=300,
    )

    # Daily report: 4:00 PM ET, Mon-Fri
    scheduler.add_job(
        daily_report_job,
        CronTrigger(hour=16, minute=0, day_of_week="mon-fri", timezone="US/Eastern"),
        id="daily_report",
        name="Daily P&L Report",
        misfire_grace_time=600,
    )

    return scheduler


def main():
    logger.info("=" * 60)
    logger.info("AUTO-TRADER STARTING")
    logger.info(f"  Capital: ${settings.INITIAL_CAPITAL:,.2f}")
    logger.info(f"  Max Risk/Trade: {settings.MAX_RISK_PER_TRADE*100:.0f}%")
    logger.info(f"  Max Daily Loss: {settings.MAX_DAILY_LOSS*100:.0f}%")
    logger.info(f"  Max Positions: {settings.MAX_POSITIONS}")
    logger.info(f"  Strategy: ORB + VWAP")
    logger.info(f"  Universe: {settings.STOCK_UNIVERSE}")
    logger.info(f"  Paper Trading: ON")
    logger.info("=" * 60)

    # Initialize database
    init_db()

    # Verify Alpaca connection
    try:
        from engine.trader import AlpacaTrader
        trader = AlpacaTrader()
        account = trader.get_account()
        logger.info(f"Alpaca connected | Balance: ${account['portfolio_value']:,.2f}")
    except Exception as e:
        logger.error(f"Failed to connect to Alpaca: {e}")
        logger.error("Check your ALPACA_API_KEY and ALPACA_SECRET_KEY in .env")
        sys.exit(1)

    # Create and start scheduler
    scheduler = create_scheduler()
    scheduler.start()

    logger.info("Scheduler started. Waiting for market hours...")
    logger.info("  Pre-market scan: 8:00 AM ET")
    logger.info("  Trading: 9:45 AM - 3:45 PM ET")
    logger.info("  Daily report: 4:00 PM ET")
    logger.info("Press Ctrl+C to stop.")

    # Graceful shutdown
    def shutdown(signum, frame):
        logger.info("Shutting down...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Keep alive
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown(wait=False)
        logger.info("Auto-trader stopped.")


if __name__ == "__main__":
    main()
