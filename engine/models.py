import sqlite3
from datetime import datetime

from config.settings import settings
from utils.logger import logger

_connection = None


def _get_connection() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        _connection = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
        _connection.row_factory = sqlite3.Row
    return _connection


def init_db():
    """Create all tables if they don't exist."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            qty INTEGER NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL,
            pnl REAL,
            entry_time TEXT NOT NULL,
            exit_time TEXT,
            strategy TEXT DEFAULT 'ORB_VWAP',
            stop_loss REAL,
            take_profit REAL,
            exit_reason TEXT,
            status TEXT DEFAULT 'open'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_pnl (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,
            starting_balance REAL NOT NULL,
            ending_balance REAL NOT NULL,
            total_pnl REAL NOT NULL,
            num_trades INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            win_rate REAL DEFAULT 0.0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            headline TEXT NOT NULL,
            sentiment_score REAL NOT NULL,
            source TEXT,
            url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    logger.info("Database initialized")


def log_trade_open(symbol: str, side: str, qty: int, entry_price: float,
                   stop_loss: float, take_profit: float) -> int:
    """Log a new trade entry. Returns the trade ID."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO trade_log (symbol, side, qty, entry_price, entry_time, stop_loss, take_profit, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'open')""",
        (symbol, side, qty, entry_price, datetime.now().isoformat(), stop_loss, take_profit),
    )
    conn.commit()
    trade_id = cursor.lastrowid
    logger.info(f"Trade opened: #{trade_id} {side} {qty} {symbol} @ ${entry_price:.2f}")
    return trade_id


def log_trade_close(trade_id: int, exit_price: float, exit_reason: str):
    """Close a trade and calculate P&L."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM trade_log WHERE id = ?", (trade_id,))
    trade = cursor.fetchone()
    if not trade:
        logger.error(f"Trade #{trade_id} not found")
        return

    if trade["side"] == "buy":
        pnl = (exit_price - trade["entry_price"]) * trade["qty"]
    else:
        pnl = (trade["entry_price"] - exit_price) * trade["qty"]

    cursor.execute(
        """UPDATE trade_log SET exit_price = ?, exit_time = ?, pnl = ?, exit_reason = ?, status = 'closed'
           WHERE id = ?""",
        (exit_price, datetime.now().isoformat(), pnl, exit_reason, trade_id),
    )
    conn.commit()
    logger.info(f"Trade closed: #{trade_id} {trade['symbol']} P&L: ${pnl:.2f} ({exit_reason})")


def log_daily_pnl(date: str, starting_balance: float, ending_balance: float,
                  total_pnl: float, num_trades: int, wins: int, losses: int):
    """Log daily performance summary."""
    conn = _get_connection()
    cursor = conn.cursor()
    win_rate = (wins / num_trades * 100) if num_trades > 0 else 0.0

    cursor.execute(
        """INSERT OR REPLACE INTO daily_pnl (date, starting_balance, ending_balance, total_pnl,
           num_trades, wins, losses, win_rate) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (date, starting_balance, ending_balance, total_pnl, num_trades, wins, losses, win_rate),
    )
    conn.commit()
    logger.info(f"Daily P&L logged: {date} | P&L: ${total_pnl:.2f} | Trades: {num_trades} | Win rate: {win_rate:.1f}%")


def log_news_score(symbol: str, headline: str, sentiment_score: float,
                   source: str = "", url: str = ""):
    """Log a news headline with its sentiment score."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO news_scores (date, symbol, headline, sentiment_score, source, url)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (datetime.now().strftime("%Y-%m-%d"), symbol, headline, sentiment_score, source, url),
    )
    conn.commit()


def get_open_trades() -> list[dict]:
    """Get all currently open trades."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trade_log WHERE status = 'open'")
    return [dict(row) for row in cursor.fetchall()]


def get_trade_history(limit: int = 50) -> list[dict]:
    """Get recent trade history."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trade_log ORDER BY id DESC LIMIT ?", (limit,))
    return [dict(row) for row in cursor.fetchall()]


def get_todays_trades() -> list[dict]:
    """Get all trades from today."""
    conn = _get_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT * FROM trade_log WHERE entry_time LIKE ?", (f"{today}%",))
    return [dict(row) for row in cursor.fetchall()]


def get_daily_pnl_history(limit: int = 30) -> list[dict]:
    """Get recent daily P&L history."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM daily_pnl ORDER BY date DESC LIMIT ?", (limit,))
    return [dict(row) for row in cursor.fetchall()]


def get_todays_news_scores(symbol: str | None = None) -> list[dict]:
    """Get today's news sentiment scores."""
    conn = _get_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    if symbol:
        cursor.execute("SELECT * FROM news_scores WHERE date = ? AND symbol = ? ORDER BY id DESC", (today, symbol))
    else:
        cursor.execute("SELECT * FROM news_scores WHERE date = ? ORDER BY id DESC", (today,))
    return [dict(row) for row in cursor.fetchall()]


def get_todays_pnl() -> float:
    """Calculate today's total P&L from closed trades."""
    conn = _get_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute(
        "SELECT COALESCE(SUM(pnl), 0) as total FROM trade_log WHERE status = 'closed' AND exit_time LIKE ?",
        (f"{today}%",),
    )
    return cursor.fetchone()["total"]
