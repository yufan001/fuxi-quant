from collections import OrderedDict
import multiprocessing as mp
import queue
import time

import pandas as pd

from app.core.factor_backtest import FactorBacktestConfig, run_factor_backtest, run_selection_backtest
from app.core.factor_frame import DEFAULT_FACTOR_COLUMNS
from app.core.factor_worker import run_script_worker
from app.core.jobs import JobCancelledError

HISTORY_BATCH_SIZE = 200


class FactorScriptExecutionError(Exception):
    def __init__(self, status: str, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


def _script_timeout_seconds(request) -> float:
    configured = getattr(request, "script_timeout_seconds", None)
    if configured is None:
        return 10.0
    return float(configured)


def _script_worker_entry(result_queue, script: str, history_frame_records: list[dict], rebalance_dates: list[str], context_base: dict):
    result_queue.put(
        run_script_worker(
            script=script,
            history_frame_records=history_frame_records,
            rebalance_dates=rebalance_dates,
            context_base=context_base,
        )
    )


def _pick_rebalance_dates(trade_dates: list[str], rebalance: str) -> list[str]:
    if not trade_dates:
        return []

    grouped = OrderedDict()
    for date in trade_dates:
        key = date[:8] if rebalance == "weekly" else date[:7]
        grouped[key] = date
    return list(grouped.values())

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


def _run_script_worker_supervised(history_frame: pd.DataFrame, request, rebalance_dates: list[str], assert_not_cancelled=None) -> list[dict]:
    ctx = mp.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(
        target=_script_worker_entry,
        args=(
            result_queue,
            request.script,
            history_frame.to_dict("records"),
            rebalance_dates,
            {
                "start_date": request.start_date,
                "end_date": request.end_date,
                "rebalance": request.rebalance,
                "top_n": request.top_n,
            },
        ),
        daemon=True,
    )
    process.start()
    deadline = time.monotonic() + _script_timeout_seconds(request)

    try:
        while process.is_alive():
            if assert_not_cancelled:
                try:
                    assert_not_cancelled()
                except JobCancelledError:
                    process.terminate()
                    process.join(timeout=1)
                    raise
            if time.monotonic() >= deadline:
                process.terminate()
                process.join(timeout=1)
                raise FactorScriptExecutionError("timeout", "script_timeout", "script execution timeout")
            time.sleep(0.05)

        try:
            outcome = result_queue.get_nowait()
        except queue.Empty as exc:
            raise FactorScriptExecutionError("script_error", "script_error", "script worker exited without result") from exc
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=1)
        result_queue.close()

    if outcome["status"] != "success":
        error = outcome.get("error") or {}
        raise FactorScriptExecutionError(
            outcome["status"],
            error.get("code", "script_error"),
            error.get("message", "script execution failed"),
            outcome,
        )
    return outcome["rebalances"]


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
            _run_script_worker_supervised(
                history_frame,
                request,
                rebalance_dates,
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
