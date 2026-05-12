from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是", "封住", "打开", "开"}


def parse_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    multiplier = 1.0
    if text.endswith("万"):
        multiplier = 10_000
        text = text[:-1]
    elif text.endswith("亿"):
        multiplier = 100_000_000
        text = text[:-1]
    if text.endswith("%"):
        text = text[:-1]
    try:
        return float(text) * multiplier
    except ValueError:
        return default


def parse_int(value: Any, default: int = 0) -> int:
    return int(parse_float(value, float(default)))


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class ShortTermCandidate:
    code: str
    trade_date: str
    name: str = ""
    sector: str = ""
    candidate_type: str = "weak_sealed_board"
    limit_hit_count: int = 0
    limit_open_count: int = 0
    visible_open_seconds: float = 0.0
    closed_at_limit: bool = False
    first_limit_time: str = ""
    last_limit_time: str = ""
    score_prev_day: float = 0.0
    notes: str = ""
    data_quality: str = "normal"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuctionSnapshot:
    code: str
    trade_date: str
    captured_at: str = field(default_factory=now_iso)
    name: str = ""
    sector: str = ""
    auction_price: float = 0.0
    prev_close: float = 0.0
    auction_gap_pct: float = 0.0
    auction_volume: float = 0.0
    auction_amount: float = 0.0
    auction_volume_vs_prev_day_pct: float = 0.0
    limit_buy_rank: int = 0
    limit_buy_amount: float = 0.0
    data_source: str = "csv"
    data_quality: str = "normal"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if not data["auction_gap_pct"] and self.prev_close and self.auction_price:
            data["auction_gap_pct"] = (self.auction_price - self.prev_close) / self.prev_close * 100
        return data


@dataclass
class SectorSnapshot:
    sector_name: str
    trade_date: str
    captured_at: str = field(default_factory=now_iso)
    sector_rank: int = 0
    sector_limit_up_count: int = 0
    sector_avg_gap_pct: float = 0.0
    sector_auction_amount: float = 0.0
    sector_score: float = 0.0
    data_source: str = "csv"
    data_quality: str = "normal"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OpenSnapshot:
    code: str
    trade_date: str
    captured_at: str = field(default_factory=now_iso)
    latest_price: float = 0.0
    auction_price: float = 0.0
    prev_close: float = 0.0
    vwap_1m: float = 0.0
    volume_1m: float = 0.0
    amount_1m: float = 0.0
    hold_above_auction: bool = False
    hold_above_vwap: bool = False
    pullback_pct: float = 0.0
    large_sell_pressure_flag: bool = False
    data_source: str = "csv"
    data_quality: str = "normal"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
