import sqlite3
from pathlib import Path
from app.core.config import MARKET_DB_PATH, BIZ_DB_PATH


def _configure_conn(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def get_market_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(MARKET_DB_PATH))
    return _configure_conn(conn)


def get_biz_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(BIZ_DB_PATH), check_same_thread=False)
    return _configure_conn(conn)


def init_market_db():
    conn = get_market_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_daily (
            code TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            turn REAL,
            peTTM REAL,
            pbMRQ REAL,
            psTTM REAL,
            pcfNcfTTM REAL,
            PRIMARY KEY (code, date)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_weekly (
            code TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            turn REAL,
            peTTM REAL,
            pbMRQ REAL,
            psTTM REAL,
            pcfNcfTTM REAL,
            PRIMARY KEY (code, date)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_monthly (
            code TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            turn REAL,
            peTTM REAL,
            pbMRQ REAL,
            psTTM REAL,
            pcfNcfTTM REAL,
            PRIMARY KEY (code, date)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_info (
            code TEXT PRIMARY KEY,
            name TEXT,
            industry TEXT,
            listed_date TEXT,
            delisted_date TEXT,
            status TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_calendar (
            date TEXT PRIMARY KEY,
            is_trading_day INTEGER
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_daily_code ON stock_daily(code)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_daily_date ON stock_daily(date)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_weekly_code ON stock_weekly(code)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_weekly_date ON stock_weekly(date)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_monthly_code ON stock_monthly(code)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_monthly_date ON stock_monthly(date)
    """)

    conn.commit()
    conn.close()


def init_biz_db():
    conn = get_biz_db()
    conn.commit()
    conn.close()
