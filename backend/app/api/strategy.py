import json
import sqlite3
from fastapi import APIRouter, Body
from pydantic import BaseModel
from typing import Optional
from app.models.db import get_market_db

router = APIRouter()

BUILTIN_STRATEGIES = [
    {"id": "ma_cross", "name": "均线交叉", "type": "tech", "builtin": True,
     "params": {"short": 5, "long": 20},
     "description": "短期均线上穿长期均线买入，下穿卖出"},
    {"id": "macd", "name": "MACD", "type": "tech", "builtin": True,
     "params": {"fast": 12, "slow": 26, "signal": 9},
     "description": "MACD金叉买入，死叉卖出"},
    {"id": "rsi", "name": "RSI", "type": "tech", "builtin": True,
     "params": {"period": 14, "overbought": 70, "oversold": 30},
     "description": "RSI超卖区回升买入，超买区回落卖出"},
    {"id": "bollinger", "name": "布林带突破", "type": "tech", "builtin": True,
     "params": {"period": 20, "std": 2},
     "description": "价格突破下轨买入，触及上轨卖出"},
    {"id": "platform_breakout", "name": "强势平台启动", "type": "pattern", "builtin": True,
     "params": {"days": 20, "amplitude": 10},
     "description": "识别横盘整理区间，突破上沿买入"},
    {"id": "factor_low_pb_momentum", "name": "低PB + 动量", "type": "factor", "builtin": True,
     "params": {
         "factor_configs": [
             {"key": "pb", "weight": 0.5},
             {"key": "momentum_20", "weight": 0.5}
         ],
         "top_n": 10,
         "rebalance": "monthly"
     },
     "description": "低估值与短期动量混合打分，做月度调仓"},
]


def _init_strategy_table():
    conn = get_market_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_strategies (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT DEFAULT 'custom',
            description TEXT DEFAULT '',
            params TEXT DEFAULT '{}',
            code TEXT DEFAULT '',
            enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


_init_strategy_table()


class StrategyCreate(BaseModel):
    name: str
    type: str = "custom"
    description: str = ""
    params: dict = {}
    code: str = ""


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    params: Optional[dict] = None
    code: Optional[str] = None
    enabled: Optional[bool] = None


@router.get("/list")
def list_strategies():
    conn = get_market_db()
    rows = conn.execute("SELECT * FROM user_strategies WHERE enabled = 1 ORDER BY created_at").fetchall()
    conn.close()
    user_strategies = [
        {
            "id": r["id"], "name": r["name"], "type": r["type"],
            "description": r["description"], "builtin": False,
            "params": json.loads(r["params"]) if r["params"] else {},
            "code": r["code"] or "",
            "enabled": bool(r["enabled"]),
        }
        for r in rows
    ]
    return {"data": BUILTIN_STRATEGIES + user_strategies}


@router.post("/create")
def create_strategy(s: StrategyCreate):
    import uuid
    sid = f"custom_{uuid.uuid4().hex[:8]}"
    conn = get_market_db()
    conn.execute(
        "INSERT INTO user_strategies (id, name, type, description, params, code) VALUES (?, ?, ?, ?, ?, ?)",
        (sid, s.name, s.type, s.description, json.dumps(s.params), s.code),
    )
    conn.commit()
    conn.close()
    return {"data": {"id": sid, "name": s.name}}


@router.put("/{strategy_id}")
def update_strategy(strategy_id: str, s: StrategyUpdate):
    conn = get_market_db()
    fields = []
    values = []
    if s.name is not None:
        fields.append("name = ?")
        values.append(s.name)
    if s.description is not None:
        fields.append("description = ?")
        values.append(s.description)
    if s.params is not None:
        fields.append("params = ?")
        values.append(json.dumps(s.params))
    if s.code is not None:
        fields.append("code = ?")
        values.append(s.code)
    if s.enabled is not None:
        fields.append("enabled = ?")
        values.append(int(s.enabled))
    if fields:
        fields.append("updated_at = datetime('now')")
        sql = f"UPDATE user_strategies SET {', '.join(fields)} WHERE id = ?"
        values.append(strategy_id)
        conn.execute(sql, values)
        conn.commit()
    conn.close()
    return {"data": {"id": strategy_id, "updated": True}}


@router.delete("/{strategy_id}")
def delete_strategy(strategy_id: str):
    if any(s["id"] == strategy_id for s in BUILTIN_STRATEGIES):
        return {"error": "内置策略不能删除"}
    conn = get_market_db()
    conn.execute("DELETE FROM user_strategies WHERE id = ?", (strategy_id,))
    conn.commit()
    conn.close()
    return {"data": {"id": strategy_id, "deleted": True}}


@router.get("/{strategy_id}")
def get_strategy(strategy_id: str):
    for s in BUILTIN_STRATEGIES:
        if s["id"] == strategy_id:
            return {"data": s}
    conn = get_market_db()
    row = conn.execute("SELECT * FROM user_strategies WHERE id = ?", (strategy_id,)).fetchone()
    conn.close()
    if not row:
        return {"error": "策略不存在"}
    return {
        "data": {
            "id": row["id"], "name": row["name"], "type": row["type"],
            "description": row["description"], "builtin": False,
            "params": json.loads(row["params"]) if row["params"] else {},
            "code": row["code"] or "",
            "enabled": bool(row["enabled"]),
        }
    }
