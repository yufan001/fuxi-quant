from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def build_steps(host: str = "127.0.0.1", port: int = 8000, download_mode: str = "full") -> list[dict[str, str]]:
    return [
        {"name": "prepare data directories", "command": "mkdir -p data/market data/db"},
        {"name": "create virtualenv", "command": "python3 -m venv .venv"},
        {"name": "install backend requirements", "command": ".venv/bin/python -m pip install -r backend/requirements.txt"},
        {
            "name": "initialize sqlite databases",
            "command": "PYTHONPATH=backend .venv/bin/python -c \"from app.models.db import init_market_db, init_biz_db; init_market_db(); init_biz_db()\"",
        },
        {
            "name": "download market data from baostock",
            "command": f"PYTHONPATH=backend .venv/bin/python -m app.data.downloader --mode {download_mode}",
        },
        {
            "name": "start api server",
            "command": f".venv/bin/python -m uvicorn app.main:app --host {host} --port {port} --app-dir backend",
        },
    ]


def run_steps(steps: list[dict[str, str]], dry_run: bool = False) -> None:
    for step in steps:
        print(f"[step] {step['name']}")
        print(step["command"])
        if dry_run:
            continue
        subprocess.run(step["command"], shell=True, cwd=REPO_ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap Fuxi on macOS")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--download-mode", default="full", choices=["full", "update", "test"])
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_steps(build_steps(host=args.host, port=args.port, download_mode=args.download_mode), dry_run=args.dry_run)


if __name__ == "__main__":
    main()
