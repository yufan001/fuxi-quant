import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.job_handlers import data_import_db_job, factor_backtest_job
from app.core.jobs import JobContext


class JobHandlerTests(unittest.TestCase):
    def make_context(self, payload):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = Path(temp_dir.name) / 'jobs.db'
        artifacts_dir = Path(temp_dir.name) / 'artifacts'

        def make_conn():
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute(
                "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, progress_json TEXT, logs_json TEXT, summary_json TEXT, artifact_json TEXT, cancel_requested INTEGER DEFAULT 0, updated_at TEXT)"
            )
            conn.execute(
                "INSERT OR REPLACE INTO jobs (id, progress_json, logs_json, summary_json, artifact_json, cancel_requested, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ('job_test', '{}', '[]', '{}', '[]', 0, 'now'),
            )
            conn.commit()
            return conn

        return JobContext(job_id='job_test', payload=payload, _db_factory=make_conn, artifacts_root=artifacts_dir)

    def test_factor_backtest_job_uses_existing_runner(self):
        context = self.make_context({'strategy_id': 'custom_factor_script'})
        mock_storage = MagicMock()

        with patch('app.core.job_handlers.MarketStorage', return_value=mock_storage), patch(
            'app.core.job_handlers.run_factor_job',
            return_value={'metrics': {'final_equity': 123.45}, 'equity_curve': [{'date': '2024-01-01', 'equity': 123.45}], 'rebalances': [{'date': '2024-01-01', 'selected': []}]},
        ):
            result = factor_backtest_job(context)

        self.assertEqual(result['metrics']['final_equity'], 123.45)
        self.assertEqual(context.progress['message'], 'factor_backtest_complete')
        self.assertEqual(context.summary['final_equity'], 123.45)
        self.assertTrue(any(item['name'] == 'result.json' for item in context.artifacts))
        self.assertTrue(any(item['name'] == 'equity_curve.json' for item in context.artifacts))

    def test_data_import_db_job_copies_source_database(self):
        src = tempfile.NamedTemporaryFile(delete=False)
        src.write(b'test-db')
        src.close()
        self.addCleanup(lambda: os.unlink(src.name))
        dest_dir = tempfile.TemporaryDirectory()
        self.addCleanup(dest_dir.cleanup)
        dest = Path(dest_dir.name) / 'market.db'

        context = self.make_context({'source_path': src.name, 'replace_existing': True})

        with patch('app.core.job_handlers.MARKET_DB_PATH', dest):
            result = data_import_db_job(context)

        self.assertTrue(dest.exists())
        self.assertEqual(dest.read_bytes(), b'test-db')
        self.assertEqual(result['target_path'], str(dest))
        self.assertTrue(any(item['name'] == 'import_report.json' for item in context.artifacts))


if __name__ == '__main__':
    unittest.main()
