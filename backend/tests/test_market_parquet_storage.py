import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data.parquet_market_store import ParquetMarketStore


class MarketParquetStoreTests(unittest.TestCase):
    def test_replace_code_rows_writes_sorted_daily_parquet_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ParquetMarketStore(Path(tmpdir))
            store.replace_code_rows(
                "stock_daily",
                "AAA",
                [
                    {"code": "AAA", "date": "2024-01-03", "close": 11.0},
                    {"code": "AAA", "date": "2024-01-02", "close": 10.0},
                ],
            )

            file_path = Path(tmpdir) / "stock_daily" / "AAA.parquet"
            self.assertTrue(file_path.exists())

            frame = pd.read_parquet(file_path)
            self.assertEqual(frame["date"].tolist(), ["2024-01-02", "2024-01-03"])
            self.assertEqual(frame["close"].tolist(), [10.0, 11.0])


if __name__ == "__main__":
    unittest.main()
