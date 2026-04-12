import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.factor_runner import run_factor_job


def make_history(base_close: float, daily_step: float, days: int = 22):
    return [
        {
            "date": f"2024-01-{day:02d}",
            "close": base_close + day * daily_step,
            "pbMRQ": 1.0 + day * 0.01,
            "amount": 1_000_000 + day * 1_000,
            "turn": 1.0 + day * 0.01,
        }
        for day in range(1, days + 1)
    ]


class FactorScriptRunnerTests(unittest.TestCase):
    def setUp(self):
        self.storage = MagicMock()
        self.storage.get_histories.return_value = {
            "AAA": make_history(100, 2.0),
            "BBB": make_history(100, 0.5),
        }
        self.storage.get_trade_dates.return_value = [f"2024-01-{day:02d}" for day in range(1, 23)]
        self.storage.get_all_stock_codes.return_value = ["AAA", "BBB"]
        self.storage.get_downloaded_codes.return_value = {"AAA", "BBB"}

    def test_run_factor_job_supports_score_scripts(self):
        request = SimpleNamespace(
            script='def score_stocks(histories, context):\n    return {code: rows[-1]["close"] for code, rows in histories.items()}',
            factor_configs=[],
            top_n=1,
            start_date="2024-01-01",
            end_date="2024-01-22",
            capital=100000,
            rebalance="monthly",
            rebalance_dates=["2024-01-21"],
            pool_codes=["AAA", "BBB"],
        )

        result = run_factor_job(self.storage, request)

        self.assertEqual(result["rebalances"][0]["selected"][0]["code"], "AAA")
        self.assertGreater(result["metrics"]["final_equity"], 100000)

    def test_run_factor_job_supports_portfolio_scripts(self):
        request = SimpleNamespace(
            script='def select_portfolio(histories, context):\n    return [{"code": "BBB", "weight": 1.0}]',
            factor_configs=[],
            top_n=1,
            start_date="2024-01-01",
            end_date="2024-01-22",
            capital=100000,
            rebalance="monthly",
            rebalance_dates=["2024-01-21"],
            pool_codes=["AAA", "BBB"],
        )

        result = run_factor_job(self.storage, request)

        self.assertEqual(result["rebalances"][0]["selected"][0]["code"], "BBB")
        self.assertGreater(result["metrics"]["final_equity"], 100000)


if __name__ == "__main__":
    unittest.main()
