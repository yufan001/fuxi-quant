from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class FactorDefinition:
    key: str
    label: str
    direction: str = "higher_better"
    weight: float = 1.0

    def multiplier(self) -> int:
        return -1 if self.direction == "lower_better" else 1


def _zscore(values: dict[str, float]) -> dict[str, float]:
    valid = {code: value for code, value in values.items() if value is not None and isfinite(value)}
    if not valid:
        return {}

    mean = sum(valid.values()) / len(valid)
    variance = sum((value - mean) ** 2 for value in valid.values()) / len(valid)
    if variance == 0:
        return {code: 0.0 for code in valid}

    std = variance ** 0.5
    return {code: (value - mean) / std for code, value in valid.items()}


def combine_factor_scores(raw_values: dict[str, dict[str, float]], definitions: list[FactorDefinition]) -> list[dict]:
    if not definitions:
        return []

    available_codes = None
    normalized_by_factor: dict[str, dict[str, float]] = {}

    for definition in definitions:
        values = raw_values.get(definition.key, {})
        normalized = _zscore(values)
        if definition.multiplier() < 0:
            normalized = {code: -score for code, score in normalized.items()}
        normalized_by_factor[definition.key] = normalized
        codes = set(normalized.keys())
        available_codes = codes if available_codes is None else available_codes & codes

    if not available_codes:
        return []

    ranked = []
    for code in sorted(available_codes):
        factor_scores = {definition.key: normalized_by_factor[definition.key][code] for definition in definitions}
        factor_values = {definition.key: raw_values[definition.key][code] for definition in definitions}
        score = sum(factor_scores[definition.key] * definition.weight for definition in definitions)
        ranked.append(
            {
                "code": code,
                "score": score,
                "factor_scores": factor_scores,
                "factor_values": factor_values,
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked


def rank_stocks(scores: list[dict], top_n: int) -> list[dict]:
    ordered = sorted(scores, key=lambda item: item["score"], reverse=True)
    if top_n <= 0:
        return []
    return ordered[:top_n]
