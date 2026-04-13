from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

mcp = FastMCP('fuxi-mcp', json_response=True)


class MCPError(BaseModel):
    code: str
    message: str


class JobData(BaseModel):
    job: dict[str, Any]


class ResultData(BaseModel):
    result: dict[str, Any]


class ArtifactsData(BaseModel):
    artifacts: list[dict[str, Any]]


class LogsData(BaseModel):
    logs: list[str]


class JobResponse(BaseModel):
    ok: bool
    data: JobData | None = None
    error: MCPError | None = None


class ResultResponse(BaseModel):
    ok: bool
    data: ResultData | None = None
    error: MCPError | None = None


class ArtifactsResponse(BaseModel):
    ok: bool
    data: ArtifactsData | None = None
    error: MCPError | None = None


class LogsResponse(BaseModel):
    ok: bool
    data: LogsData | None = None
    error: MCPError | None = None


class MCPToolError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


async def submit_factor_backtest_tool(
    base_url: str,
    start_date: str,
    end_date: str,
    strategy_id: str | None = None,
    script: str | None = None,
    factor_configs: list[dict] | None = None,
    top_n: int = 10,
    capital: float = 100000,
    rebalance: str = 'monthly',
    pool_codes: list[str] | None = None,
    callback_url: str | None = None,
    callback_secret: str | None = None,
    script_timeout_seconds: float | None = None,
):
    if script_timeout_seconds is not None and script_timeout_seconds <= 0:
        return _error_response(JobResponse, 'invalid_arguments', 'script_timeout_seconds must be greater than 0')

    payload = {
        'strategy_id': strategy_id,
        'script': script,
        'factor_configs': factor_configs or [],
        'top_n': top_n,
        'start_date': start_date,
        'end_date': end_date,
        'capital': capital,
        'rebalance': rebalance,
        'pool_codes': pool_codes,
        'callback_url': callback_url,
        'callback_secret': callback_secret,
        'script_timeout_seconds': script_timeout_seconds,
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response_payload = await _request_json(client, 'POST', f'{base_url}/api/jobs/backtest/factor', payload)
            submission = _extract_api_data(response_payload, default_error_code='upstream_invalid_response')
            return _job_success(_submission_to_job(submission))
    except MCPToolError as exc:
        return _error_response(JobResponse, exc.code, exc.message)


async def get_job_status_tool(base_url: str, job_id: str):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            job = await _fetch_job_status(client, base_url, job_id)
            return _job_success(job)
    except MCPToolError as exc:
        return _error_response(JobResponse, exc.code, exc.message)


async def get_job_result_tool(base_url: str, job_id: str):
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            await _fetch_job_status(client, base_url, job_id)
            response_payload = await _request_json(client, 'GET', f'{base_url}/api/jobs/{job_id}/result')
            result = _extract_api_data(response_payload, default_error_code='upstream_invalid_response')
            if not isinstance(result, dict):
                raise MCPToolError('upstream_invalid_response', 'Upstream returned invalid result payload')
            return _result_success(result)
    except MCPToolError as exc:
        return _error_response(ResultResponse, exc.code, exc.message)


async def get_job_artifacts_tool(base_url: str, job_id: str):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            await _fetch_job_status(client, base_url, job_id)
            response_payload = await _request_json(client, 'GET', f'{base_url}/api/jobs/{job_id}/artifacts')
            artifacts_payload = _extract_api_data(response_payload, default_error_code='upstream_invalid_response')
            if not isinstance(artifacts_payload, dict) or not isinstance(artifacts_payload.get('artifacts'), list):
                raise MCPToolError('upstream_invalid_response', 'Upstream returned invalid artifacts payload')
            return _artifacts_success(artifacts_payload['artifacts'])
    except MCPToolError as exc:
        return _error_response(ArtifactsResponse, exc.code, exc.message)


async def get_job_logs_tool(base_url: str, job_id: str):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            await _fetch_job_status(client, base_url, job_id)
            response_payload = await _request_json(client, 'GET', f'{base_url}/api/jobs/{job_id}/logs')
            logs_payload = _extract_api_data(response_payload, default_error_code='upstream_invalid_response')
            if not isinstance(logs_payload, dict) or not isinstance(logs_payload.get('logs'), list):
                raise MCPToolError('upstream_invalid_response', 'Upstream returned invalid logs payload')
            return _logs_success(logs_payload['logs'])
    except MCPToolError as exc:
        return _error_response(LogsResponse, exc.code, exc.message)


async def cancel_job_tool(base_url: str, job_id: str):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            await _fetch_job_status(client, base_url, job_id)
            response_payload = await _request_json(client, 'POST', f'{base_url}/api/jobs/{job_id}/cancel')
            cancel_payload = _extract_api_data(response_payload, default_error_code='job_cancel_failed')
            if not isinstance(cancel_payload, dict) or cancel_payload.get('cancelled') is not True:
                raise MCPToolError('job_cancel_failed', f'Failed to cancel job {job_id}')
            job = await _fetch_job_status(client, base_url, job_id)
            return _job_success(job)
    except MCPToolError as exc:
        return _error_response(JobResponse, exc.code, exc.message)


async def submit_data_update_tool(base_url: str, mode: str = 'incremental', callback_url: str | None = None, callback_secret: str | None = None):
    payload = {'mode': mode, 'callback_url': callback_url, 'callback_secret': callback_secret}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response_payload = await _request_json(client, 'POST', f'{base_url}/api/jobs/data/update', payload)
            submission = _extract_api_data(response_payload, default_error_code='upstream_invalid_response')
            return _job_success(_submission_to_job(submission))
    except MCPToolError as exc:
        return _error_response(JobResponse, exc.code, exc.message)


async def submit_data_import_tool(base_url: str, source_path: str, replace_existing: bool = True, callback_url: str | None = None, callback_secret: str | None = None):
    payload = {
        'source_path': source_path,
        'replace_existing': replace_existing,
        'callback_url': callback_url,
        'callback_secret': callback_secret,
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response_payload = await _request_json(client, 'POST', f'{base_url}/api/jobs/data/import-db', payload)
            submission = _extract_api_data(response_payload, default_error_code='upstream_invalid_response')
            return _job_success(_submission_to_job(submission))
    except MCPToolError as exc:
        return _error_response(JobResponse, exc.code, exc.message)


async def _request_json(client: httpx.AsyncClient, method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        if method == 'GET':
            response = await client.get(url)
        elif method == 'POST':
            response = await client.post(url, json=payload)
        else:
            raise MCPToolError('upstream_invalid_response', f'Unsupported HTTP method: {method}')
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise MCPToolError(*_extract_http_error(exc)) from exc
    except httpx.HTTPError as exc:
        raise MCPToolError('http_request_failed', str(exc)) from exc

    try:
        parsed = response.json()
    except ValueError as exc:
        raise MCPToolError('upstream_invalid_response', f'Upstream returned non-JSON response: {exc}') from exc

    if not isinstance(parsed, dict):
        raise MCPToolError('upstream_invalid_response', 'Upstream returned non-object JSON payload')
    return parsed


async def _fetch_job_status(client: httpx.AsyncClient, base_url: str, job_id: str) -> dict[str, Any]:
    response_payload = await _request_json(client, 'GET', f'{base_url}/api/jobs/{job_id}')
    job_payload = _extract_api_data(response_payload, default_error_code='job_not_found')
    return _coerce_job_payload(job_payload)


def _extract_api_data(payload: dict[str, Any], default_error_code: str) -> Any:
    if 'data' in payload:
        return payload['data']
    if 'error' in payload:
        raise MCPToolError(_extract_error_code(payload['error'], default_error_code), _extract_error_message(payload['error']))
    if 'detail' in payload:
        raise MCPToolError(_extract_error_code(payload['detail'], default_error_code), _extract_error_message(payload['detail']))
    raise MCPToolError('upstream_invalid_response', 'Upstream response missing both data and error fields')


def _extract_http_error(exc: httpx.HTTPStatusError) -> tuple[str, str]:
    response = exc.response
    try:
        payload = response.json()
    except ValueError:
        return 'http_request_failed', f'HTTP {response.status_code}: {response.text}'

    if isinstance(payload, dict):
        if 'detail' in payload:
            detail = payload['detail']
            return _extract_error_code(detail, 'http_request_failed'), _extract_error_message(detail)
        if 'error' in payload:
            error = payload['error']
            return _extract_error_code(error, 'http_request_failed'), _extract_error_message(error)

    return 'http_request_failed', f'HTTP {response.status_code}: {response.text}'


def _extract_error_code(payload: Any, default: str) -> str:
    if isinstance(payload, dict):
        code = payload.get('code')
        if isinstance(code, str) and code:
            return code
    return default


def _extract_error_message(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ('message', 'detail', 'error'):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        return str(payload)
    return str(payload)


def _submission_to_job(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise MCPToolError('upstream_invalid_response', 'Upstream returned invalid submission payload')
    job_id = payload.get('job_id')
    status = payload.get('status')
    if not isinstance(job_id, str) or not isinstance(status, str):
        raise MCPToolError('upstream_invalid_response', 'Upstream submission payload missing job_id/status')
    return {'id': job_id, 'status': status}


def _coerce_job_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise MCPToolError('upstream_invalid_response', 'Upstream returned invalid job payload')
    job_id = payload.get('id')
    status = payload.get('status')
    if not isinstance(job_id, str) or not isinstance(status, str):
        raise MCPToolError('upstream_invalid_response', 'Upstream returned invalid job payload: missing id/status')
    return payload


def _job_success(job: dict[str, Any]) -> dict[str, Any]:
    return {
        'ok': True,
        'data': {
            'job': job,
        },
        'error': None,
    }



def _result_success(result: dict[str, Any]) -> dict[str, Any]:
    return {
        'ok': True,
        'data': {
            'result': result,
        },
        'error': None,
    }



def _artifacts_success(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'ok': True,
        'data': {
            'artifacts': artifacts,
        },
        'error': None,
    }



def _logs_success(logs: list[str]) -> dict[str, Any]:
    return {
        'ok': True,
        'data': {
            'logs': logs,
        },
        'error': None,
    }



def _error_response(response_model: type[BaseModel], code: str, message: str) -> dict[str, Any]:
    return {
        'ok': False,
        'data': None,
        'error': MCPError(code=code, message=message).model_dump(mode='json'),
    }


@mcp.tool(name='submit_factor_backtest')
async def submit_factor_backtest_mcp(
    base_url: str,
    start_date: str,
    end_date: str,
    strategy_id: str | None = None,
    script: str | None = None,
    factor_configs: list[dict] | None = None,
    top_n: int = 10,
    capital: float = 100000,
    rebalance: str = 'monthly',
    pool_codes: list[str] | None = None,
    callback_url: str | None = None,
    callback_secret: str | None = None,
    script_timeout_seconds: float | None = None,
) -> JobResponse:
    return await submit_factor_backtest_tool(base_url, start_date, end_date, strategy_id, script, factor_configs, top_n, capital, rebalance, pool_codes, callback_url, callback_secret, script_timeout_seconds)


@mcp.tool(name='get_job_status')
async def get_job_status_mcp(base_url: str, job_id: str) -> JobResponse:
    return await get_job_status_tool(base_url, job_id)


@mcp.tool(name='get_job_result')
async def get_job_result_mcp(base_url: str, job_id: str) -> ResultResponse:
    return await get_job_result_tool(base_url, job_id)


@mcp.tool(name='get_job_artifacts')
async def get_job_artifacts_mcp(base_url: str, job_id: str) -> ArtifactsResponse:
    return await get_job_artifacts_tool(base_url, job_id)


@mcp.tool(name='get_job_logs')
async def get_job_logs_mcp(base_url: str, job_id: str) -> LogsResponse:
    return await get_job_logs_tool(base_url, job_id)


@mcp.tool(name='cancel_job')
async def cancel_job_mcp(base_url: str, job_id: str) -> JobResponse:
    return await cancel_job_tool(base_url, job_id)


@mcp.tool(name='submit_data_update')
async def submit_data_update_mcp(base_url: str, mode: str = 'incremental', callback_url: str | None = None, callback_secret: str | None = None) -> JobResponse:
    return await submit_data_update_tool(base_url, mode, callback_url, callback_secret)


@mcp.tool(name='submit_data_import')
async def submit_data_import_mcp(base_url: str, source_path: str, replace_existing: bool = True, callback_url: str | None = None, callback_secret: str | None = None) -> JobResponse:
    return await submit_data_import_tool(base_url, source_path, replace_existing, callback_url, callback_secret)



def main():
    mcp.run()


if __name__ == '__main__':
    main()
