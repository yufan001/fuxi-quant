from fastapi import APIRouter, Query
from typing import Optional
from app.data.storage import MarketStorage

router = APIRouter()


@router.get("/stocks")
def list_stocks(q: Optional[str] = Query(None, description="搜索关键词（代码或名称）")):
    storage = MarketStorage()
    stocks = storage.search_stocks(q)
    return {"data": stocks}


@router.get("/kline/{code}")
def get_kline(
    code: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    storage = MarketStorage()
    data = storage.get_daily(code, start_date, end_date)
    return {"data": data}


@router.get("/status")
def get_status():
    storage = MarketStorage()
    status = storage.get_data_status()
    return {"data": status}
