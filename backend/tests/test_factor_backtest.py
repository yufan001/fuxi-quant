import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.factor_backtest import FactorBacktestConfig, run_factor_backtest, run_factor_backtest_from_frame


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


class FactorBacktestTests(unittest.TestCase):
    def test_run_factor_backtest_selects_top_ranked_stock_and_grows_equity(self):
        histories = {
            "AAA": make_history(100, 2.0, 1.4, -0.01),
            "BBB": make_history(100, 0.8, 2.0, 0.01),
            "CCC": make_history(100, -0.5, 3.0, 0.02),
        }
        config = FactorBacktestConfig(
            factor_configs=[
                {"key": "pb", "weight": 0.5},
                {"key": "momentum_20", "weight": 0.5},
            ],
            top_n=1,
            initial_capital=100000,
            rebalance_dates=["2024-01-21"],
        )

        result = run_factor_backtest(histories, config)

        self.assertEqual(result.rebalances[0]["selected"][0]["code"], "AAA")
        self.assertGreater(result.metrics["final_equity"], config.initial_capital)
        self.assertEqual(result.equity_curve[-1]["date"], "2024-01-22")

    def test_run_factor_backtest_skips_symbols_without_required_history(self):
        histories = {
            "AAA": make_history(100, 2.0, 1.4, -0.01),
            "BBB": make_history(100, 3.0, 1.2, -0.02, days=10),
        }
        config = FactorBacktestConfig(
            factor_configs=[
                {"key": "pb", "weight": 0.5},
                {"key": "momentum_20", "weight": 0.5},
            ],
            top_n=2,
            initial_capital=100000,
            rebalance_dates=["2024-01-21"],
        )

        result = run_factor_backtest(histories, config)

        self.assertEqual([item["code"] for item in result.rebalances[0]["selected"]], ["AAA"])

    def test_run_factor_backtest_from_frame_selects_top_ranked_stock_and_grows_equity(self):
        frame = pd.DataFrame(
            [
                {"code": "AAA", "date": f"2024-01-{day:02d}", "close": 100 + day * 2.0, "pbMRQ": 1.4 - day * 0.01}
                for day in range(1, 23)
            ]
            + [
                {"code": "BBB", "date": f"2024-01-{day:02d}", "close": 100 + day * 0.8, "pbMRQ": 2.0 + day * 0.01}
                for day in range(1, 23)
            ]
        )
        config = FactorBacktestConfig(
            factor_configs=[
                {"key": "pb", "weight": 0.5},
                {"key": "momentum_20", "weight": 0.5},
            ],
            top_n=1,
            initial_capital=100000,
            rebalance_dates=["2024-01-21"],
        )

        result = run_factor_backtest_from_frame(frame, config)

        self.assertEqual(result.rebalances[0]["selected"][0]["code"], "AAA")
        self.assertGreater(result.metrics["final_equity"], config.initial_capital)


if __name__ == "__main__":
    unittest.main()
