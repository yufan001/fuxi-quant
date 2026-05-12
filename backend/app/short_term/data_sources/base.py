from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class ShortTermDataSource(ABC):
    @abstractmethod
    def read(self, data_type: str, path: str | Path) -> list[dict]:
        ...
