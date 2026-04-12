import sqlite3
from typing import Optional
from app.models.db import get_market_db


class MarketStorage:

    def save_stock_daily(self, records: list[dict]):
        if not records:
            return
        conn = get_market_db()
        cursor = conn.cursor()
        cursor.executemany(
            """INSERT OR REPLACE INTO stock_daily
               (code, date, open, high, low, close, volume, amount, turn, peTTM, pbMRQ, psTTM, pcfNcfTTM)
               VALUES (:code, :date, :open, :high, :low, :close, :volume, :amount, :turn, :peTTM, :pbMRQ, :psTTM, :pcfNcfTTM)""",
            records,
        )
        conn.commit()
        conn.close()

    def save_stock_info(self, records: list[dict]):
        if not records:
            return
        conn = get_market_db()
        cursor = conn.cursor()
        cursor.executemany(
            """INSERT OR REPLACE INTO stock_info
               (code, name, industry, listed_date, delisted_date, status)
               VALUES (:code, :name, :industry, :listed_date, :delisted_date, :status)""",
            records,
        )
        conn.commit()
        conn.close()

    def save_trade_calendar(self, records: list[dict]):
        if not records:
            return
        conn = get_market_db()
        cursor = conn.cursor()
        cursor.executemany(
            """INSERT OR REPLACE INTO trade_calendar (date, is_trading_day)
               VALUES (:date, :is_trading_day)""",
            records,
        )
        conn.commit()
        conn.close()

    def get_daily(self, code: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> list[dict]:
        conn = get_market_db()
        sql = "SELECT * FROM stock_daily WHERE code = ?"
        params: list = [code]
        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)
        sql += " ORDER BY date ASC"
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_latest_date(self, code: str) -> Optional[str]:
        conn = get_market_db()
        row = conn.execute(
            "SELECT MAX(date) as max_date FROM stock_daily WHERE code = ?", (code,)
        ).fetchone()
        conn.close()
        if row and row["max_date"]:
            return row["max_date"]
        return None

    def search_stocks(self, keyword: Optional[str] = None) -> list[dict]:
        conn = get_market_db()
        if keyword:
            rows = conn.execute(
                "SELECT * FROM stock_info WHERE code LIKE ? OR name LIKE ? ORDER BY code LIMIT 50",
                (f"%{keyword}%", f"%{keyword}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM stock_info ORDER BY code LIMIT 50"
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_data_status(self) -> dict:
        conn = get_market_db()
        total_stocks = conn.execute("SELECT COUNT(DISTINCT code) as cnt FROM stock_daily").fetchone()["cnt"]
        total_records = conn.execute("SELECT COUNT(*) as cnt FROM stock_daily").fetchone()["cnt"]
        last_date = conn.execute("SELECT MAX(date) as max_date FROM stock_daily").fetchone()["max_date"]
        conn.close()
        return {
            "total_stocks": total_stocks,
            "total_records": total_records,
            "last_update_date": last_date,
        }

    def get_all_stock_codes(self) -> list[str]:
        conn = get_market_db()
        rows = conn.execute("SELECT code FROM stock_info ORDER BY code").fetchall()
        conn.close()
        return [r["code"] for r in rows]

    def get_histories(self, codes: list[str], start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict[str, list[dict]]:
        if not codes:
            return {}

        conn = get_market_db()
        placeholders = ",".join("?" for _ in codes)
        sql = f"SELECT * FROM stock_daily WHERE code IN ({placeholders})"
        params: list = list(codes)
        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)
        sql += " ORDER BY code ASC, date ASC"

        rows = conn.execute(sql, params).fetchall()
        conn.close()

        grouped = {code: [] for code in codes}
        for row in rows:
            grouped[row["code"]].append(dict(row))
        return grouped

    def get_trade_dates(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> list[str]:
        conn = get_market_db()
        sql = "SELECT date FROM trade_calendar WHERE is_trading_day = 1"
        params: list = []
        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)
        sql += " ORDER BY date ASC"

        rows = conn.execute(sql, params).fetchall()
        if not rows:
            sql = "SELECT DISTINCT date FROM stock_daily WHERE 1 = 1"
            params = []
            if start_date:
                sql += " AND date >= ?"
                params.append(start_date)
            if end_date:
                sql += " AND date <= ?"
                params.append(end_date)
            sql += " ORDER BY date ASC"
            rows = conn.execute(sql, params).fetchall()

        conn.close()
        return [row["date"] for row in rows]

    def get_downloaded_codes(self) -> set[str]:
        conn = get_market_db()
        rows = conn.execute("SELECT DISTINCT code FROM stock_daily").fetchall()
        conn.close()
        return {r["code"] for r in rows}
