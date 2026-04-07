from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class TradeRequest(BaseModel):
    code: str
    price: float
    amount: int
    action: str  # "buy" | "sell"


@router.get("/positions")
def get_positions():
    # In real mode, this would use the actual broker
    # For now, return from the simulator or saved state
    return {"data": []}


@router.get("/orders")
def get_orders(date: Optional[str] = None):
    return {"data": []}


@router.get("/balance")
def get_balance():
    return {"data": {"total": 0, "available": 0, "frozen": 0}}


@router.post("/order")
def place_order(req: TradeRequest):
    return {"error": "实盘交易未启用。请先在运维页配置券商连接。"}
