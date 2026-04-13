import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.jobs import JobManager


class AsyncJobTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        self.db_path = tmp.name

    def tearDown(self):
        os.unlink(self.db_path)

    def make_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def test_submit_job_persists_status_and_result(self):
        manager = JobManager(db_factory=self.make_conn)
        manager.register('echo', lambda ctx: {'value': ctx.payload['value']})

        job_id = manager.submit('echo', {'value': 42}, run_async=False)
        job = manager.get_job(job_id)
        result = manager.get_job_result(job_id)

        self.assertEqual(job['status'], 'success')
        self.assertEqual(result['value'], 42)

    def test_submit_job_sends_signed_webhook_on_completion(self):
        captured = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            captured['url'] = url
            captured['json'] = json
            captured['headers'] = headers
            class Response:
                status_code = 200
            return Response()

        manager = JobManager(db_factory=self.make_conn)
        manager.register('echo', lambda ctx: {'value': 'done'})

        with patch('app.core.jobs.httpx.post', side_effect=fake_post):
            job_id = manager.submit(
                'echo',
                {'value': 'done'},
                callback={'url': 'http://nova.local/webhook', 'secret': 'test-secret'},
                run_async=False,
            )

        self.assertEqual(captured['url'], 'http://nova.local/webhook')
        self.assertEqual(captured['json']['job_id'], job_id)
        self.assertEqual(captured['json']['status'], 'success')
        self.assertIn('X-Fuxi-Signature', captured['headers'])
        self.assertIn('X-Fuxi-Timestamp', captured['headers'])


if __name__ == '__main__':
    unittest.main()
