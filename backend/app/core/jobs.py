import hashlib
import hmac
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.core.config import BIZ_DB_PATH
from app.models.db import get_biz_db


TERMINAL_STATUSES = {'success', 'failed', 'cancelled'}


class JobCancelledError(Exception):
    pass


@dataclass
class JobContext:
    job_id: str
    payload: dict
    _db_factory: callable
    artifacts_root: Path
    progress: dict = field(default_factory=lambda: {'percent': 0, 'message': 'queued'})
    logs: list[str] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    artifacts: list[dict] = field(default_factory=list)

    @property
    def artifact_dir(self) -> Path:
        path = self.artifacts_root / self.job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def log(self, message: str):
        self.logs.append(message)
        self._persist()

    def set_progress(self, percent: float, message: str):
        self.progress = {'percent': percent, 'message': message}
        self._persist()

    def set_summary(self, summary: dict[str, Any]):
        self.summary = summary
        self._persist()

    def is_cancel_requested(self) -> bool:
        conn = self._db_factory()
        row = conn.execute('SELECT cancel_requested FROM jobs WHERE id = ?', (self.job_id,)).fetchone()
        conn.close()
        return bool(row and row['cancel_requested'])

    def raise_if_cancelled(self):
        if self.is_cancel_requested():
            raise JobCancelledError(f'Job {self.job_id} cancelled')

    def write_artifact(self, name: str, data: bytes | str | dict | list, mime_type: str) -> dict[str, Any]:
        safe_name = Path(name).name
        target = self.artifact_dir / safe_name
        if isinstance(data, (dict, list)):
            raw = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        elif isinstance(data, str):
            raw = data.encode('utf-8')
        else:
            raw = data
        target.write_bytes(raw)
        entry = {
            'name': safe_name,
            'path': str(target),
            'mime_type': mime_type,
            'size_bytes': target.stat().st_size,
        }
        self.artifacts = [item for item in self.artifacts if item['name'] != safe_name]
        self.artifacts.append(entry)
        self._persist()
        return entry

    def write_json_artifact(self, name: str, data: dict | list) -> dict[str, Any]:
        return self.write_artifact(name, data, 'application/json')

    def write_text_artifact(self, name: str, text: str) -> dict[str, Any]:
        return self.write_artifact(name, text, 'text/plain')

    def _persist(self):
        conn = self._db_factory()
        conn.execute(
            'UPDATE jobs SET progress_json = ?, logs_json = ?, summary_json = ?, artifact_json = ?, updated_at = ? WHERE id = ?',
            (
                json.dumps(self.progress, ensure_ascii=False),
                json.dumps(self.logs, ensure_ascii=False),
                json.dumps(self.summary, ensure_ascii=False),
                json.dumps(self.artifacts, ensure_ascii=False),
                _now(),
                self.job_id,
            ),
        )
        conn.commit()
        conn.close()


