from copy import deepcopy
from dataclasses import dataclass, field

import pandas as pd

from app.core.engine import BacktestEngine
from app.core.factor_frame import frame_to_histories, slice_frame_until
from app.factors.base import combine_factor_scores, rank_stocks
from app.factors.builtin import build_builtin_definitions, compute_factor_values, compute_factor_values_from_frame


@dataclass
class FactorBacktestConfig:
    factor_configs: list[dict]
    top_n: int = 10
    initial_capital: float = 100000.0
    rebalance_dates: list[str] = field(default_factory=list)


@dataclass
class FactorBacktestResult:
    metrics: dict
    equity_curve: list[dict]
    rebalances: list[dict]


COMMISSION_RATE = BacktestEngine.COMMISSION_RATE
MIN_COMMISSION = BacktestEngine.MIN_COMMISSION
STAMP_TAX_RATE = BacktestEngine.STAMP_TAX_RATE
TRANSFER_FEE_RATE = BacktestEngine.TRANSFER_FEE_RATE
SLIPPAGE = BacktestEngine.SLIPPAGE


def _calc_buy_cost(price: float, amount: int) -> float:
    total = price * amount
    commission = max(total * COMMISSION_RATE, MIN_COMMISSION)
    transfer = total * TRANSFER_FEE_RATE
    return commission + transfer


def _calc_sell_cost(price: float, amount: int) -> float:
    total = price * amount
    commission = max(total * COMMISSION_RATE, MIN_COMMISSION)
    stamp_tax = total * STAMP_TAX_RATE
    transfer = total * TRANSFER_FEE_RATE
    return commission + stamp_tax + transfer


def _history_until(history: list[dict], as_of_date: str) -> list[dict]:
    return [row for row in history if row["date"] <= as_of_date]


def _price_on_or_before(history: list[dict], as_of_date: str) -> float | None:
    for row in reversed(history):
        if row["date"] <= as_of_date:
            return float(row["close"])
    return None


def _build_equity_curve(histories_by_code: dict[str, list[dict]], states: list[dict], start_date: str) -> list[dict]:
    all_dates = sorted({row["date"] for history in histories_by_code.values() for row in history})
    equity_curve = []

    for current_date in all_dates:
        if current_date < start_date:
            continue
        active_state = None
        for state in states:
            if state["date"] <= current_date:
                active_state = state
            else:
                break
        if active_state is None:
            continue

        equity = active_state["cash"]
        for code, amount in active_state["positions"].items():
            price = _price_on_or_before(histories_by_code[code], current_date)
            if price is not None:
                equity += price * amount
        equity_curve.append({"date": current_date, "equity": round(equity, 2)})

    return equity_curve


