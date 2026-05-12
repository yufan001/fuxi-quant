from __future__ import annotations

from app.short_term.config import ShortTermStrategyConfig


def build_observation_alerts(scores: list[dict], config: ShortTermStrategyConfig | None = None) -> list[dict]:
    config = config or ShortTermStrategyConfig()
    alerts = []
    for score in scores:
        total = float(score.get("total_score") or 0)
        phase = score.get("phase") or "preopen"
        threshold = config.open_strength_score if phase == "open" else config.preopen_observe_score
        if total < threshold:
            continue
        code = score.get("code")
        reasons = "；".join(score.get("reasons") or [])
        message = f"观察 {code}: {phase} 分数 {total:.0f}，{reasons}"
        alerts.append({
            "symbol": code,
            "trade_date": score.get("trade_date"),
            "alert_type": f"short_term_{phase}_observe",
            "score": total,
            "message": message,
            "payload": score,
        })
    return alerts
