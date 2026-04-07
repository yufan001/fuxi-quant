import sqlite3
from pathlib import Path
from app.core.config import MARKET_DB_PATH


def get_market_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(MARKET_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


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

    conn.commit()
    conn.close()
