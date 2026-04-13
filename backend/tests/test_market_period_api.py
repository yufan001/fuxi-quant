import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app


class MarketPeriodApiTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        self.db_path = tmp.name
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        for table in ("stock_daily", "stock_weekly", "stock_monthly"):
            conn.execute(f"""
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
            """)
        conn.execute("INSERT INTO stock_weekly (code, date, close) VALUES ('AAA', '2024-02-02', 14)")
        conn.commit()
        conn.close()

    def tearDown(self):
        os.unlink(self.db_path)

    def make_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def test_market_kline_supports_weekly_period(self):
        with patch("app.data.storage.get_market_db", side_effect=self.make_conn), \
             patch("app.models.db.init_market_db", lambda: None), \
             patch("app.models.db.init_biz_db", lambda: None), \
             patch("app.core.scheduler.init_scheduler", lambda: None), \
             patch("app.core.job_handlers.register_job_handlers", lambda manager: None):
            with TestClient(create_app()) as client:
                response = client.get("/api/market/kline/AAA?period=w")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["date"], "2024-02-02")

    def test_market_kline_rejects_invalid_period(self):
        with patch("app.models.db.init_market_db", lambda: None), \
             patch("app.models.db.init_biz_db", lambda: None), \
             patch("app.core.scheduler.init_scheduler", lambda: None), \
             patch("app.core.job_handlers.register_job_handlers", lambda manager: None):
            with TestClient(create_app(), raise_server_exceptions=False) as client:
                response = client.get("/api/market/kline/AAA?period=q")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "unsupported period: q")


if __name__ == "__main__":
    unittest.main()
