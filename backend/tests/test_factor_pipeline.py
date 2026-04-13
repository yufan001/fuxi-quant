import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.factors.base import FactorDefinition, combine_factor_scores, rank_stocks
from app.factors.builtin import build_builtin_definitions, compute_factor_values, compute_factor_values_from_frame


class FactorPipelineTests(unittest.TestCase):
    def test_combine_factor_scores_respects_factor_direction_and_weight(self):
        definitions = [
            FactorDefinition(key="pb", label="PB", direction="lower_better", weight=0.6),
            FactorDefinition(key="momentum_20", label="20日动量", direction="higher_better", weight=0.4),
        ]
        raw_values = {
            "pb": {"AAA": 1.0, "BBB": 2.5, "CCC": 4.0},
            "momentum_20": {"AAA": 0.12, "BBB": 0.05, "CCC": -0.03},
        }

        scores = combine_factor_scores(raw_values, definitions)

        self.assertEqual([item["code"] for item in scores], ["AAA", "BBB", "CCC"])
        self.assertGreater(scores[0]["score"], scores[1]["score"])
        self.assertGreater(scores[1]["score"], scores[2]["score"])
        self.assertIn("pb", scores[0]["factor_scores"])
        self.assertIn("momentum_20", scores[0]["factor_scores"])

    def test_combine_factor_scores_drops_codes_with_missing_factor_values(self):
        definitions = [
            FactorDefinition(key="pb", label="PB", direction="lower_better", weight=0.5),
            FactorDefinition(key="momentum_20", label="20日动量", direction="higher_better", weight=0.5),
        ]
        raw_values = {
            "pb": {"AAA": 1.2, "BBB": 2.8},
            "momentum_20": {"AAA": 0.1},
        }

        scores = combine_factor_scores(raw_values, definitions)

        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0]["code"], "AAA")

    def test_rank_stocks_returns_top_n_in_score_order(self):
        ranked = rank_stocks(
            [
                {"code": "AAA", "score": 1.5, "factor_scores": {}, "factor_values": {}},
                {"code": "BBB", "score": 0.8, "factor_scores": {}, "factor_values": {}},
                {"code": "CCC", "score": -0.2, "factor_scores": {}, "factor_values": {}},
            ],
            top_n=2,
        )

        self.assertEqual([item["code"] for item in ranked], ["AAA", "BBB"])

    def test_build_builtin_definitions_uses_registry_defaults(self):
        definitions = build_builtin_definitions([
            {"key": "pb", "weight": 0.7},
            {"key": "momentum_20", "weight": 0.3},
        ])

        self.assertEqual([item.key for item in definitions], ["pb", "momentum_20"])
        self.assertEqual(definitions[0].direction, "lower_better")
        self.assertEqual(definitions[0].weight, 0.7)
        self.assertEqual(definitions[1].direction, "higher_better")

    def test_compute_factor_values_uses_latest_snapshot_and_lookback_return(self):
        definitions = build_builtin_definitions([
            {"key": "pb", "weight": 0.5},
            {"key": "momentum_20", "weight": 0.5},
        ])
        histories = {
            "AAA": [
                {"date": f"2024-01-{day:02d}", "close": 100 + day, "pbMRQ": 2.0 - day * 0.02}
                for day in range(1, 23)
            ],
            "BBB": [
                {"date": f"2024-01-{day:02d}", "close": 80 + day * 0.5, "pbMRQ": 1.5 + day * 0.01}
                for day in range(1, 23)
            ],
        }

        values = compute_factor_values(histories, definitions)

        self.assertAlmostEqual(values["pb"]["AAA"], histories["AAA"][-1]["pbMRQ"])
        expected_momentum = histories["AAA"][-1]["close"] / histories["AAA"][-21]["close"] - 1
        self.assertAlmostEqual(values["momentum_20"]["AAA"], expected_momentum)

    def test_compute_factor_values_from_frame_uses_latest_snapshot_and_momentum(self):
        definitions = build_builtin_definitions([
            {"key": "pb", "weight": 0.5},
            {"key": "momentum_20", "weight": 0.5},
        ])
        frame = pd.DataFrame(
            [
                {"code": "AAA", "date": f"2024-01-{day:02d}", "close": 100 + day, "pbMRQ": 2.0 - day * 0.02}
                for day in range(1, 23)
            ]
            + [
                {"code": "BBB", "date": f"2024-01-{day:02d}", "close": 80 + day * 0.5, "pbMRQ": 1.5 + day * 0.01}
                for day in range(1, 23)
            ]
        )

        values = compute_factor_values_from_frame(frame, definitions)

        self.assertAlmostEqual(values["pb"]["AAA"], frame[frame["code"] == "AAA"].iloc[-1]["pbMRQ"])
        self.assertAlmostEqual(values["momentum_20"]["AAA"], (122 / 102) - 1)


if __name__ == "__main__":
    unittest.main()
