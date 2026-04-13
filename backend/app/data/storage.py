import sqlite3
from collections import OrderedDict
from datetime import date
from typing import Optional

import pandas as pd

from app.core.config import MARKET_PARQUET_DIR
from app.data.duckdb_market_query import DuckDbMarketQuery
from app.data.parquet_market_store import ParquetMarketStore
from app.models.db import get_market_db


def _period_key(day: str, period: str) -> str:
    parsed = date.fromisoformat(day)
    if period == "weekly":
        iso_year, iso_week, _ = parsed.isocalendar()
        return f"{iso_year}-{iso_week:02d}"
    if period == "monthly":
        return day[:7]
    raise ValueError(f"unsupported aggregate period: {period}")


class MarketStorage:

    def __init__(self, parquet_root=None, parquet_store=None, duckdb_query=None):
        parquet_root = parquet_root or MARKET_PARQUET_DIR
        self.parquet_root = parquet_root
        self.parquet_store = parquet_store or ParquetMarketStore(parquet_root)
        self.duckdb_query = duckdb_query or DuckDbMarketQuery(parquet_root)

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

    def get_kline_data(self, code: str, start_date: Optional[str] = None, end_date: Optional[str] = None, period: str = "d") -> list[dict]:
        table = {
            "d": "stock_daily",
            "w": "stock_weekly",
            "m": "stock_monthly",
        }.get(period)
        if table is None:
            raise ValueError(f"unsupported period: {period}")

        conn = get_market_db()
        sql = f"SELECT * FROM {table} WHERE code = ?"
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

    def get_daily(self, code: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> list[dict]:
        return self.get_kline_data(code, start_date, end_date, period="d")

    def rebuild_aggregates(self, codes: list[str], periods: list[str] | None = None):
        periods = periods or ["weekly", "monthly"]
        table_map = {"weekly": "stock_weekly", "monthly": "stock_monthly"}
        conn = get_market_db()
        try:
            for code in codes:
                daily_rows = [
                    dict(r) for r in conn.execute(
                        "SELECT * FROM stock_daily WHERE code = ? ORDER BY date ASC",
                        (code,),
                    ).fetchall()
                ]
                valid_rows = [
                    row for row in daily_rows
                    if all(row.get(field) is not None for field in ("open", "high", "low", "close"))
                ]
                for period in periods:
                    table = table_map[period]
                    conn.execute(f"DELETE FROM {table} WHERE code = ?", (code,))
                    grouped = OrderedDict()
                    for row in valid_rows:
                        grouped.setdefault(_period_key(row["date"], period), []).append(row)
                    aggregates = []
                    for group_rows in grouped.values():
                        first = group_rows[0]
                        last = group_rows[-1]
                        aggregates.append({
                            "code": first["code"],
                            "date": last["date"],
                            "open": first["open"],
                            "high": max(item["high"] for item in group_rows),
                            "low": min(item["low"] for item in group_rows),
                            "close": last["close"],
                            "volume": sum((item["volume"] or 0) for item in group_rows),
                            "amount": sum((item["amount"] or 0) for item in group_rows),
                            "turn": sum((item["turn"] or 0) for item in group_rows),
                            "peTTM": last["peTTM"],
                            "pbMRQ": last["pbMRQ"],
                            "psTTM": last["psTTM"],
                            "pcfNcfTTM": last["pcfNcfTTM"],
                        })
                    if aggregates:
                        conn.executemany(
                            f"""INSERT OR REPLACE INTO {table}
                               (code, date, open, high, low, close, volume, amount, turn, peTTM, pbMRQ, psTTM, pcfNcfTTM)
                               VALUES (:code, :date, :open, :high, :low, :close, :volume, :amount, :turn, :peTTM, :pbMRQ, :psTTM, :pcfNcfTTM)""",
                            aggregates,
                        )
            conn.commit()
        finally:
            conn.close()

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

    def sync_parquet_tables(self, codes: list[str], periods: list[str] | None = None):
        periods = periods or ["d", "w", "m"]
        table_map = {"d": "stock_daily", "w": "stock_weekly", "m": "stock_monthly"}
        unique_codes = sorted(set(codes))
        if not unique_codes:
            return

        conn = get_market_db()
        try:
            for code in unique_codes:
                for period in periods:
                    table = table_map[period]
                    rows = [
                        dict(r)
                        for r in conn.execute(
                            f"SELECT * FROM {table} WHERE code = ? ORDER BY date ASC",
                            (code,),
                        ).fetchall()
                    ]
                    self.parquet_store.replace_code_rows(table, code, rows)
        finally:
            conn.close()

    def _get_history_frame_from_sqlite(
        self,
        codes: list[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        selected_columns = columns or [
            "code",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "turn",
            "peTTM",
            "pbMRQ",
            "psTTM",
            "pcfNcfTTM",
        ]
        if not codes:
            return pd.DataFrame(columns=selected_columns)

        conn = get_market_db()
        placeholders = ",".join("?" for _ in codes)
        sql = f"SELECT {', '.join(selected_columns)} FROM stock_daily WHERE code IN ({placeholders})"
        params: list = list(codes)
        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)
        sql += " ORDER BY code ASC, date ASC"
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        conn.close()
        return pd.DataFrame(rows, columns=selected_columns)

    def get_history_frame(
        self,
        codes: list[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        selected_columns = columns or [
            "code",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "turn",
            "peTTM",
            "pbMRQ",
            "psTTM",
            "pcfNcfTTM",
        ]
        frame = self.duckdb_query.get_history_frame(codes, start_date, end_date, columns=selected_columns)
        if not frame.empty or not codes:
            return frame
        return self._get_history_frame_from_sqlite(codes, start_date, end_date, columns=selected_columns)

    def _get_histories_from_sqlite(self, codes: list[str], start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict[str, list[dict]]:
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

    def get_histories(self, codes: list[str], start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict[str, list[dict]]:
        if not codes:
            return {}

        parquet_grouped = self.duckdb_query.get_histories(codes, start_date, end_date)
        missing_codes = [code for code, rows in parquet_grouped.items() if not rows]
        if not missing_codes:
            return parquet_grouped

        sqlite_grouped = self._get_histories_from_sqlite(missing_codes, start_date, end_date)
        for code in missing_codes:
            parquet_grouped[code] = sqlite_grouped.get(code, [])
        return parquet_grouped

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
