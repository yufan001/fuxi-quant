import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app
import app.core.scheduler  # noqa: F401


FAKE_JOB_HANDLERS = SimpleNamespace(register_job_handlers=lambda manager: None)


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
             patch.dict(sys.modules, {"app.core.job_handlers": FAKE_JOB_HANDLERS}):
            with TestClient(create_app()) as client:
                response = client.get("/api/market/kline/AAA?period=w")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["date"], "2024-02-02")

    def test_market_kline_rejects_invalid_period(self):
        with patch("app.models.db.init_market_db", lambda: None), \
             patch("app.models.db.init_biz_db", lambda: None), \
             patch("app.core.scheduler.init_scheduler", lambda: None), \
             patch.dict(sys.modules, {"app.core.job_handlers": FAKE_JOB_HANDLERS}):
            with TestClient(create_app(), raise_server_exceptions=False) as client:
                response = client.get("/api/market/kline/AAA?period=q")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "unsupported period: q")

    def test_xau_chart_endpoint_returns_dynamic_snapshot(self):
        snapshot = {
            "spot_symbol": "XAUUSD20",
            "futures_symbol": "GC=F",
            "interval": "1m",
            "candles": [{"time": 1, "open": 1, "high": 2, "low": 1, "close": 2, "volume": 1}],
            "zones": [{"rank": 1, "lower": 1.0, "upper": 2.0}],
            "trend_120m": {"visible": True, "direction": "up"},
        }
        with patch("app.models.db.init_market_db", lambda: None), \
             patch("app.models.db.init_biz_db", lambda: None), \
             patch("app.core.scheduler.init_scheduler", lambda: None), \
             patch.dict(sys.modules, {"app.core.job_handlers": FAKE_JOB_HANDLERS}), \
             patch("app.api.market.build_xau_chart_snapshot", return_value=snapshot) as build_snapshot:
            with TestClient(create_app()) as client:
                response = client.get("/api/market/xau/chart?interval=1m&lookback_bars=120")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["interval"], "1m")
        self.assertEqual(response.json()["data"]["trend_120m"]["direction"], "up")
        build_snapshot.assert_called_once()


if __name__ == "__main__":
    unittest.main()
