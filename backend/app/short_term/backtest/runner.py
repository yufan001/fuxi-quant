from __future__ import annotations

from app.short_term.backtest.metrics import summarize_score_buckets
from app.short_term.strategy.scoring import score_candidate


def run_event_backtest(candidates: list[dict], auctions: list[dict], sectors: list[dict], open_snapshots: list[dict]) -> dict:
    auctions_by_key = {(row["code"], row["trade_date"]): row for row in auctions}
    opens_by_key = {(row["code"], row["trade_date"]): row for row in open_snapshots}
    sectors_by_key = {(row["sector_name"], row["trade_date"]): row for row in sectors}
    scores = []
    for candidate in candidates:
        for (code, trade_date), auction in auctions_by_key.items():
            if code != candidate["code"]:
                continue
            sector_name = auction.get("sector") or candidate.get("sector")
            score = score_candidate(
                candidate,
                auction=auction,
                sector=sectors_by_key.get((sector_name, trade_date)),
                open_snapshot=opens_by_key.get((code, trade_date)),
                phase="open" if (code, trade_date) in opens_by_key else "preopen",
            )
            scores.append(score)
    return {"scores": scores, "metrics": summarize_score_buckets(scores)}
