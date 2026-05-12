from __future__ import annotations


def summarize_score_buckets(scores: list[dict]) -> dict:
    buckets = {"0-59": 0, "60-69": 0, "70-79": 0, "80+": 0}
    for score in scores:
        total = float(score.get("total_score") or 0)
        if total >= 80:
            buckets["80+"] += 1
        elif total >= 70:
            buckets["70-79"] += 1
        elif total >= 60:
            buckets["60-69"] += 1
        else:
            buckets["0-59"] += 1
    return {"score_buckets": buckets, "score_count": len(scores)}
