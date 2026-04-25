"""
Combined entry point: runs the trading bot scheduler + Streamlit dashboard
in a single process. Used for deployment on platforms that only allow one service.
"""
import subprocess
import sys
import os
import threading
import time

from main import create_scheduler
from config.settings import settings
from engine.models import init_db
from utils.logger import logger


def start_bot():
    """Start the trading bot scheduler in a background thread."""
    logger.info("Starting trading bot scheduler...")
    init_db()

    # Verify Alpaca connection
    try:
        from engine.trader import AlpacaTrader
        trader = AlpacaTrader()
        account = trader.get_account()
        logger.info(f"Alpaca connected | Balance: ${account['portfolio_value']:,.2f}")
    except Exception as e:
        logger.error(f"Failed to connect to Alpaca: {e}")
        return

    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Bot scheduler running in background")


def start_dashboard():
    """Start Streamlit dashboard."""
    port = os.environ.get("PORT", "8501")
    logger.info(f"Starting Streamlit dashboard on port {port}...")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", "dashboard/app.py",
        "--server.port", port,
        "--server.address", "0.0.0.0",
        "--server.headless", "true",
    ])


if __name__ == "__main__":
    # Start bot in background thread
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()

    # Give bot a moment to initialize
    time.sleep(2)

    # Start dashboard in main thread (blocking)
    start_dashboard()
