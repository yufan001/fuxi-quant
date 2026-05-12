from __future__ import annotations

from pathlib import Path

from app.short_term.data_sources.base import ShortTermDataSource
from app.short_term.ocr.parser import parse_rank_rows


class ScreenshotShortTermSource(ShortTermDataSource):
    def read(self, data_type: str, path: str | Path) -> list[dict]:
        if data_type != "rank_text":
            raise ValueError(f"unsupported screenshot data_type: {data_type}")
        return parse_rank_rows(Path(path).read_text(encoding="utf-8"))
