from __future__ import annotations

from typing import Any

from app.short_term.models import parse_bool, parse_float


def score_open_continuation(open_snapshot: dict[str, Any] | None) -> tuple[int, list[str]]:
    if not open_snapshot:
        return 0, []
    score = 0
    reasons: list[str] = []
    if parse_bool(open_snapshot.get("hold_above_auction")):
        score += 4
        reasons.append("开盘承接在竞价价上方 +4")
    if parse_bool(open_snapshot.get("hold_above_vwap")):
        score += 2
        reasons.append("开盘 VWAP 承接较强 +2")
    pullback = parse_float(open_snapshot.get("pullback_pct"), 0.0)
    if pullback <= 1.5:
        score += 2
        reasons.append("开盘回撤较小 +2")
    if parse_float(open_snapshot.get("amount_1m"), 0.0) > 0:
        score += 2
        reasons.append("首分钟有成交验证 +2")
    if parse_bool(open_snapshot.get("large_sell_pressure_flag")):
        score -= 4
        reasons.append("开盘大卖压 -4")
    return max(0, min(score, 10)), reasons
