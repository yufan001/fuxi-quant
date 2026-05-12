from __future__ import annotations

import re


def parse_rank_rows(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        normalized = " ".join(line.strip().split())
        if not normalized:
            continue
        match = re.search(r"(?P<rank>\d+)\s+(?P<code>\d{6})\s+(?P<name>\S+)", normalized)
        if not match:
            rows.append({"raw_text": line, "data_quality": "needs_review"})
            continue
        rows.append({**match.groupdict(), "data_quality": "normal"})
    return rows
