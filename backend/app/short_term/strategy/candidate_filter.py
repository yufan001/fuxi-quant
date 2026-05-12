from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.short_term.config import ShortTermStrategyConfig
from app.short_term.models import ShortTermCandidate, parse_bool, parse_float, parse_int


def build_candidates(rows: Iterable[dict[str, Any]], config: ShortTermStrategyConfig | None = None) -> list[dict[str, Any]]:
    config = config or ShortTermStrategyConfig()
    candidates: list[dict[str, Any]] = []
    for row in rows:
        if parse_bool(row.get("is_st")) or parse_bool(row.get("is_suspended")):
            continue
        code = str(row.get("code") or row.get("symbol") or "").strip()
        trade_date = str(row.get("trade_date") or row.get("date") or "").strip()
        if not code or not trade_date:
            continue

        limit_hit_count = parse_int(row.get("limit_hit_count") or row.get("hit_count"), 0)
        limit_open_count = parse_int(row.get("limit_open_count") or row.get("open_count"), 0)
        visible_open_seconds = parse_float(row.get("visible_open_seconds") or row.get("open_seconds"), 0.0)
        touched_limit = parse_bool(row.get("touched_limit")) or limit_hit_count > 0
        visible_open = parse_bool(row.get("visible_opened")) or visible_open_seconds >= config.min_visible_open_seconds
        if not touched_limit or limit_open_count < config.min_limit_open_count or not visible_open:
            continue

        closed_at_limit = parse_bool(row.get("closed_at_limit"))
        candidate_type = "weak_sealed_board" if closed_at_limit else "failed_board"
        candidate = ShortTermCandidate(
            code=code,
            trade_date=trade_date,
            name=str(row.get("name") or ""),
            sector=str(row.get("sector") or row.get("industry") or ""),
            candidate_type=str(row.get("candidate_type") or candidate_type),
            limit_hit_count=limit_hit_count,
            limit_open_count=limit_open_count,
            visible_open_seconds=visible_open_seconds,
            closed_at_limit=closed_at_limit,
            first_limit_time=str(row.get("first_limit_time") or ""),
            last_limit_time=str(row.get("last_limit_time") or ""),
            notes=str(row.get("notes") or ""),
            data_quality=str(row.get("data_quality") or "normal"),
        )
        score = 10 if candidate.candidate_type == "failed_board" else 15
        score += min(max(limit_open_count - config.min_limit_open_count + 1, 0) * 2, 6)
        score += 4 if visible_open_seconds >= 60 else 2
        candidate.score_prev_day = min(score, 25)
        candidates.append(candidate.to_dict())
    return candidates
