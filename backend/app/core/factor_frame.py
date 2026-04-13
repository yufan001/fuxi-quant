import pandas as pd

DEFAULT_FACTOR_COLUMNS = [
    "code",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "turn",
    "peTTM",
    "pbMRQ",
    "psTTM",
    "pcfNcfTTM",
]


def slice_frame_until(frame: pd.DataFrame, as_of_date: str) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    sliced = frame[frame["date"] <= as_of_date].copy()
    return sliced.sort_values(["code", "date"]).reset_index(drop=True)


def frame_to_histories(frame: pd.DataFrame) -> dict[str, list[dict]]:
    if frame.empty:
        return {}
    grouped = {}
    for code, chunk in frame.sort_values(["code", "date"]).groupby("code"):
        grouped[code] = chunk.to_dict("records")
    return grouped
