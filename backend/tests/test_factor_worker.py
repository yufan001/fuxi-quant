import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.factor_worker import run_script_worker


class FactorWorkerTests(unittest.TestCase):
    def test_run_script_worker_returns_structured_script_error(self):
        frame = pd.DataFrame(
            [
                {"code": "AAA", "date": "2024-01-02", "close": 10.0},
                {"code": "AAA", "date": "2024-01-03", "close": 11.0},
            ]
        )

        result = run_script_worker(
            script='def score_frame(frame, context):\n    raise ValueError("boom")',
            history_frame_records=frame.to_dict("records"),
            rebalance_dates=["2024-01-03"],
            context_base={
                "start_date": "2024-01-01",
                "end_date": "2024-01-03",
                "rebalance": "monthly",
                "top_n": 1,
            },
        )

        self.assertEqual(result["status"], "script_error")
        self.assertEqual(result["error"]["code"], "script_error")
        self.assertIn("boom", result["error"]["message"])


if __name__ == "__main__":
    unittest.main()
