from pydantic import BaseModel
from typing import Optional


class StockDaily(BaseModel):
    code: str
    date: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    amount: Optional[float] = None
    turn: Optional[float] = None
    peTTM: Optional[float] = None
    pbMRQ: Optional[float] = None
    psTTM: Optional[float] = None
    pcfNcfTTM: Optional[float] = None


class StockInfo(BaseModel):
    code: str
    name: Optional[str] = None
    industry: Optional[str] = None
    listed_date: Optional[str] = None
    delisted_date: Optional[str] = None
    status: Optional[str] = None


class KlineRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class DataStatus(BaseModel):
    total_stocks: int
    total_records: int
    last_update_date: Optional[str] = None
