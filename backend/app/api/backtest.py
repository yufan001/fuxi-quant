import importlib
import json
import uuid
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.engine import BacktestEngine
from app.core.factor_runner import FactorScriptExecutionError, run_factor_job
from app.data.storage import MarketStorage
from app.models.db import get_market_db

router = APIRouter()

STRATEGY_MAP = {
    "ma_cross": ("app.strategies.tech.ma_cross", "MACrossStrategy"),
    "macd": ("app.strategies.tech.macd", "MACDStrategy"),
    "rsi": ("app.strategies.tech.rsi", "RSIStrategy"),
    "bollinger": ("app.strategies.tech.bollinger", "BollingerStrategy"),
    "platform_breakout": ("app.strategies.pattern.platform_breakout", "PlatformBreakoutStrategy"),
}


class BacktestConfig(BaseModel):
    strategy: str
    code: str
    start_date: str
    end_date: str
    capital: float = 100000
    params: Optional[dict] = None


class FactorBacktestRequest(BaseModel):
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


FACTOR_TEMPLATES = [
    {
        "id": "factor_low_pb_momentum",
        "name": "低PB + 动量",
        "type": "factor",
        "params": {
            "factor_configs": [
                {"key": "pb", "weight": 0.5},
                {"key": "momentum_20", "weight": 0.5},
            ],
            "top_n": 10,
            "rebalance": "monthly",
        },
        "description": "低估值与短期动量混合打分，做月度调仓",
    }
]


def _init_factor_backtest_table():
    conn = get_market_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS factor_backtest_runs (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            config_json TEXT NOT NULL,
            result_json TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    conn.close()


_init_factor_backtest_table()


def _resolve_factor_request(request: FactorBacktestRequest, conn) -> FactorBacktestRequest:
    payload = request.model_dump()
    strategy_id = payload.get("strategy_id")
    if strategy_id and not payload.get("script"):
        row = conn.execute("SELECT * FROM user_strategies WHERE id = ?", (strategy_id,)).fetchone()
        if row:
            params = json.loads(row["params"]) if row["params"] else {}
            payload["script"] = row["code"] or payload.get("script")
            if not payload.get("factor_configs"):
                payload["factor_configs"] = params.get("factor_configs", [])
            if payload.get("top_n") == 10 and params.get("top_n"):
                payload["top_n"] = params["top_n"]
            if payload.get("rebalance") == "monthly" and params.get("rebalance"):
                payload["rebalance"] = params["rebalance"]
    return FactorBacktestRequest(**payload)


@router.post("/run")
def run_backtest(config: BacktestConfig):
    if config.strategy not in STRATEGY_MAP:
        return {"error": f"Unknown strategy: {config.strategy}"}

    module_path, class_name = STRATEGY_MAP[config.strategy]
    module = importlib.import_module(module_path)
    strategy_class = getattr(module, class_name)
    strategy = strategy_class(config.params)

    storage = MarketStorage()
    data = storage.get_daily(config.code, config.start_date, config.end_date)
    if not data:
        return {"error": "No data found for the given code and date range"}

    engine = BacktestEngine(capital=config.capital)
    result = engine.run(strategy, data, config.code)

    return {
        "data": {
            "metrics": result.metrics,
            "trades": result.trades,
            "equity_curve": result.equity_curve,
        }
    }


@router.post("/factor/run")
def run_factor_backtest_job(request: FactorBacktestRequest):
    run_id = f"factor_{uuid.uuid4().hex[:10]}"

    conn = get_market_db()
    resolved_request = _resolve_factor_request(request, conn)
    config_json = resolved_request.model_dump_json()
    conn.execute(
        "INSERT INTO factor_backtest_runs (id, status, config_json) VALUES (?, ?, ?)",
        (run_id, "running", config_json),
    )
    conn.commit()

    try:
        storage = MarketStorage()
        result = run_factor_job(storage, resolved_request)
        payload = {"run_id": run_id, "status": "success", **result}
        conn.execute(
            "UPDATE factor_backtest_runs SET status = ?, result_json = ?, updated_at = datetime('now') WHERE id = ?",
            ("success", json.dumps(payload, ensure_ascii=False), run_id),
        )
        conn.commit()
        return {"data": payload}
    except FactorScriptExecutionError as exc:
        error_payload = {
            "run_id": run_id,
            "status": exc.status,
            "error": {"code": exc.code, "message": exc.message},
        }
        conn.execute(
            "UPDATE factor_backtest_runs SET status = ?, result_json = ?, updated_at = datetime('now') WHERE id = ?",
            ("failed", json.dumps(error_payload, ensure_ascii=False), run_id),
        )
        conn.commit()
        return {"error": exc.message, "data": error_payload}
    except Exception as exc:
        error_payload = {"run_id": run_id, "status": "failed", "error": {"code": "job_failed", "message": str(exc)}}
        conn.execute(
            "UPDATE factor_backtest_runs SET status = ?, result_json = ?, updated_at = datetime('now') WHERE id = ?",
            ("failed", json.dumps(error_payload, ensure_ascii=False), run_id),
        )
        conn.commit()
        return {"error": str(exc), "data": error_payload}
    finally:
        conn.close()


@router.get("/factor/{run_id}")
def get_factor_backtest_result(run_id: str):
    conn = get_market_db()
    row = conn.execute("SELECT * FROM factor_backtest_runs WHERE id = ?", (run_id,)).fetchone()
    conn.close()
    if not row:
        return {"error": "因子回测记录不存在"}

    payload = json.loads(row["result_json"]) if row["result_json"] else {}
    return {
        "data": {
            "run_id": run_id,
            "status": row["status"],
            **payload,
        }
    }


@router.get("/strategies")
def list_strategies():
    strategies = [
        {"id": "ma_cross", "name": "均线交叉", "params": {"short": 5, "long": 20}},
        {"id": "macd", "name": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9}},
        {"id": "rsi", "name": "RSI", "params": {"period": 14, "overbought": 70, "oversold": 30}},
        {"id": "bollinger", "name": "布林带突破", "params": {"period": 20, "std": 2}},
        {"id": "platform_breakout", "name": "强势平台启动", "params": {"days": 20, "amplitude": 10}},
    ]
    return {"data": strategies + FACTOR_TEMPLATES}
