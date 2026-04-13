import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.jobs import JobCancelledError, JobManager


class JobCancelAndArtifactTests(unittest.TestCase):
    def setUp(self):
        db_tmp = tempfile.NamedTemporaryFile(delete=False)
        db_tmp.close()
        self.db_path = db_tmp.name
        self.artifacts_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        for path in sorted(self.artifacts_dir.rglob('*'), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        if self.artifacts_dir.exists():
            self.artifacts_dir.rmdir()

    def make_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def make_manager(self):
        return JobManager(db_factory=self.make_conn, artifacts_root=self.artifacts_dir)

    def test_cancel_queued_job_marks_it_cancelled_before_execution(self):
        manager = self.make_manager()
        manager.register('echo', lambda ctx: {'value': 1})

        with patch('app.core.jobs.threading.Thread.start', lambda self: None):
            job_id = manager.submit('echo', {'value': 1}, run_async=True)

        cancelled = manager.cancel(job_id)
        job = manager.get_job(job_id)

        self.assertTrue(cancelled)
        self.assertEqual(job['status'], 'cancelled')
        self.assertEqual(job['progress']['message'], 'cancelled')

    def test_running_job_honors_cancel_request(self):
        manager = self.make_manager()
        started = threading.Event()

        def slow_handler(ctx):
            started.set()
            while True:
                ctx.raise_if_cancelled()
                time.sleep(0.02)

        manager.register('slow', slow_handler)
        job_id = manager.submit('slow', {}, run_async=True)

        self.assertTrue(started.wait(timeout=2))
        self.assertTrue(manager.cancel(job_id))

        for _ in range(100):
            job = manager.get_job(job_id)
            if job['status'] == 'cancelled':
                break
            time.sleep(0.02)
        else:
            self.fail('job did not become cancelled')

        self.assertEqual(job['status'], 'cancelled')

    def test_job_persists_summary_and_artifacts(self):
        manager = self.make_manager()

        def artifact_handler(ctx):
            ctx.set_summary({'records': 2})
            ctx.write_json_artifact('summary.json', {'records': 2})
            ctx.write_text_artifact('logs.txt', 'hello artifact')
            return {'result': 'ok'}

        manager.register('artifact', artifact_handler)
        job_id = manager.submit('artifact', {}, run_async=False)

        job = manager.get_job(job_id)
        result = manager.get_job_result(job_id)
        artifacts = manager.get_job_artifacts(job_id)

        self.assertEqual(job['summary']['records'], 2)
        self.assertEqual(result['result'], 'ok')
        self.assertEqual(len(artifacts), 2)
        self.assertTrue(any(item['name'] == 'summary.json' for item in artifacts))
        self.assertTrue((self.artifacts_dir / job_id / 'summary.json').exists())
        self.assertTrue((self.artifacts_dir / job_id / 'logs.txt').exists())


if __name__ == '__main__':
    unittest.main()
