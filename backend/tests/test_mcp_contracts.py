import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.mcp_server import cancel_job_tool, get_job_logs_tool, get_job_result_tool, get_job_status_tool, mcp


class MCPContractTests(unittest.TestCase):
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

    def test_registered_tools_publish_output_schemas(self):
        expected_names = {
            'submit_factor_backtest',
            'get_job_status',
            'get_job_result',
            'get_job_artifacts',
            'get_job_logs',
            'cancel_job',
            'submit_data_update',
            'submit_data_import',
        }

        actual = {
            tool.name: tool.output_schema
            for tool in mcp._tool_manager.list_tools()
            if tool.name in expected_names
        }

        self.assertEqual(set(actual), expected_names)
        for name, schema in actual.items():
            self.assertIsNotNone(schema, name)

    def test_get_job_status_tool_returns_structured_job_not_found_error(self):
        async def run_test():
            client = self.make_client()
            client.get.return_value = self.make_response({'error': '任务不存在'})

            with patch('app.mcp_server.httpx.AsyncClient', return_value=client):
                result = await get_job_status_tool(base_url='http://127.0.0.1:8000', job_id='job_missing')

            self.assertEqual(result, {
                'ok': False,
                'data': None,
                'error': {
                    'code': 'job_not_found',
                    'message': '任务不存在',
                },
            })

        asyncio.run(run_test())

    def test_cancel_job_tool_returns_job_cancel_failed_error_when_upstream_rejects_cancel(self):
        async def run_test():
            client = self.make_client()
            client.get.return_value = self.make_response({'data': {'id': 'job_123', 'status': 'running'}})
            client.post.return_value = self.make_response({'data': {'job_id': 'job_123', 'cancelled': False}})

            with patch('app.mcp_server.httpx.AsyncClient', return_value=client):
                result = await cancel_job_tool(base_url='http://127.0.0.1:8000', job_id='job_123')

            self.assertFalse(result['ok'])
            self.assertIsNone(result['data'])
            self.assertEqual(result['error']['code'], 'job_cancel_failed')

        asyncio.run(run_test())

    def test_get_job_logs_tool_returns_upstream_invalid_response_error_for_bad_payload(self):
        async def run_test():
            client = self.make_client()
            client.get.side_effect = [
                self.make_response({'data': {'id': 'job_123', 'status': 'success'}}),
                self.make_response({'unexpected': True}),
            ]

            with patch('app.mcp_server.httpx.AsyncClient', return_value=client):
                result = await get_job_logs_tool(base_url='http://127.0.0.1:8000', job_id='job_123')

            self.assertFalse(result['ok'])
            self.assertIsNone(result['data'])
            self.assertEqual(result['error']['code'], 'upstream_invalid_response')

        asyncio.run(run_test())

    def test_get_job_status_tool_returns_http_request_failed_on_transport_error(self):
        async def run_test():
            client = self.make_client()
            client.get.side_effect = httpx.ConnectError('boom')

            with patch('app.mcp_server.httpx.AsyncClient', return_value=client):
                result = await get_job_status_tool(base_url='http://127.0.0.1:8000', job_id='job_123')

            self.assertFalse(result['ok'])
            self.assertIsNone(result['data'])
            self.assertEqual(result['error']['code'], 'http_request_failed')
            self.assertIn('boom', result['error']['message'])

        asyncio.run(run_test())

    def test_get_job_status_tool_text_fallback_matches_structured_content(self):
        async def run_test():
            client = self.make_client()
            client.get.return_value = self.make_response({
                'data': {
                    'id': 'job_123',
                    'status': 'success',
                    'job_type': 'factor_backtest',
                    'progress': {'percent': 100, 'message': 'success'},
                }
            })

            tool = mcp._tool_manager.get_tool('get_job_status')
            with patch('app.mcp_server.httpx.AsyncClient', return_value=client):
                content, structured = await tool.run(
                    {'base_url': 'http://127.0.0.1:8000', 'job_id': 'job_123'},
                    convert_result=True,
                )

            self.assertEqual(len(content), 1)
            self.assertEqual(json.loads(content[0].text), structured)

        asyncio.run(run_test())

    def test_get_job_result_tool_returns_structured_timeout_payload(self):
        async def run_test():
            client = self.make_client()
            client.get.side_effect = [
                self.make_response({'data': {'id': 'job_123', 'status': 'failed'}}),
                self.make_response({'data': {'status': 'timeout', 'error': {'code': 'script_timeout', 'message': 'script timeout'}}}),
            ]

            with patch('app.mcp_server.httpx.AsyncClient', return_value=client):
                result = await get_job_result_tool(base_url='http://127.0.0.1:8000', job_id='job_123')

            self.assertTrue(result['ok'])
            self.assertEqual(result['data']['result']['status'], 'timeout')
            self.assertEqual(result['data']['result']['error']['code'], 'script_timeout')

        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()
