from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from app.short_term.data_sources.base import ShortTermDataSource
from app.short_term.models import AuctionSnapshot, OpenSnapshot, SectorSnapshot, parse_float, parse_int
from app.short_term.strategy.candidate_filter import build_candidates


class CsvShortTermSource(ShortTermDataSource):
    def read(self, data_type: str, path: str | Path) -> list[dict]:
        rows = _read_csv(path)
        if data_type in {"candidates", "candidate_seeds"}:
            return build_candidates(rows)
        if data_type == "auction":
            return [_auction(row) for row in rows]
        if data_type == "sector":
            return [_sector(row) for row in rows]
        if data_type == "open":
            return [_open(row) for row in rows]
        raise ValueError(f"unsupported short-term csv data_type: {data_type}")


def _read_csv(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _auction(row: dict[str, Any]) -> dict[str, Any]:
    snapshot = AuctionSnapshot(
        code=str(row.get("code") or row.get("symbol") or "").strip(),
        trade_date=str(row.get("trade_date") or row.get("date") or "").strip(),
        captured_at=str(row.get("captured_at") or row.get("time") or ""),
        name=str(row.get("name") or ""),
        sector=str(row.get("sector") or row.get("industry") or ""),
        auction_price=parse_float(row.get("auction_price"), 0.0),
        prev_close=parse_float(row.get("prev_close"), 0.0),
        auction_gap_pct=parse_float(row.get("auction_gap_pct"), 0.0),
        auction_volume=parse_float(row.get("auction_volume"), 0.0),
        auction_amount=parse_float(row.get("auction_amount"), 0.0),
        auction_volume_vs_prev_day_pct=parse_float(row.get("auction_volume_vs_prev_day_pct"), 0.0),
        limit_buy_rank=parse_int(row.get("limit_buy_rank"), 0),
        limit_buy_amount=parse_float(row.get("limit_buy_amount"), 0.0),
        data_source=str(row.get("data_source") or "csv"),
        data_quality=str(row.get("data_quality") or "normal"),
    )
    data = snapshot.to_dict()
    if not data["captured_at"]:
        data["captured_at"] = snapshot.captured_at
    return data


def _sector(row: dict[str, Any]) -> dict[str, Any]:
    snapshot = SectorSnapshot(
        sector_name=str(row.get("sector_name") or row.get("sector") or row.get("industry") or "").strip(),
        trade_date=str(row.get("trade_date") or row.get("date") or "").strip(),
        captured_at=str(row.get("captured_at") or row.get("time") or ""),
        sector_rank=parse_int(row.get("sector_rank") or row.get("rank"), 0),
        sector_limit_up_count=parse_int(row.get("sector_limit_up_count") or row.get("limit_up_count"), 0),
        sector_avg_gap_pct=parse_float(row.get("sector_avg_gap_pct"), 0.0),
        sector_auction_amount=parse_float(row.get("sector_auction_amount"), 0.0),
        sector_score=parse_float(row.get("sector_score"), 0.0),
        data_source=str(row.get("data_source") or "csv"),
        data_quality=str(row.get("data_quality") or "normal"),
    )
    data = snapshot.to_dict()
    if not data["captured_at"]:
        data["captured_at"] = snapshot.captured_at
    return data


def _open(row: dict[str, Any]) -> dict[str, Any]:
    snapshot = OpenSnapshot(
        code=str(row.get("code") or row.get("symbol") or "").strip(),
        trade_date=str(row.get("trade_date") or row.get("date") or "").strip(),
        captured_at=str(row.get("captured_at") or row.get("time") or ""),
        latest_price=parse_float(row.get("latest_price"), 0.0),
        auction_price=parse_float(row.get("auction_price"), 0.0),
        prev_close=parse_float(row.get("prev_close"), 0.0),
        vwap_1m=parse_float(row.get("vwap_1m"), 0.0),
        volume_1m=parse_float(row.get("volume_1m"), 0.0),
        amount_1m=parse_float(row.get("amount_1m"), 0.0),
        hold_above_auction=str(row.get("hold_above_auction") or "").strip().lower() in {"1", "true", "yes", "是"},
        hold_above_vwap=str(row.get("hold_above_vwap") or "").strip().lower() in {"1", "true", "yes", "是"},
        pullback_pct=parse_float(row.get("pullback_pct"), 0.0),
        large_sell_pressure_flag=str(row.get("large_sell_pressure_flag") or "").strip().lower() in {"1", "true", "yes", "是"},
        data_source=str(row.get("data_source") or "csv"),
        data_quality=str(row.get("data_quality") or "normal"),
    )
    data = snapshot.to_dict()
    if not data["captured_at"]:
        data["captured_at"] = snapshot.captured_at
    return data
