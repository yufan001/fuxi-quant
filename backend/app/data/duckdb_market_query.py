from pathlib import Path

import duckdb


class DuckDbMarketQuery:
    def __init__(self, parquet_root: Path):
        self.parquet_root = Path(parquet_root)

    def _code_files(self, table: str, codes: list[str]) -> list[Path]:
        table_dir = self.parquet_root / table
        return [table_dir / f"{code}.parquet" for code in codes if (table_dir / f"{code}.parquet").exists()]

    def get_histories(self, codes: list[str], start_date: str | None = None, end_date: str | None = None) -> dict[str, list[dict]]:
        grouped = {code: [] for code in codes}
        files = self._code_files("stock_daily", codes)
        if not files:
            return grouped

        files_sql = ", ".join(f"'{path.as_posix()}'" for path in files)
        filters = [f"code IN ({', '.join('?' for _ in codes)})"]
        params: list = list(codes)
        if start_date:
            filters.append("date >= ?")
            params.append(start_date)
        if end_date:
            filters.append("date <= ?")
            params.append(end_date)

        sql = f"""
            SELECT *
            FROM read_parquet([{files_sql}])
            WHERE {' AND '.join(filters)}
            ORDER BY code ASC, date ASC
        """

        with duckdb.connect() as conn:
            rows = conn.execute(sql, params).fetchdf().to_dict("records")

        for row in rows:
            grouped[row["code"]].append(row)
        return grouped