class JobManager:
    def __init__(self, db_factory=None, artifacts_root: Path | None = None):
        self.db_factory = db_factory or get_biz_db
        self.artifacts_root = artifacts_root or (BIZ_DB_PATH.parent / 'job_artifacts')
        self.handlers = {}
        self._ensure_tables()

    def _ensure_tables(self):
        conn = self.db_factory()
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                callback_json TEXT,
                progress_json TEXT DEFAULT '{}',
                result_json TEXT,
                logs_json TEXT DEFAULT '[]',
                error_text TEXT,
                cancel_requested INTEGER DEFAULT 0,
                artifact_json TEXT DEFAULT '[]',
                summary_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                updated_at TEXT NOT NULL
            )
            '''
        )
        existing = {row['name'] for row in conn.execute('PRAGMA table_info(jobs)').fetchall()}
        additions = {
            'cancel_requested': "ALTER TABLE jobs ADD COLUMN cancel_requested INTEGER DEFAULT 0",
            'artifact_json': "ALTER TABLE jobs ADD COLUMN artifact_json TEXT DEFAULT '[]'",
            'summary_json': "ALTER TABLE jobs ADD COLUMN summary_json TEXT DEFAULT '{}'",
        }
        for column, sql in additions.items():
            if column not in existing:
                conn.execute(sql)
        conn.commit()
        conn.close()

    def register(self, job_type: str, handler):
        self.handlers[job_type] = handler

    def submit(self, job_type: str, payload: dict, callback: dict | None = None, run_async: bool = True) -> str:
        if job_type not in self.handlers:
            raise ValueError(f'Unknown job type: {job_type}')

        job_id = f'job_{uuid.uuid4().hex[:12]}'
        now = _now()
        conn = self.db_factory()
        conn.execute(
            'INSERT INTO jobs (id, job_type, status, payload_json, callback_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (job_id, job_type, 'queued', json.dumps(payload, ensure_ascii=False), json.dumps(callback, ensure_ascii=False) if callback else None, now, now),
        )
        conn.commit()
        conn.close()

        if run_async:
            thread = threading.Thread(target=self._run_job, args=(job_id,), daemon=True)
            thread.start()
        else:
            self._run_job(job_id)
        return job_id

    def cancel(self, job_id: str) -> bool:
        conn = self.db_factory()
        row = conn.execute('SELECT status FROM jobs WHERE id = ?', (job_id,)).fetchone()
        if not row:
            conn.close()
            return False

        status = row['status']
        if status in TERMINAL_STATUSES:
            conn.close()
            return status == 'cancelled'

        if status == 'queued':
            conn.execute(
                'UPDATE jobs SET status = ?, cancel_requested = 1, progress_json = ?, finished_at = ?, updated_at = ? WHERE id = ?',
                ('cancelled', json.dumps({'percent': 100, 'message': 'cancelled'}, ensure_ascii=False), _now(), _now(), job_id),
            )
        else:
            conn.execute(
                'UPDATE jobs SET cancel_requested = 1, progress_json = ?, updated_at = ? WHERE id = ?',
                (json.dumps({'percent': 100, 'message': 'cancel_requested'}, ensure_ascii=False), _now(), job_id),
            )
        conn.commit()
        conn.close()
        return True

    def _run_job(self, job_id: str):
        conn = self.db_factory()
        row = conn.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
        if not row:
            conn.close()
            return
        if row['status'] == 'cancelled':
            conn.close()
            return

        payload = json.loads(row['payload_json'])
        callback = json.loads(row['callback_json']) if row['callback_json'] else None
        job_type = row['job_type']
        conn.execute(
            'UPDATE jobs SET status = ?, started_at = ?, progress_json = ?, updated_at = ? WHERE id = ?',
            ('running', _now(), json.dumps({'percent': 1, 'message': 'running'}, ensure_ascii=False), _now(), job_id),
        )
        conn.commit()
        conn.close()

        context = JobContext(job_id=job_id, payload=payload, _db_factory=self.db_factory, artifacts_root=self.artifacts_root)
        context.set_progress(5, 'running')

        try:
            result = self.handlers[job_type](context)
            context.raise_if_cancelled()
            conn = self.db_factory()
            conn.execute(
                'UPDATE jobs SET status = ?, result_json = ?, progress_json = ?, logs_json = ?, summary_json = ?, artifact_json = ?, finished_at = ?, updated_at = ? WHERE id = ?',
                (
                    'success',
                    json.dumps(result, ensure_ascii=False),
                    json.dumps({'percent': 100, 'message': 'success'}, ensure_ascii=False),
                    json.dumps(context.logs, ensure_ascii=False),
                    json.dumps(context.summary, ensure_ascii=False),
                    json.dumps(context.artifacts, ensure_ascii=False),
                    _now(),
                    _now(),
                    job_id,
                ),
            )
            conn.commit()
            conn.close()
            self._deliver_callback(job_id, job_type, callback, result=result, summary=context.summary, artifacts=context.artifacts)
        except JobCancelledError:
            conn = self.db_factory()
            conn.execute(
                'UPDATE jobs SET status = ?, progress_json = ?, logs_json = ?, summary_json = ?, artifact_json = ?, finished_at = ?, updated_at = ? WHERE id = ?',
                (
                    'cancelled',
                    json.dumps({'percent': 100, 'message': 'cancelled'}, ensure_ascii=False),
                    json.dumps(context.logs, ensure_ascii=False),
                    json.dumps(context.summary, ensure_ascii=False),
                    json.dumps(context.artifacts, ensure_ascii=False),
                    _now(),
                    _now(),
                    job_id,
                ),
            )
            conn.commit()
            conn.close()
            self._deliver_callback(job_id, job_type, callback, error='cancelled', summary=context.summary, artifacts=context.artifacts, status='cancelled')
        except Exception as exc:
            conn = self.db_factory()
            conn.execute(
                'UPDATE jobs SET status = ?, error_text = ?, progress_json = ?, logs_json = ?, summary_json = ?, artifact_json = ?, finished_at = ?, updated_at = ? WHERE id = ?',
                (
                    'failed',
                    str(exc),
                    json.dumps({'percent': 100, 'message': 'failed'}, ensure_ascii=False),
                    json.dumps(context.logs, ensure_ascii=False),
                    json.dumps(context.summary, ensure_ascii=False),
                    json.dumps(context.artifacts, ensure_ascii=False),
                    _now(),
                    _now(),
                    job_id,
                ),
            )
            conn.commit()
            conn.close()
            self._deliver_callback(job_id, job_type, callback, error=str(exc), summary=context.summary, artifacts=context.artifacts)

    def _deliver_callback(self, job_id: str, job_type: str, callback: dict | None, result: dict | None = None, error: str | None = None, summary: dict | None = None, artifacts: list[dict] | None = None, status: str | None = None):
        if not callback or not callback.get('url'):
            return
        payload = {
            'job_id': job_id,
            'job_type': job_type,
            'status': status or ('success' if error is None else 'failed'),
            'summary': summary or {},
            'artifacts': artifacts or [],
            'result': result,
            'error': error,
        }
        headers = {'Content-Type': 'application/json'}
        secret = callback.get('secret')
        if secret:
            timestamp = str(int(time.time()))
            body = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
            signature = hmac.new(secret.encode(), f'{timestamp}.{body}'.encode(), hashlib.sha256).hexdigest()
            headers['X-Fuxi-Timestamp'] = timestamp
            headers['X-Fuxi-Signature'] = signature
        httpx.post(callback['url'], json=payload, headers=headers, timeout=15)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        conn = self.db_factory()
        row = conn.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
        conn.close()
        if not row:
            return None
        return {
            'id': row['id'],
            'job_type': row['job_type'],
            'status': row['status'],
            'progress': json.loads(row['progress_json'] or '{}'),
            'summary': json.loads(row['summary_json'] or '{}'),
            'artifacts': json.loads(row['artifact_json'] or '[]'),
            'cancel_requested': bool(row['cancel_requested']),
            'error': row['error_text'],
            'created_at': row['created_at'],
            'started_at': row['started_at'],
            'finished_at': row['finished_at'],
        }

    def get_job_result(self, job_id: str) -> dict[str, Any] | None:
        conn = self.db_factory()
        row = conn.execute('SELECT result_json, summary_json, artifact_json FROM jobs WHERE id = ?', (job_id,)).fetchone()
        conn.close()
        if not row:
            return None
        payload = json.loads(row['result_json']) if row['result_json'] else {}
        payload['_summary'] = json.loads(row['summary_json'] or '{}')
        payload['_artifacts'] = json.loads(row['artifact_json'] or '[]')
        return payload

    def get_job_logs(self, job_id: str) -> list[str]:
        conn = self.db_factory()
        row = conn.execute('SELECT logs_json FROM jobs WHERE id = ?', (job_id,)).fetchone()
        conn.close()
        if not row or not row['logs_json']:
            return []
        return json.loads(row['logs_json'])

    def get_job_artifacts(self, job_id: str) -> list[dict[str, Any]]:
        conn = self.db_factory()
        row = conn.execute('SELECT artifact_json FROM jobs WHERE id = ?', (job_id,)).fetchone()
        conn.close()
        if not row or not row['artifact_json']:
            return []
        return json.loads(row['artifact_json'])

    def read_job_artifact(self, job_id: str, artifact_name: str) -> tuple[dict[str, Any], bytes] | tuple[None, None]:
        safe_name = Path(artifact_name).name
        for item in self.get_job_artifacts(job_id):
            if item['name'] == safe_name:
                path = Path(item['path'])
                if not path.exists():
                    return None, None
                return item, path.read_bytes()
        return None, None


_JOB_MANAGER = None


def get_job_manager() -> JobManager:
    global _JOB_MANAGER
    if _JOB_MANAGER is None:
        _JOB_MANAGER = JobManager()
    return _JOB_MANAGER


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
