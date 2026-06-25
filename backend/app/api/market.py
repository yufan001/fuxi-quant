from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.data.storage import MarketStorage
from app.research.gc_volume_profile import build_xau_chart_snapshot

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
    period: str = Query("d"),
):
    storage = MarketStorage()
    try:
        data = storage.get_kline_data(code, start_date, end_date, period=period)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": data}


@router.get("/xau/chart")
def get_xau_chart(
    interval: str = Query("5m", description="XAU chart interval: 1m or 5m"),
    days: Optional[float] = Query(None, ge=0.1, le=7),
    trend_days: float = Query(45.0, ge=7, le=180),
    lookback_bars: Optional[int] = Query(None, ge=20, le=2000),
    price_step: float = Query(0.5, gt=0, le=10),
    value_area_pct: float = Query(0.7, gt=0, le=1),
    force_refresh: bool = Query(False),
):
    try:
        data = build_xau_chart_snapshot(
            interval=interval,
            days=days,
            trend_days=trend_days,
            lookback_bars=lookback_bars,
            price_step=price_step,
            value_area_pct=value_area_pct,
            force_refresh=force_refresh,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"failed to load dynamic XAU/GC data: {exc}") from exc
    return {"data": data}


@router.get("/status")
def get_status():
    storage = MarketStorage()
    status = storage.get_data_status()
    return {"data": status}
