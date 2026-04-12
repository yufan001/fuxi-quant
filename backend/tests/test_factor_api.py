import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.backtest import FactorBacktestRequest, get_factor_backtest_result, run_factor_backtest_job
from app.api.strategy import list_strategies


def make_history(base_close: float, daily_step: float, base_pb: float, pb_step: float, days: int = 22):
    return [
        {
            "date": f"2024-01-{day:02d}",
            "close": base_close + day * daily_step,
            "pbMRQ": base_pb + day * pb_step,
            "amount": 1_000_000 + day * 1_000,
            "turn": 1.0 + day * 0.01,
        }
        for day in range(1, days + 1)
    ]


class FactorApiTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        self.db_path = tmp.name
        self.conn = self.make_conn()
        self.conn.execute(
            """
            CREATE TABLE factor_backtest_runs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                config_json TEXT NOT NULL,
                result_json TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE user_strategies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT DEFAULT 'custom',
                description TEXT DEFAULT '',
                params TEXT DEFAULT '{}',
                code TEXT DEFAULT '',
                enabled INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        self.conn.commit()

    def make_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def tearDown(self):
        self.conn.close()
        os.unlink(self.db_path)

    def test_run_factor_backtest_job_persists_result(self):
        mock_storage = MagicMock()
        mock_storage.get_histories.return_value = {
            "AAA": make_history(100, 2.0, 1.4, -0.01),
            "BBB": make_history(100, 0.8, 2.0, 0.01),
        }

        request = FactorBacktestRequest(
            factor_configs=[
                {"key": "pb", "weight": 0.5},
                {"key": "momentum_20", "weight": 0.5},
            ],
            top_n=1,
            start_date="2024-01-01",
            end_date="2024-01-22",
            rebalance_dates=["2024-01-21"],
            pool_codes=["AAA", "BBB"],
        )

        with patch("app.api.backtest.MarketStorage", return_value=mock_storage), patch(
            "app.api.backtest.get_market_db", side_effect=self.make_conn
        ):
            response = run_factor_backtest_job(request)

        self.assertIn("run_id", response["data"])
        self.assertEqual(response["data"]["metrics"]["rebalance_count"], 1)

        check_conn = self.make_conn()
        row = check_conn.execute("SELECT * FROM factor_backtest_runs WHERE id = ?", (response["data"]["run_id"],)).fetchone()
        check_conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "success")
        self.assertEqual(json.loads(row["result_json"])["metrics"]["rebalance_count"], 1)

    def test_run_factor_backtest_job_accepts_inline_script(self):
        mock_storage = MagicMock()
        mock_storage.get_histories.return_value = {
            "AAA": make_history(100, 2.0, 1.4, -0.01),
            "BBB": make_history(100, 0.8, 2.0, 0.01),
        }

        request = FactorBacktestRequest(
            script='def score_stocks(histories, context):\n    return {code: rows[-1]["close"] for code, rows in histories.items()}',
            factor_configs=[],
            top_n=1,
            start_date="2024-01-01",
            end_date="2024-01-22",
            rebalance_dates=["2024-01-21"],
            pool_codes=["AAA", "BBB"],
        )

        with patch("app.api.backtest.MarketStorage", return_value=mock_storage), patch(
            "app.api.backtest.get_market_db", side_effect=self.make_conn
        ):
            response = run_factor_backtest_job(request)

        self.assertEqual(response["data"]["rebalances"][0]["selected"][0]["code"], "AAA")

    def test_run_factor_backtest_job_loads_saved_script_strategy(self):
        self.conn.execute(
            "INSERT INTO user_strategies (id, name, type, description, params, code) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "custom_factor_script",
                "脚本因子",
                "factor",
                "inline script",
                json.dumps({"top_n": 1, "rebalance": "monthly"}),
                'def score_stocks(histories, context):\n    return {code: rows[-1]["close"] for code, rows in histories.items()}',
            ),
        )
        self.conn.commit()

        mock_storage = MagicMock()
        mock_storage.get_histories.return_value = {
            "AAA": make_history(100, 2.0, 1.4, -0.01),
            "BBB": make_history(100, 0.8, 2.0, 0.01),
        }

        request = FactorBacktestRequest(
            strategy_id="custom_factor_script",
            factor_configs=[],
            top_n=1,
            start_date="2024-01-01",
            end_date="2024-01-22",
            rebalance_dates=["2024-01-21"],
            pool_codes=["AAA", "BBB"],
        )

        with patch("app.api.backtest.MarketStorage", return_value=mock_storage), patch(
            "app.api.backtest.get_market_db", side_effect=self.make_conn
        ):
            response = run_factor_backtest_job(request)

        self.assertEqual(response["data"]["rebalances"][0]["selected"][0]["code"], "AAA")

    def test_get_factor_backtest_result_reads_saved_run(self):
        payload = {"metrics": {"final_equity": 123456.78}, "equity_curve": [], "rebalances": []}
        self.conn.execute(
            "INSERT INTO factor_backtest_runs (id, status, config_json, result_json) VALUES (?, ?, ?, ?)",
            ("run_1", "success", json.dumps({"top_n": 1}), json.dumps(payload)),
        )
        self.conn.commit()

        with patch("app.api.backtest.get_market_db", side_effect=self.make_conn):
            response = get_factor_backtest_result("run_1")

        self.assertEqual(response["data"]["run_id"], "run_1")
        self.assertEqual(response["data"]["metrics"]["final_equity"], 123456.78)

    def test_strategy_list_includes_builtin_factor_template(self):
        with patch("app.api.strategy.get_market_db", side_effect=self.make_conn):
            response = list_strategies()

        ids = {item["id"] for item in response["data"]}
        self.assertIn("factor_low_pb_momentum", ids)


if __name__ == "__main__":
    unittest.main()
