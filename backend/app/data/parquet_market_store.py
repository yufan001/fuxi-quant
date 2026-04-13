from pathlib import Path

import pandas as pd


class ParquetMarketStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def code_path(self, table: str, code: str) -> Path:
        return self.root / table / f"{code}.parquet"

    def replace_code_rows(self, table: str, code: str, rows: list[dict]):
        file_path = self.code_path(table, code)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if not rows:
            if file_path.exists():
                file_path.unlink()
            return

        frame = pd.DataFrame(rows).sort_values(["date"]).reset_index(drop=True)
        frame.to_parquet(file_path, index=False)

    def table_has_files(self, table: str) -> bool:
        table_dir = self.root / table
        return table_dir.exists() and any(table_dir.glob("*.parquet"))
