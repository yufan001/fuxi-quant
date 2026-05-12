from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShortTermStrategyConfig:
    min_limit_open_count: int = 2
    min_visible_open_seconds: float = 1.0
    min_auction_gap_pct: float = 1.0
    preferred_auction_gap_min_pct: float = 2.0
    preferred_auction_gap_max_pct: float = 7.0
    max_auction_gap_pct: float = 8.5
    min_auction_amount: float = 10_000_000
    min_auction_volume_vs_prev_day_pct: float = 1.5
    top_sector_full_rank: int = 3
    top_sector_partial_rank: int = 8
    top_buy_rank_full: int = 10
    top_buy_rank_partial: int = 30
    preopen_observe_score: float = 65.0
    open_strength_score: float = 75.0
    weakening_score_drop: float = 20.0
