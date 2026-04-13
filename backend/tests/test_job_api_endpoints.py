import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.jobs import (
    DataImportDBRequest,
    DataUpdateJobRequest,
    FactorJobRequest,
    cancel_job,
    get_job_artifact,
    get_job_artifacts,
    get_job_logs,
    get_job_result,
    get_job_status,
    submit_data_import_job,
    submit_data_update_job,
    submit_factor_job,
)


class FakeManager:
    def __init__(self):
        self.calls = []

    def submit(self, job_type, payload, callback=None, run_async=True):
        self.calls.append({
            'job_type': job_type,
            'payload': payload,
            'callback': callback,
            'run_async': run_async,
        })
        return 'job_test_1'

    def cancel(self, job_id):
        self.calls.append({'cancel': job_id})
        return True

    def get_job(self, job_id):
        return {'id': job_id, 'status': 'running', 'progress': {'percent': 20, 'message': 'loading'}, 'summary': {'rows': 2}, 'artifacts': [{'name': 'summary.json', 'mime_type': 'application/json'}]}

    def get_job_result(self, job_id):
        return {'metrics': {'final_equity': 123456.78}, '_artifacts': [{'name': 'summary.json'}]}

    def get_job_logs(self, job_id):
        return ['line-1', 'line-2']

    def get_job_artifacts(self, job_id):
        return [{'name': 'summary.json', 'mime_type': 'application/json'}]

    def read_job_artifact(self, job_id, artifact_name):
        return ({'name': artifact_name, 'mime_type': 'application/json'}, b'{"rows": 2}')


class JobApiEndpointTests(unittest.TestCase):
    def test_submit_factor_job_enqueues_factor_backtest_with_callback(self):
        manager = FakeManager()
        request = FactorJobRequest(
            strategy_id='custom_factor_script',
            start_date='2023-01-01',
            end_date='2024-12-31',
            pool_codes=['sh.600000'],
            callback_url='http://nova.local/webhook',
            callback_secret='secret-123',
        )

        with patch('app.api.jobs.get_job_manager', return_value=manager):
            response = submit_factor_job(request)

        self.assertEqual(response['data']['job_id'], 'job_test_1')
        self.assertEqual(manager.calls[0]['job_type'], 'factor_backtest')
        self.assertEqual(manager.calls[0]['payload']['strategy_id'], 'custom_factor_script')
        self.assertEqual(manager.calls[0]['callback']['url'], 'http://nova.local/webhook')

    def test_submit_data_import_job_enqueues_import_task(self):
        manager = FakeManager()
        request = DataImportDBRequest(source_path='D:/AAA/seed/market.db', replace_existing=True)

        with patch('app.api.jobs.get_job_manager', return_value=manager):
            response = submit_data_import_job(request)

        self.assertEqual(response['data']['job_id'], 'job_test_1')
        self.assertEqual(manager.calls[0]['job_type'], 'data_import_db')
        self.assertEqual(manager.calls[0]['payload']['source_path'], 'D:/AAA/seed/market.db')

    def test_submit_data_update_job_enqueues_update_task(self):
        manager = FakeManager()
        request = DataUpdateJobRequest(mode='incremental')

        with patch('app.api.jobs.get_job_manager', return_value=manager):
            response = submit_data_update_job(request)

        self.assertEqual(response['data']['job_id'], 'job_test_1')
        self.assertEqual(manager.calls[0]['job_type'], 'data_update')
        self.assertEqual(manager.calls[0]['payload']['mode'], 'incremental')

    def test_job_query_endpoints_return_status_result_logs_and_artifacts(self):
        manager = FakeManager()
        with patch('app.api.jobs.get_job_manager', return_value=manager):
            status = get_job_status('job_test_1')
            result = get_job_result('job_test_1')
            logs = get_job_logs('job_test_1')
            artifacts = get_job_artifacts('job_test_1')
            artifact = get_job_artifact('job_test_1', 'summary.json')

        self.assertEqual(status['data']['status'], 'running')
        self.assertEqual(status['data']['summary']['rows'], 2)
        self.assertEqual(result['data']['metrics']['final_equity'], 123456.78)
        self.assertEqual(logs['data']['logs'], ['line-1', 'line-2'])
        self.assertEqual(artifacts['data']['artifacts'][0]['name'], 'summary.json')
        self.assertEqual(artifact['data']['name'], 'summary.json')

    def test_get_job_result_returns_structured_terminal_payload(self):
        manager = FakeManager()
        manager.get_job_result = lambda job_id: {'status': 'timeout', 'error': {'code': 'script_timeout', 'message': 'script timeout'}}

        with patch('app.api.jobs.get_job_manager', return_value=manager):
            result = get_job_result('job_test_1')

        self.assertEqual(result['data']['status'], 'timeout')
        self.assertEqual(result['data']['error']['code'], 'script_timeout')

    def test_cancel_job_endpoint_forwards_to_manager(self):
        manager = FakeManager()
        with patch('app.api.jobs.get_job_manager', return_value=manager):
            response = cancel_job('job_test_1')

        self.assertEqual(response['data']['job_id'], 'job_test_1')
        self.assertTrue(response['data']['cancelled'])


if __name__ == '__main__':
    unittest.main()
