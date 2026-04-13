import base64
import json
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.jobs import get_job_manager

router = APIRouter()


class FactorJobRequest(BaseModel):
    strategy_id: Optional[str] = None
    script: Optional[str] = None
    factor_configs: list[dict] = []
    top_n: int = 10
    start_date: str
    end_date: str
    capital: float = 100000
    rebalance: str = "monthly"
    rebalance_dates: list[str] = []
    pool_codes: Optional[list[str]] = None
    script_timeout_seconds: Optional[float] = Field(default=None, gt=0)
    callback_url: Optional[str] = None
    callback_secret: Optional[str] = None


class DataImportDBRequest(BaseModel):
    source_path: str
    replace_existing: bool = True
    callback_url: Optional[str] = None
    callback_secret: Optional[str] = None


class DataUpdateJobRequest(BaseModel):
    mode: str = 'incremental'
    callback_url: Optional[str] = None
    callback_secret: Optional[str] = None


@router.post('/backtest/factor')
def submit_factor_job(request: FactorJobRequest):
    manager = get_job_manager()
    payload = request.model_dump(exclude={'callback_url', 'callback_secret'})
    callback = None
    if request.callback_url:
        callback = {'url': request.callback_url, 'secret': request.callback_secret}
    job_id = manager.submit('factor_backtest', payload, callback=callback)
    return {'data': {'job_id': job_id, 'status': 'queued'}}


@router.post('/data/import-db')
def submit_data_import_job(request: DataImportDBRequest):
    manager = get_job_manager()
    payload = request.model_dump(exclude={'callback_url', 'callback_secret'})
    callback = None
    if request.callback_url:
        callback = {'url': request.callback_url, 'secret': request.callback_secret}
    job_id = manager.submit('data_import_db', payload, callback=callback)
    return {'data': {'job_id': job_id, 'status': 'queued'}}


@router.post('/data/update')
def submit_data_update_job(request: DataUpdateJobRequest):
    manager = get_job_manager()
    payload = request.model_dump(exclude={'callback_url', 'callback_secret'})
    callback = None
    if request.callback_url:
        callback = {'url': request.callback_url, 'secret': request.callback_secret}
    job_id = manager.submit('data_update', payload, callback=callback)
    return {'data': {'job_id': job_id, 'status': 'queued'}}


@router.get('/{job_id}')
def get_job_status(job_id: str):
    job = get_job_manager().get_job(job_id)
    if not job:
        return {'error': '任务不存在'}
    return {'data': job}


@router.get('/{job_id}/result')
def get_job_result(job_id: str):
    result = get_job_manager().get_job_result(job_id)
    if result is None:
        return {'error': '结果不存在'}
    return {'data': result}


@router.get('/{job_id}/logs')
def get_job_logs(job_id: str):
    logs = get_job_manager().get_job_logs(job_id)
    return {'data': {'logs': logs}}


@router.get('/{job_id}/artifacts')
def get_job_artifacts(job_id: str):
    artifacts = get_job_manager().get_job_artifacts(job_id)
    return {'data': {'artifacts': artifacts}}


@router.get('/{job_id}/artifacts/{artifact_name}')
def get_job_artifact(job_id: str, artifact_name: str):
    meta, content = get_job_manager().read_job_artifact(job_id, artifact_name)
    if not meta:
        return {'error': 'artifact 不存在'}

    if meta['mime_type'] == 'application/json':
        parsed = json.loads(content.decode('utf-8'))
    elif meta['mime_type'].startswith('text/'):
        parsed = content.decode('utf-8')
    else:
        parsed = base64.b64encode(content).decode('ascii')

    return {'data': {**meta, 'content': parsed}}


@router.post('/{job_id}/cancel')
def cancel_job(job_id: str):
    cancelled = get_job_manager().cancel(job_id)
    return {'data': {'job_id': job_id, 'cancelled': cancelled}}
