from collections import OrderedDict

import pandas as pd

from app.core.factor_backtest import FactorBacktestConfig, run_factor_backtest, run_selection_backtest
from app.core.factor_frame import DEFAULT_FACTOR_COLUMNS, frame_to_histories, slice_frame_until

HISTORY_BATCH_SIZE = 200


def _pick_rebalance_dates(trade_dates: list[str], rebalance: str) -> list[str]:
    if not trade_dates:
        return []

    grouped = OrderedDict()
    for date in trade_dates:
        key = date[:8] if rebalance == "weekly" else date[:7]
        grouped[key] = date
    return list(grouped.values())


def _history_until(history: list[dict], as_of_date: str) -> list[dict]:
    return [row for row in history if row["date"] <= as_of_date]


def _load_histories(storage, pool_codes, start_date, end_date, progress_callback=None, log_callback=None, assert_not_cancelled=None):
    histories = {}
    total_batches = max((len(pool_codes) + HISTORY_BATCH_SIZE - 1) // HISTORY_BATCH_SIZE, 1)
    for index in range(total_batches):
        if assert_not_cancelled:
            assert_not_cancelled()
        chunk = pool_codes[index * HISTORY_BATCH_SIZE:(index + 1) * HISTORY_BATCH_SIZE]
        if not chunk:
            continue
        if log_callback:
            log_callback(f'loading history batch {index + 1}/{total_batches}')
        histories.update(storage.get_histories(chunk, start_date, end_date))
        if progress_callback:
            progress_callback(5 + (index + 1) / total_batches * 10, f'loading_histories_{index + 1}_of_{total_batches}')
    return histories


def _load_script_entrypoints(script: str):
    namespace = {}
    exec(script, {}, namespace)
    score_stocks = namespace.get("score_stocks")
    select_portfolio = namespace.get("select_portfolio")
    score_frame = namespace.get("score_frame")
    if not callable(score_stocks) and not callable(select_portfolio) and not callable(score_frame):
        raise ValueError("脚本必须定义 score_stocks(histories, context)、select_portfolio(histories, context) 或 score_frame(frame, context)")
    return score_stocks, select_portfolio, score_frame


def _normalize_portfolio_selection(selection) -> list[dict]:
    if isinstance(selection, dict):
        return [{"code": code, "weight": weight} for code, weight in selection.items()]
    normalized = []
    for item in selection or []:
        if isinstance(item, str):
            normalized.append({"code": item, "weight": 1.0})
        elif isinstance(item, dict) and item.get("code"):
            normalized.append({**item, "weight": float(item.get("weight", 1.0))})
    return normalized


def _build_script_rebalances(history_frame: pd.DataFrame, histories: dict[str, list[dict]], request, rebalance_dates: list[str], progress_callback=None, assert_not_cancelled=None) -> list[dict]:
    score_stocks, select_portfolio, score_frame = _load_script_entrypoints(request.script)
    rebalances = []

    total_rebalances = len(rebalance_dates)
    for index, rebalance_date in enumerate(rebalance_dates, start=1):
        if assert_not_cancelled:
            assert_not_cancelled()
        snapshot_frame = slice_frame_until(history_frame, rebalance_date)
        if callable(score_frame):
            snapshot_histories = frame_to_histories(snapshot_frame)
        else:
            snapshot_histories = {code: _history_until(history, rebalance_date) for code, history in histories.items()}
        snapshot_histories = {code: rows for code, rows in snapshot_histories.items() if rows}
        context = {
            "date": rebalance_date,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "rebalance": request.rebalance,
            "top_n": request.top_n,
        }

        if callable(score_frame):
            scores = score_frame(snapshot_frame, context) or {}
            ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[: request.top_n]
            selected = [{"code": code, "score": float(score)} for code, score in ranked if code in snapshot_histories]
        elif callable(score_stocks):
            scores = score_stocks(snapshot_histories, context) or {}
            ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[: request.top_n]
            selected = [{"code": code, "score": float(score)} for code, score in ranked if code in snapshot_histories]
        else:
            selected = _normalize_portfolio_selection(select_portfolio(snapshot_histories, context))
            selected = [item for item in selected if item["code"] in snapshot_histories]

        rebalances.append({"date": rebalance_date, "selected": selected})
        if progress_callback:
            progress_callback(10 + index / max(total_rebalances, 1) * 20, f'script_rebalance_{index}_of_{total_rebalances}')

    return rebalances


def run_factor_job(storage, request, progress_callback=None, log_callback=None, assert_not_cancelled=None) -> dict:
    if log_callback:
        log_callback('loading histories')
    if progress_callback:
        progress_callback(5, 'loading_histories')
    if assert_not_cancelled:
        assert_not_cancelled()
    pool_codes = request.pool_codes or storage.get_all_stock_codes() or sorted(storage.get_downloaded_codes())
    histories = _load_histories(
        storage,
        pool_codes,
        request.start_date,
        request.end_date,
        progress_callback=progress_callback,
        log_callback=log_callback,
        assert_not_cancelled=assert_not_cancelled,
    )
    history_frame = storage.get_history_frame(
        pool_codes,
        request.start_date,
        request.end_date,
        columns=DEFAULT_FACTOR_COLUMNS,
    )
    if not isinstance(history_frame, pd.DataFrame):
        history_frame = pd.DataFrame(
            [
                {**row, "code": code}
                for code, history in histories.items()
                for row in history
            ],
            columns=DEFAULT_FACTOR_COLUMNS,
        )

    if request.pool_codes:
        eligible_codes = request.pool_codes
    else:
        eligible_codes = [code for code, history in histories.items() if history]
        histories = {code: history for code, history in histories.items() if history}

    if progress_callback:
        progress_callback(8, 'loading_trade_dates')
    trade_dates = storage.get_trade_dates(request.start_date, request.end_date)
    rebalance_dates = request.rebalance_dates or _pick_rebalance_dates(trade_dates, request.rebalance)

    if getattr(request, "script", None):
        result = run_selection_backtest(
            histories,
            _build_script_rebalances(
                history_frame,
                histories,
                request,
                rebalance_dates,
                progress_callback=progress_callback,
                assert_not_cancelled=assert_not_cancelled,
            ),
            request.capital,
            progress_callback=progress_callback,
            assert_not_cancelled=assert_not_cancelled,
        )
    else:
        result = run_factor_backtest(
            histories,
            FactorBacktestConfig(
                factor_configs=request.factor_configs,
                top_n=request.top_n,
                initial_capital=request.capital,
                rebalance_dates=rebalance_dates,
            ),
            progress_callback=progress_callback,
            assert_not_cancelled=assert_not_cancelled,
        )

    return {
        "pool_size": len(eligible_codes),
        "rebalance": request.rebalance,
        "metrics": result.metrics,
        "equity_curve": result.equity_curve,
        "rebalances": result.rebalances,
    }
