from __future__ import annotations

from pathlib import Path

from app.short_term.alerts.notifier import build_observation_alerts
from app.short_term.backtest.runner import run_event_backtest
from app.short_term.data_sources.csv_source import CsvShortTermSource
from app.short_term.storage import ShortTermStorage
from app.short_term.strategy.scoring import score_candidate


def short_term_import_csv_job(context):
    data_type = context.payload["data_type"]
    source_path = Path(context.payload["source_path"])
    context.set_progress(10, "short_term_import_loading_csv")
    rows = CsvShortTermSource().read(data_type, source_path)
    storage = ShortTermStorage()
    if data_type in {"candidates", "candidate_seeds"}:
        storage.save_candidates(rows)
    elif data_type == "auction":
        storage.save_auction_snapshots(rows)
    elif data_type == "sector":
        storage.save_sector_snapshots(rows)
    elif data_type == "open":
        storage.save_open_snapshots(rows)
    else:
        raise ValueError(f"unsupported short-term data_type: {data_type}")
    result = {"data_type": data_type, "row_count": len(rows), "source_path": str(source_path)}
    context.set_summary(result)
    context.write_json_artifact("result.json", result)
    context.write_text_artifact("logs.txt", "\n".join(context.logs))
    context.set_progress(100, "short_term_import_complete")
    return result


def short_term_build_candidates_job(context):
    storage = ShortTermStorage()
    trade_date = context.payload.get("trade_date")
    candidates = storage.list_candidates(trade_date)
    result = {"trade_date": trade_date, "candidate_count": len(candidates), "candidates": candidates}
    context.set_summary({"trade_date": trade_date, "candidate_count": len(candidates)})
    context.write_json_artifact("candidates.json", candidates)
    context.write_json_artifact("result.json", result)
    context.set_progress(100, "short_term_candidates_complete")
    return result


def short_term_score_auction_job(context):
    trade_date = context.payload["trade_date"]
    candidate_date = context.payload.get("candidate_date") or trade_date
    phase = context.payload.get("phase", "preopen")
    storage = ShortTermStorage()
    candidates = storage.list_candidates(candidate_date)
    auctions = storage.latest_by_code("short_term_auction_snapshots", trade_date)
    sectors = storage.latest_sector_by_name(trade_date)
    opens = storage.latest_by_code("short_term_open_snapshots", trade_date) if phase == "open" else {}
    scores = []
    for candidate in candidates:
        auction = auctions.get(candidate["code"])
        sector_name = (auction or {}).get("sector") or candidate.get("sector")
        scores.append(score_candidate(candidate, auction, sectors.get(sector_name), opens.get(candidate["code"]), phase=phase))
    storage.save_scores(scores)
    alerts = build_observation_alerts(scores)
    storage.save_alerts(alerts)
    result = {"trade_date": trade_date, "candidate_date": candidate_date, "phase": phase, "scores": scores, "alerts": alerts}
    context.set_summary({"score_count": len(scores), "alert_count": len(alerts), "phase": phase})
    context.write_json_artifact("scores.json", scores)
    context.write_json_artifact("alerts.json", alerts)
    context.write_json_artifact("result.json", result)
    context.set_progress(100, "short_term_score_complete")
    return result


def short_term_monitor_open_job(context):
    context.payload["phase"] = "open"
    return short_term_score_auction_job(context)


def short_term_backtest_job(context):
    storage = ShortTermStorage()
    start_date = context.payload["start_date"]
    end_date = context.payload["end_date"]
    candidates = [row for row in storage.list_candidates() if start_date <= row["trade_date"] <= end_date]
    auctions = [row for row in storage.list_auction_snapshots() if start_date <= row["trade_date"] <= end_date]
    sectors = [row for row in storage.list_sector_snapshots() if start_date <= row["trade_date"] <= end_date]
    opens = [row for row in storage.list_open_snapshots() if start_date <= row["trade_date"] <= end_date]
    result = run_event_backtest(candidates, auctions, sectors, opens)
    context.set_summary(result["metrics"])
    context.write_json_artifact("result.json", result)
    context.write_json_artifact("scores.json", result["scores"])
    context.set_progress(100, "short_term_backtest_complete")
    return result
