from collections.abc import Callable

import pandas as pd

from app.factors.base import FactorDefinition


def _latest_field(field_name: str) -> Callable[[list[dict]], float | None]:
    def reader(history: list[dict]) -> float | None:
        if not history:
            return None
        value = history[-1].get(field_name)
        return None if value is None else float(value)

    return reader


def _momentum(lookback: int) -> Callable[[list[dict]], float | None]:
    def reader(history: list[dict]) -> float | None:
        if len(history) < lookback + 1:
            return None
        start = history[-(lookback + 1)].get("close")
        end = history[-1].get("close")
        if not start or end is None:
            return None
        return float(end) / float(start) - 1

    return reader


FACTOR_REGISTRY = {
    "pb": {"label": "PB", "direction": "lower_better", "calculator": _latest_field("pbMRQ")},
    "pe": {"label": "PE", "direction": "lower_better", "calculator": _latest_field("peTTM")},
    "ps": {"label": "PS", "direction": "lower_better", "calculator": _latest_field("psTTM")},
    "momentum_20": {"label": "20日动量", "direction": "higher_better", "calculator": _momentum(20)},
    "momentum_60": {"label": "60日动量", "direction": "higher_better", "calculator": _momentum(60)},
    "momentum_120": {"label": "120日动量", "direction": "higher_better", "calculator": _momentum(120)},
}


def build_builtin_definitions(configs: list[dict]) -> list[FactorDefinition]:
    definitions = []
    for config in configs:
        key = config["key"]
        meta = FACTOR_REGISTRY[key]
        definitions.append(
            FactorDefinition(
                key=key,
                label=meta["label"],
                direction=meta["direction"],
                weight=float(config.get("weight", 1.0)),
            )
        )
    return definitions


def compute_factor_values(histories_by_code: dict[str, list[dict]], definitions: list[FactorDefinition]) -> dict[str, dict[str, float]]:
    values_by_factor: dict[str, dict[str, float]] = {}
    for definition in definitions:
        calculator = FACTOR_REGISTRY[definition.key]["calculator"]
        factor_values = {}
        for code, history in histories_by_code.items():
            value = calculator(history)
            if value is not None:
                factor_values[code] = value
        values_by_factor[definition.key] = factor_values
    return values_by_factor


def compute_factor_values_from_frame(frame: pd.DataFrame, definitions: list[FactorDefinition]) -> dict[str, dict[str, float]]:
    if frame.empty:
        return {definition.key: {} for definition in definitions}

    ordered = frame.sort_values(["code", "date"]).reset_index(drop=True)
    latest = ordered.groupby("code").tail(1).set_index("code")
    values_by_factor: dict[str, dict[str, float]] = {}

    for definition in definitions:
        if definition.key == "pb":
            values_by_factor[definition.key] = latest["pbMRQ"].dropna().astype(float).to_dict()
        elif definition.key == "pe":
            values_by_factor[definition.key] = latest["peTTM"].dropna().astype(float).to_dict()
        elif definition.key == "ps":
            values_by_factor[definition.key] = latest["psTTM"].dropna().astype(float).to_dict()
        elif definition.key.startswith("momentum_"):
            lookback = int(definition.key.split("_")[1])
            momentum_values = {}
            for code, chunk in ordered.groupby("code"):
                if len(chunk) < lookback + 1:
                    continue
                start = chunk.iloc[-(lookback + 1)]["close"]
                end = chunk.iloc[-1]["close"]
                if start and pd.notna(end):
                    momentum_values[code] = float(end) / float(start) - 1
            values_by_factor[definition.key] = momentum_values
        else:
            raise KeyError(f"unsupported builtin factor for frame path: {definition.key}")

    return values_by_factor
