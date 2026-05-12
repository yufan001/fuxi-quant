from __future__ import annotations

from typing import Any

from app.short_term.config import ShortTermStrategyConfig
from app.short_term.models import parse_float, parse_int
from app.short_term.strategy.open_monitor import score_open_continuation


def _previous_day_score(candidate: dict[str, Any]) -> tuple[int, list[str]]:
    score = 10 if candidate.get("candidate_type") == "failed_board" else 15
    reasons = ["昨日弱势涨停基础分 +15" if score == 15 else "昨日触板未封基础分 +10"]
    open_count = parse_int(candidate.get("limit_open_count"), 0)
    if open_count >= 2:
        bonus = min((open_count - 1) * 2, 6)
        score += bonus
        reasons.append(f"昨日涨停打开 {open_count} 次 +{bonus}")
    visible_seconds = parse_float(candidate.get("visible_open_seconds"), 0.0)
    if visible_seconds >= 60:
        score += 4
        reasons.append("可见开板时间超过 60 秒 +4")
    elif visible_seconds > 0:
        score += 2
        reasons.append("存在可见开板 +2")
    return min(score, 25), reasons


def _auction_score(auction: dict[str, Any] | None, config: ShortTermStrategyConfig) -> tuple[int, list[str]]:
    if not auction:
        return 0, []
    score = 0
    reasons: list[str] = []
    gap = parse_float(auction.get("auction_gap_pct"), 0.0)
    amount = parse_float(auction.get("auction_amount"), 0.0)
    volume_ratio = parse_float(auction.get("auction_volume_vs_prev_day_pct"), 0.0)
    if config.min_auction_gap_pct <= gap <= config.max_auction_gap_pct:
        score += 8
        reasons.append(f"竞价高开 {gap:.2f}% +8")
    if config.preferred_auction_gap_min_pct <= gap <= config.preferred_auction_gap_max_pct:
        score += 6
        reasons.append("竞价高开处于偏强区间 +6")
    if amount >= config.min_auction_amount:
        score += 10
        reasons.append(f"竞价额 {amount:.0f} 达标 +10")
    if volume_ratio >= config.min_auction_volume_vs_prev_day_pct:
        score += 6
        reasons.append(f"竞价量比 {volume_ratio:.2f} 达标 +6")
    return min(score, 30), reasons


def _sector_score(sector: dict[str, Any] | None, config: ShortTermStrategyConfig) -> tuple[int, list[str]]:
    if not sector:
        return 0, []
    rank = parse_int(sector.get("sector_rank"), 0)
    score = 0
    reasons: list[str] = []
    if rank and rank <= config.top_sector_full_rank:
        score = 20
        reasons.append(f"板块排名第 {rank} +20")
    elif rank and rank <= config.top_sector_partial_rank:
        score = 12
        reasons.append(f"板块排名第 {rank} +12")
    limit_up_count = parse_int(sector.get("sector_limit_up_count"), 0)
    if limit_up_count >= 3 and score < 20:
        score += 4
        reasons.append("板块涨停家数较多 +4")
    return min(score, 20), reasons


def _buy_rank_score(auction: dict[str, Any] | None, config: ShortTermStrategyConfig) -> tuple[int, list[str]]:
    if not auction:
        return 0, []
    rank = parse_int(auction.get("limit_buy_rank"), 0)
    if rank and rank <= config.top_buy_rank_full:
        return 15, [f"竞价涨停委买榜排名第 {rank} +15"]
    if rank and rank <= config.top_buy_rank_partial:
        return 8, [f"竞价涨停委买榜排名第 {rank} +8"]
    return 0, []


def score_candidate(
    candidate: dict[str, Any],
    auction: dict[str, Any] | None = None,
    sector: dict[str, Any] | None = None,
    open_snapshot: dict[str, Any] | None = None,
    config: ShortTermStrategyConfig | None = None,
    phase: str = "preopen",
) -> dict[str, Any]:
    config = config or ShortTermStrategyConfig()
    previous_day, previous_reasons = _previous_day_score(candidate)
    auction_score, auction_reasons = _auction_score(auction, config)
    sector_score, sector_reasons = _sector_score(sector, config)
    buy_rank_score, buy_rank_reasons = _buy_rank_score(auction, config)
    open_score, open_reasons = score_open_continuation(open_snapshot)
    breakdown = {
        "previous_day": previous_day,
        "auction": auction_score,
        "sector": sector_score,
        "buy_order_rank": buy_rank_score,
        "open_continuation": open_score,
    }
    total = min(sum(breakdown.values()), 100)
    trade_date = (open_snapshot or auction or candidate).get("trade_date")
    return {
        "code": candidate["code"],
        "trade_date": trade_date,
        "candidate_trade_date": candidate.get("trade_date"),
        "phase": phase,
        "total_score": total,
        "score_breakdown": breakdown,
        "reasons": previous_reasons + auction_reasons + sector_reasons + buy_rank_reasons + open_reasons,
        "data_quality": _combined_quality(candidate, auction, sector, open_snapshot),
    }


def _combined_quality(*items: dict[str, Any] | None) -> str:
    qualities = {str(item.get("data_quality") or "normal") for item in items if item}
    if "low" in qualities or "needs_review" in qualities:
        return "needs_review"
    return "normal"
