import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data.storage import MarketStorage


class MarketAggregateRebuildTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        self.db_path = tmp.name
        conn = self.make_conn()
        schema = """
        CREATE TABLE {table} (
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
        conn.execute(schema.format(table="stock_daily"))
        conn.execute(schema.format(table="stock_weekly"))
        conn.execute(schema.format(table="stock_monthly"))
        conn.executemany(
            "INSERT INTO stock_daily (code, date, open, high, low, close, volume, amount, turn, pbMRQ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("AAA", "2024-01-29", 10, 12, 9, 11, 100, 1000, 1.0, 1.5),
                ("AAA", "2024-01-31", 11, 13, 10, 12, 120, 1200, 1.1, 1.4),
                ("AAA", "2024-02-01", 12, 14, 11, 13, 150, 1500, 1.2, 1.3),
                ("AAA", "2024-02-02", 13, 15, 12, 14, 180, 1800, 1.3, 1.2),
            ],
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        os.unlink(self.db_path)

    def make_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def test_rebuild_weekly_aggregates_ohlcv_from_daily_rows(self):
        storage = MarketStorage()
        with patch("app.data.storage.get_market_db", side_effect=self.make_conn):
            storage.rebuild_aggregates(["AAA"], periods=["weekly"])

        conn = self.make_conn()
        rows = [dict(r) for r in conn.execute("SELECT * FROM stock_weekly WHERE code = 'AAA' ORDER BY date").fetchall()]
        conn.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["open"], 10)
        self.assertEqual(rows[0]["high"], 15)
        self.assertEqual(rows[0]["low"], 9)
        self.assertEqual(rows[0]["close"], 14)
        self.assertEqual(rows[0]["volume"], 550)
        self.assertEqual(rows[0]["amount"], 5500)
        self.assertEqual(rows[0]["turn"], 4.6)
        self.assertEqual(rows[0]["pbMRQ"], 1.2)
        self.assertEqual(rows[0]["date"], "2024-02-02")

    def test_rebuild_monthly_splits_natural_months(self):
        storage = MarketStorage()
        with patch("app.data.storage.get_market_db", side_effect=self.make_conn):
            storage.rebuild_aggregates(["AAA"], periods=["monthly"])

        conn = self.make_conn()
        rows = [dict(r) for r in conn.execute("SELECT * FROM stock_monthly WHERE code = 'AAA' ORDER BY date").fetchall()]
        conn.close()
        self.assertEqual([row["date"] for row in rows], ["2024-01-31", "2024-02-02"])
        self.assertEqual(rows[0]["close"], 12)
        self.assertEqual(rows[1]["close"], 14)

    def test_download_daily_data_rebuilds_aggregates_and_syncs_parquet_for_updated_codes(self):
        from app.data.downloader import DataDownloader

        downloader = DataDownloader()
        downloader.storage = MagicMock()
        downloader.storage.get_latest_date.return_value = None
        downloader.storage.rebuild_aggregates = MagicMock()
        downloader.storage.sync_parquet_tables = MagicMock()
        downloader.provider = MagicMock()
        downloader.provider.get_daily.return_value = MagicMock(
            empty=False,
            to_dict=MagicMock(return_value=[
                {
                    "code": "AAA",
                    "date": "2024-02-02",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10.5,
                    "volume": 100,
                    "amount": 1000,
                    "turn": 1.0,
                    "peTTM": None,
                    "pbMRQ": 1.2,
                    "psTTM": None,
                    "pcfNcfTTM": None,
                }
            ]),
        )

        downloader.download_daily_data(codes=["AAA"], start_date="2024-02-01", end_date="2024-02-02")

        downloader.storage.rebuild_aggregates.assert_called_once_with(["AAA"], periods=["weekly", "monthly"])
        downloader.storage.sync_parquet_tables.assert_called_once_with(["AAA"], periods=["d", "w", "m"])

    def test_rebuild_aggregates_skips_rows_with_missing_ohlc(self):
        conn = self.make_conn()
        conn.executemany(
            "INSERT INTO stock_daily (code, date, open, high, low, close, volume, amount, turn, pbMRQ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("BBB", "2024-01-01", None, None, None, None, None, None, 9.9, 2.0),
                ("BBB", "2024-01-02", 20, 22, 19, 21, 200, 2000, 2.1, 1.9),
                ("BBB", "2024-01-03", 21, 23, 20, 22, 220, 2200, 2.2, 1.8),
            ],
        )
        conn.commit()
        conn.close()

        storage = MarketStorage()
        with patch("app.data.storage.get_market_db", side_effect=self.make_conn):
            storage.rebuild_aggregates(["BBB"], periods=["weekly"])

        conn = self.make_conn()
        rows = [dict(r) for r in conn.execute("SELECT * FROM stock_weekly WHERE code = 'BBB' ORDER BY date").fetchall()]
        conn.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["open"], 20)
        self.assertEqual(rows[0]["high"], 23)
        self.assertEqual(rows[0]["low"], 19)
        self.assertEqual(rows[0]["close"], 22)
        self.assertEqual(rows[0]["date"], "2024-01-03")


if __name__ == "__main__":
    unittest.main()
