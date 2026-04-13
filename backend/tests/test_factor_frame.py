import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.factor_frame import frame_to_histories, slice_frame_until
from app.data.storage import MarketStorage


class FactorFrameStorageTests(unittest.TestCase):
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
        self.conn.executemany(
            "INSERT INTO stock_daily (code, date, close, pbMRQ, amount, turn) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("AAA", "2024-01-02", 10.0, 1.1, 1000.0, 1.0),
                ("AAA", "2024-01-03", 11.0, 1.0, 1100.0, 1.1),
                ("BBB", "2024-01-02", 20.0, 2.0, 2000.0, 2.0),
            ],
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_get_history_frame_prefers_parquet_and_keeps_requested_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            parquet_root = Path(tmpdir)
            (parquet_root / "stock_daily").mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                [
                    {"code": "AAA", "date": "2024-01-02", "close": 100.0, "pbMRQ": 0.9},
                    {"code": "AAA", "date": "2024-01-03", "close": 110.0, "pbMRQ": 0.8},
                ]
            ).to_parquet(parquet_root / "stock_daily" / "AAA.parquet", index=False)

            storage = MarketStorage(parquet_root=parquet_root)
            with patch("app.data.storage.get_market_db", return_value=self.conn):
                frame = storage.get_history_frame(
                    ["AAA"],
                    start_date="2024-01-02",
                    end_date="2024-01-03",
                    columns=["code", "date", "close", "pbMRQ"],
                )

        self.assertEqual(frame.columns.tolist(), ["code", "date", "close", "pbMRQ"])
        self.assertEqual(frame["close"].tolist(), [100.0, 110.0])

    def test_slice_frame_until_keeps_rows_up_to_rebalance_date(self):
        frame = pd.DataFrame(
            [
                {"code": "AAA", "date": "2024-01-02", "close": 10.0},
                {"code": "AAA", "date": "2024-01-03", "close": 11.0},
                {"code": "BBB", "date": "2024-01-04", "close": 20.0},
            ]
        )

        sliced = slice_frame_until(frame, "2024-01-03")
        histories = frame_to_histories(sliced)

        self.assertEqual(sliced["date"].tolist(), ["2024-01-02", "2024-01-03"])
        self.assertEqual([row["close"] for row in histories["AAA"]], [10.0, 11.0])
        self.assertNotIn("BBB", histories)


if __name__ == "__main__":
    unittest.main()
