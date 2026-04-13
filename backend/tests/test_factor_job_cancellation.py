import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.jobs import JobCancelledError
from app.core.factor_runner import run_factor_job


class ChunkedStorage:
    def __init__(self):
        self.calls = []

    def get_all_stock_codes(self):
        return [f'code_{i:03d}' for i in range(250)]

    def get_downloaded_codes(self):
        return set(self.get_all_stock_codes())

    def get_histories(self, codes, start_date=None, end_date=None):
        self.calls.append(list(codes))
        return {code: [] for code in codes}

    def get_trade_dates(self, start_date=None, end_date=None):
        return []


class FactorJobCancellationTests(unittest.TestCase):
    def test_run_factor_job_checks_cancellation_between_history_batches(self):
        storage = ChunkedStorage()
        request = SimpleNamespace(
            pool_codes=None,
            start_date='2023-01-01',
            end_date='2024-12-31',
            rebalance='monthly',
            rebalance_dates=[],
            script=None,
            factor_configs=[],
            top_n=10,
            capital=100000,
        )
        checks = {'count': 0}

        def assert_not_cancelled():
            checks['count'] += 1
            if checks['count'] >= 3:
                raise JobCancelledError('cancelled during history load')

        with self.assertRaises(JobCancelledError):
            run_factor_job(storage, request, assert_not_cancelled=assert_not_cancelled)

        self.assertGreaterEqual(len(storage.calls), 1)


if __name__ == '__main__':
    unittest.main()
