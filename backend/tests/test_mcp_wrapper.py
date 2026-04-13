import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.mcp_server import (
    cancel_job_tool,
    get_job_artifacts_tool,
    get_job_logs_tool,
    get_job_result_tool,
    get_job_status_tool,
    submit_factor_backtest_tool,
)


class MCPWrapperTests(unittest.TestCase):
    def make_response(self, payload):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = payload
        return response

    def make_client(self):
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        return client

    def test_submit_factor_backtest_tool_returns_enveloped_job(self):
        async def run_test():
            client = self.make_client()
            client.post.return_value = self.make_response({'data': {'job_id': 'job_123', 'status': 'queued'}})

            with patch('app.mcp_server.httpx.AsyncClient', return_value=client):
                result = await submit_factor_backtest_tool(
                    base_url='http://127.0.0.1:8000',
                    strategy_id='custom_factor_script',
                    start_date='2023-01-01',
                    end_date='2024-12-31',
                    pool_codes=['sh.600000'],
                )

            self.assertEqual(result, {
                'ok': True,
                'data': {
                    'job': {
                        'id': 'job_123',
                        'status': 'queued',
                    }
                },
                'error': None,
            })
            client.post.assert_awaited()

        asyncio.run(run_test())

    def test_get_job_status_tool_returns_enveloped_job(self):
        async def run_test():
            client = self.make_client()
            client.get.return_value = self.make_response({
                'data': {
                    'id': 'job_123',
                    'status': 'running',
                    'progress': {'percent': 20, 'message': 'loading'},
                }
            })

            with patch('app.mcp_server.httpx.AsyncClient', return_value=client):
                result = await get_job_status_tool(base_url='http://127.0.0.1:8000', job_id='job_123')

            self.assertTrue(result['ok'])
            self.assertEqual(result['data']['job']['id'], 'job_123')
            self.assertEqual(result['data']['job']['status'], 'running')
            client.get.assert_awaited()

        asyncio.run(run_test())

    def test_get_job_result_tool_returns_enveloped_result(self):
        async def run_test():
            client = self.make_client()
            client.get.side_effect = [
                self.make_response({'data': {'id': 'job_123', 'status': 'success'}}),
                self.make_response({'data': {'metrics': {'final_equity': 123456.78}}}),
            ]

            with patch('app.mcp_server.httpx.AsyncClient', return_value=client):
                result = await get_job_result_tool(base_url='http://127.0.0.1:8000', job_id='job_123')

            self.assertTrue(result['ok'])
            self.assertEqual(result['data']['result']['metrics']['final_equity'], 123456.78)
            self.assertGreaterEqual(client.get.await_count, 2)

        asyncio.run(run_test())

    def test_get_job_artifacts_tool_returns_enveloped_artifacts(self):
        async def run_test():
            client = self.make_client()
            client.get.side_effect = [
                self.make_response({'data': {'id': 'job_123', 'status': 'success'}}),
                self.make_response({'data': {'artifacts': [{'name': 'summary.json'}]}}),
            ]

            with patch('app.mcp_server.httpx.AsyncClient', return_value=client):
                result = await get_job_artifacts_tool(base_url='http://127.0.0.1:8000', job_id='job_123')

            self.assertTrue(result['ok'])
            self.assertEqual(result['data']['artifacts'][0]['name'], 'summary.json')
            self.assertGreaterEqual(client.get.await_count, 2)

        asyncio.run(run_test())

    def test_get_job_logs_tool_returns_enveloped_logs(self):
        async def run_test():
            client = self.make_client()
            client.get.side_effect = [
                self.make_response({'data': {'id': 'job_123', 'status': 'success'}}),
                self.make_response({'data': {'logs': ['line-1', 'line-2']}}),
            ]

            with patch('app.mcp_server.httpx.AsyncClient', return_value=client):
                result = await get_job_logs_tool(base_url='http://127.0.0.1:8000', job_id='job_123')

            self.assertTrue(result['ok'])
            self.assertEqual(result['data']['logs'], ['line-1', 'line-2'])
            self.assertGreaterEqual(client.get.await_count, 2)

        asyncio.run(run_test())

    def test_cancel_job_tool_returns_enveloped_job(self):
        async def run_test():
            client = self.make_client()
            client.get.side_effect = [
                self.make_response({'data': {'id': 'job_123', 'status': 'running'}}),
                self.make_response({'data': {'id': 'job_123', 'status': 'cancel_requested'}}),
            ]
            client.post.return_value = self.make_response({'data': {'job_id': 'job_123', 'cancelled': True}})

            with patch('app.mcp_server.httpx.AsyncClient', return_value=client):
                result = await cancel_job_tool(base_url='http://127.0.0.1:8000', job_id='job_123')

            self.assertTrue(result['ok'])
            self.assertEqual(result['data']['job']['id'], 'job_123')
            self.assertEqual(result['data']['job']['status'], 'cancel_requested')
            client.post.assert_awaited()

        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()
