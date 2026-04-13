import traceback

import pandas as pd

from app.core.factor_frame import frame_to_histories, slice_frame_until


def _load_script_entrypoints(script: str):
    namespace = {}
    exec(script, {}, namespace)
    return namespace.get("score_stocks"), namespace.get("select_portfolio"), namespace.get("score_frame")


def run_script_worker(script: str, history_frame_records: list[dict], rebalance_dates: list[str], context_base: dict) -> dict:
    frame = pd.DataFrame(history_frame_records)
    score_stocks, select_portfolio, score_frame = _load_script_entrypoints(script)
    if not callable(score_stocks) and not callable(select_portfolio) and not callable(score_frame):
        return {
            "status": "script_error",
            "rebalances": [],
            "error": {
                "code": "script_error",
                "message": "脚本必须定义 score_stocks(histories, context)、select_portfolio(histories, context) 或 score_frame(frame, context)",
            },
            "logs": [],
        }

    try:
        rebalances = []
        for rebalance_date in rebalance_dates:
            snapshot_frame = slice_frame_until(frame, rebalance_date)
            snapshot_histories = frame_to_histories(snapshot_frame)
            context = {**context_base, "date": rebalance_date}
            if callable(score_frame):
                scores = score_frame(snapshot_frame, context) or {}
                ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[: context_base["top_n"]]
                selected = [{"code": code, "score": float(score)} for code, score in ranked if code in snapshot_histories]
            elif callable(score_stocks):
                scores = score_stocks(snapshot_histories, context) or {}
                ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[: context_base["top_n"]]
                selected = [{"code": code, "score": float(score)} for code, score in ranked if code in snapshot_histories]
            else:
                selection = select_portfolio(snapshot_histories, context) or []
                selected = [item for item in selection if isinstance(item, dict) and item.get("code") in snapshot_histories]
            rebalances.append({"date": rebalance_date, "selected": selected})
        return {"status": "success", "rebalances": rebalances, "error": None, "logs": []}
    except Exception as exc:
        return {
            "status": "script_error",
            "rebalances": [],
            "error": {
                "code": "script_error",
                "message": str(exc),
                "traceback": traceback.format_exc(),
            },
            "logs": [],
        }
