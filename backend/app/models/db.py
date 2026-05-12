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
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS short_term_candidates (
            code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            name TEXT,
            sector TEXT,
            candidate_type TEXT,
            limit_hit_count INTEGER,
            limit_open_count INTEGER,
            visible_open_seconds REAL,
            closed_at_limit INTEGER,
            first_limit_time TEXT,
            last_limit_time TEXT,
            score_prev_day REAL,
            notes TEXT,
            data_quality TEXT,
            PRIMARY KEY (code, trade_date)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS short_term_auction_snapshots (
            code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            name TEXT,
            sector TEXT,
            auction_price REAL,
            prev_close REAL,
            auction_gap_pct REAL,
            auction_volume REAL,
            auction_amount REAL,
            auction_volume_vs_prev_day_pct REAL,
            limit_buy_rank INTEGER,
            limit_buy_amount REAL,
            data_source TEXT,
            data_quality TEXT,
            PRIMARY KEY (code, trade_date, captured_at)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS short_term_sector_snapshots (
            sector_name TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            sector_rank INTEGER,
            sector_limit_up_count INTEGER,
            sector_avg_gap_pct REAL,
            sector_auction_amount REAL,
            sector_score REAL,
            data_source TEXT,
            data_quality TEXT,
            PRIMARY KEY (sector_name, trade_date, captured_at)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS short_term_open_snapshots (
            code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            latest_price REAL,
            auction_price REAL,
            prev_close REAL,
            vwap_1m REAL,
            volume_1m REAL,
            amount_1m REAL,
            hold_above_auction INTEGER,
            hold_above_vwap INTEGER,
            pullback_pct REAL,
            large_sell_pressure_flag INTEGER,
            data_source TEXT,
            data_quality TEXT,
            PRIMARY KEY (code, trade_date, captured_at)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS short_term_scores (
            code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            phase TEXT NOT NULL,
            total_score REAL,
            score_breakdown_json TEXT,
            reasons_json TEXT,
            data_quality TEXT,
            PRIMARY KEY (code, trade_date, phase)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS short_term_alerts (
            id TEXT PRIMARY KEY,
            created_at TEXT,
            symbol TEXT,
            trade_date TEXT,
            alert_type TEXT,
            score REAL,
            message TEXT,
            payload_json TEXT,
            acknowledged INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS short_term_ocr_rows (
            id TEXT PRIMARY KEY,
            created_at TEXT,
            source_screenshot_path TEXT,
            screen_name TEXT,
            row_index INTEGER,
            raw_text TEXT,
            parsed_json TEXT,
            ocr_confidence REAL,
            data_quality TEXT,
            needs_review INTEGER DEFAULT 0
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_short_term_candidates_date ON short_term_candidates(trade_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_short_term_auction_date ON short_term_auction_snapshots(trade_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_short_term_open_date ON short_term_open_snapshots(trade_date)")
    conn.commit()
    conn.close()
