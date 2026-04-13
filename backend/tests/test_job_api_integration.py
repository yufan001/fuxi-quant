import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.jobs import JobManager
from app.main import create_app


class JobApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        self.db_path = tmp.name
        self.manager = JobManager(db_factory=self.make_conn)

    def tearDown(self):
        os.unlink(self.db_path)

    def make_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def register_handlers(self, manager):
        manager.register('factor_backtest', lambda ctx: {'metrics': {'final_equity': 111111.0}, 'equity_curve': [], 'rebalances': []})
        manager.register('data_update', lambda ctx: {'mode': 'incremental', 'status': 'completed'})
        manager.register('data_import_db', lambda ctx: {'target_path': 'D:/AAA/lianghua/data/market/market.db'})

    def test_factor_job_submit_status_and_result_flow(self):
        with patch('app.models.db.init_market_db', lambda: None), \
             patch('app.models.db.init_biz_db', lambda: None), \
             patch('app.core.scheduler.init_scheduler', lambda: None), \
             patch('app.core.jobs.get_job_manager', return_value=self.manager), \
             patch('app.api.jobs.get_job_manager', return_value=self.manager), \
             patch('app.core.job_handlers.register_job_handlers', side_effect=self.register_handlers):
            with TestClient(create_app()) as client:
                response = client.post('/api/jobs/backtest/factor', json={
                    'start_date': '2023-01-01',
                    'end_date': '2024-12-31',
                    'pool_codes': ['sh.600000'],
                    'script': 'def score_stocks(histories, context):\n    return {}'
                })
                self.assertEqual(response.status_code, 200)
                job_id = response.json()['data']['job_id']

                status_data = None
                for _ in range(20):
                    status_resp = client.get(f'/api/jobs/{job_id}')
                    status_data = status_resp.json()['data']
                    if status_data['status'] == 'success':
                        break
                    time.sleep(0.05)

                self.assertEqual(status_data['status'], 'success')
                result_resp = client.get(f'/api/jobs/{job_id}/result')
                self.assertEqual(result_resp.json()['data']['metrics']['final_equity'], 111111.0)


if __name__ == '__main__':
    unittest.main()