def run_selection_backtest(
    histories_by_code: dict[str, list[dict]],
    rebalances: list[dict],
    initial_capital: float,
    progress_callback=None,
    assert_not_cancelled=None,
) -> FactorBacktestResult:
    cash = float(initial_capital)
    positions: dict[str, int] = {}
    executed_rebalances = []
    states = []

    if not rebalances:
        return FactorBacktestResult(
            metrics={"final_equity": round(cash, 2), "total_return": 0.0, "rebalance_count": 0},
            equity_curve=[],
            rebalances=[],
        )

    total_rebalances = len(rebalances)
    for index, rebalance in enumerate(rebalances, start=1):
        if assert_not_cancelled:
            assert_not_cancelled()
        rebalance_date = rebalance["date"]
        selected = rebalance.get("selected", [])

        for code, amount in list(positions.items()):
            price = _price_on_or_before(histories_by_code[code], rebalance_date)
            if price is None:
                continue
            exec_price = price * (1 - SLIPPAGE)
            cash += exec_price * amount - _calc_sell_cost(exec_price, amount)
            del positions[code]

        valid_selected = [item for item in selected if item.get("code") in histories_by_code]
        if valid_selected:
            total_weight = sum(float(item.get("weight", 0)) for item in valid_selected)
            use_equal_weight = total_weight <= 0

            for item in valid_selected:
                code = item["code"]
                weight = (1 / len(valid_selected)) if use_equal_weight else float(item.get("weight", 0)) / total_weight
                price = _price_on_or_before(histories_by_code[code], rebalance_date)
                if price is None:
                    continue
                exec_price = price * (1 + SLIPPAGE)
                budget = cash * weight if use_equal_weight else (cash + sum(0 for _ in [])) * weight
                lot_size = int(budget / exec_price / 100) * 100
                if lot_size < 100:
                    continue
                total_cost = exec_price * lot_size + _calc_buy_cost(exec_price, lot_size)
                if total_cost > cash:
                    lot_size = int(cash / exec_price / 100) * 100
                    if lot_size < 100:
                        continue
                    total_cost = exec_price * lot_size + _calc_buy_cost(exec_price, lot_size)
                    if total_cost > cash:
                        continue
                cash -= total_cost
                positions[code] = lot_size

        executed_rebalances.append(
            {
                **rebalance,
                "positions": [{"code": code, "amount": amount} for code, amount in positions.items()],
                "cash": round(cash, 2),
            }
        )
        states.append({"date": rebalance_date, "cash": cash, "positions": deepcopy(positions)})
        if progress_callback:
            progress_callback(20 + index / max(total_rebalances, 1) * 70, f'rebalance_{index}_of_{total_rebalances}')

    equity_curve = _build_equity_curve(histories_by_code, states, rebalances[0]["date"])
    final_equity = equity_curve[-1]["equity"] if equity_curve else round(cash, 2)
    total_return = (final_equity - initial_capital) / initial_capital * 100 if initial_capital else 0.0

    return FactorBacktestResult(
        metrics={
            "final_equity": round(final_equity, 2),
            "total_return": round(total_return, 2),
            "rebalance_count": len(executed_rebalances),
        },
        equity_curve=equity_curve,
        rebalances=executed_rebalances,
    )


def run_factor_backtest_from_frame(
    history_frame: pd.DataFrame,
    config: FactorBacktestConfig,
    progress_callback=None,
    assert_not_cancelled=None,
) -> FactorBacktestResult:
    definitions = build_builtin_definitions(config.factor_configs)
    rebalance_dates = sorted(config.rebalance_dates)
    if not rebalance_dates:
        return FactorBacktestResult(
            metrics={"final_equity": round(config.initial_capital, 2), "total_return": 0.0, "rebalance_count": 0},
            equity_curve=[],
            rebalances=[],
        )

    histories_by_code = frame_to_histories(history_frame)
    rebalances = []
    total_rebalances = len(rebalance_dates)
    for index, rebalance_date in enumerate(rebalance_dates, start=1):
        if assert_not_cancelled:
            assert_not_cancelled()
        snapshot_frame = slice_frame_until(history_frame, rebalance_date)
        raw_values = compute_factor_values_from_frame(snapshot_frame, definitions)
        selected = rank_stocks(combine_factor_scores(raw_values, definitions), config.top_n)
        rebalances.append({"date": rebalance_date, "selected": selected})
        if progress_callback:
            progress_callback(10 + index / max(total_rebalances, 1) * 20, f'prepared_rebalance_{index}_of_{total_rebalances}')

    return run_selection_backtest(
        histories_by_code,
        rebalances,
        config.initial_capital,
        progress_callback=progress_callback,
        assert_not_cancelled=assert_not_cancelled,
    )


def run_factor_backtest(
    histories_by_code: dict[str, list[dict]],
    config: FactorBacktestConfig,
    progress_callback=None,
    assert_not_cancelled=None,
) -> FactorBacktestResult:
    history_frame = pd.DataFrame(
        [
            {**row, "code": code}
            for code, history in histories_by_code.items()
            for row in history
        ]
    )
    return run_factor_backtest_from_frame(
        history_frame,
        config,
        progress_callback=progress_callback,
        assert_not_cancelled=assert_not_cancelled,
    )
