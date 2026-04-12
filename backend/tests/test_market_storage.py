import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data.storage import MarketStorage


class MarketStorageTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """
            CREATE TABLE stock_daily (
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
            """
        )
        self.conn.execute(
            """
            CREATE TABLE trade_calendar (
                date TEXT PRIMARY KEY,
                is_trading_day INTEGER
            )
            """
        )
        self.conn.executemany(
            "INSERT INTO stock_daily (code, date, close, amount, turn, pbMRQ) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("AAA", "2024-01-02", 10, 1000, 1.0, 1.2),
                ("AAA", "2024-01-03", 11, 1100, 1.1, 1.1),
                ("BBB", "2024-01-02", 20, 2000, 2.0, 2.2),
            ],
        )
        self.conn.executemany(
            "INSERT INTO trade_calendar (date, is_trading_day) VALUES (?, ?)",
            [("2024-01-02", 1), ("2024-01-03", 1), ("2024-01-04", 0)],
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_get_histories_groups_rows_by_code(self):
        storage = MarketStorage()
        with patch("app.data.storage.get_market_db", return_value=self.conn):
            histories = storage.get_histories(["AAA", "BBB"], start_date="2024-01-02", end_date="2024-01-03")

        self.assertEqual([row["date"] for row in histories["AAA"]], ["2024-01-02", "2024-01-03"])
        self.assertEqual([row["date"] for row in histories["BBB"]], ["2024-01-02"])

    def test_get_trade_dates_returns_trading_days_only(self):
        storage = MarketStorage()
        with patch("app.data.storage.get_market_db", return_value=self.conn):
            trade_dates = storage.get_trade_dates("2024-01-02", "2024-01-04")

        self.assertEqual(trade_dates, ["2024-01-02", "2024-01-03"])


if __name__ == "__main__":
    unittest.main()
