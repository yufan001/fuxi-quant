from __future__ import annotations

import json
import uuid
from typing import Any

from app.models.db import get_biz_db


class ShortTermStorage:
    def save_candidates(self, rows: list[dict[str, Any]]):
        if not rows:
            return
        conn = get_biz_db()
        conn.executemany(
            """INSERT OR REPLACE INTO short_term_candidates
               (code, trade_date, name, sector, candidate_type, limit_hit_count, limit_open_count,
                visible_open_seconds, closed_at_limit, first_limit_time, last_limit_time, score_prev_day, notes, data_quality)
               VALUES (:code, :trade_date, :name, :sector, :candidate_type, :limit_hit_count, :limit_open_count,
                :visible_open_seconds, :closed_at_limit, :first_limit_time, :last_limit_time, :score_prev_day, :notes, :data_quality)""",
            [{**row, "closed_at_limit": int(bool(row.get("closed_at_limit")))} for row in rows],
        )
        conn.commit()
        conn.close()

    def save_auction_snapshots(self, rows: list[dict[str, Any]]):
        self._save_snapshots("short_term_auction_snapshots", rows, [
            "code", "trade_date", "captured_at", "name", "sector", "auction_price", "prev_close", "auction_gap_pct",
            "auction_volume", "auction_amount", "auction_volume_vs_prev_day_pct", "limit_buy_rank", "limit_buy_amount",
            "data_source", "data_quality",
        ])

    def save_sector_snapshots(self, rows: list[dict[str, Any]]):
        self._save_snapshots("short_term_sector_snapshots", rows, [
            "sector_name", "trade_date", "captured_at", "sector_rank", "sector_limit_up_count", "sector_avg_gap_pct",
            "sector_auction_amount", "sector_score", "data_source", "data_quality",
        ])

    def save_open_snapshots(self, rows: list[dict[str, Any]]):
        normalized = [{**row, "hold_above_auction": int(bool(row.get("hold_above_auction"))), "hold_above_vwap": int(bool(row.get("hold_above_vwap"))), "large_sell_pressure_flag": int(bool(row.get("large_sell_pressure_flag")))} for row in rows]
        self._save_snapshots("short_term_open_snapshots", normalized, [
            "code", "trade_date", "captured_at", "latest_price", "auction_price", "prev_close", "vwap_1m", "volume_1m",
            "amount_1m", "hold_above_auction", "hold_above_vwap", "pullback_pct", "large_sell_pressure_flag",
            "data_source", "data_quality",
        ])

    def save_scores(self, rows: list[dict[str, Any]]):
        if not rows:
            return
        conn = get_biz_db()
        conn.executemany(
            """INSERT OR REPLACE INTO short_term_scores
               (code, trade_date, phase, total_score, score_breakdown_json, reasons_json, data_quality)
               VALUES (:code, :trade_date, :phase, :total_score, :score_breakdown_json, :reasons_json, :data_quality)""",
            [
                {
                    "code": row["code"],
                    "trade_date": row["trade_date"],
                    "phase": row.get("phase", "preopen"),
                    "total_score": row.get("total_score", 0),
                    "score_breakdown_json": json.dumps(row.get("score_breakdown", {}), ensure_ascii=False),
                    "reasons_json": json.dumps(row.get("reasons", []), ensure_ascii=False),
                    "data_quality": row.get("data_quality", "normal"),
                }
                for row in rows
            ],
        )
        conn.commit()
        conn.close()

    def save_alerts(self, rows: list[dict[str, Any]]):
        if not rows:
            return
        conn = get_biz_db()
        conn.executemany(
            """INSERT OR REPLACE INTO short_term_alerts
               (id, created_at, symbol, trade_date, alert_type, score, message, payload_json, acknowledged)
               VALUES (:id, datetime('now'), :symbol, :trade_date, :alert_type, :score, :message, :payload_json, 0)""",
            [
                {
                    "id": row.get("id") or str(uuid.uuid5(uuid.NAMESPACE_URL, f"{row.get('symbol')}:{row.get('trade_date')}:{row.get('alert_type')}")),
                    "symbol": row.get("symbol"),
                    "trade_date": row.get("trade_date"),
                    "alert_type": row.get("alert_type"),
                    "score": row.get("score", 0),
                    "message": row.get("message", ""),
                    "payload_json": json.dumps(row.get("payload", {}), ensure_ascii=False),
                }
                for row in rows
            ],
        )
        conn.commit()
        conn.close()

    def list_candidates(self, trade_date: str | None = None) -> list[dict[str, Any]]:
        return self._query("short_term_candidates", trade_date=trade_date)

    def list_auction_snapshots(self, trade_date: str | None = None) -> list[dict[str, Any]]:
        return self._query("short_term_auction_snapshots", trade_date=trade_date)

    def list_sector_snapshots(self, trade_date: str | None = None) -> list[dict[str, Any]]:
        return self._query("short_term_sector_snapshots", trade_date=trade_date)

    def list_open_snapshots(self, trade_date: str | None = None) -> list[dict[str, Any]]:
        return self._query("short_term_open_snapshots", trade_date=trade_date)

    def latest_by_code(self, table: str, trade_date: str) -> dict[str, dict[str, Any]]:
        rows = self._query(table, trade_date=trade_date, order_by="captured_at ASC")
        latest = {}
        for row in rows:
            latest[row["code"]] = row
        return latest

    def latest_sector_by_name(self, trade_date: str) -> dict[str, dict[str, Any]]:
        rows = self._query("short_term_sector_snapshots", trade_date=trade_date, order_by="captured_at ASC")
        latest = {}
        for row in rows:
            latest[row["sector_name"]] = row
        return latest

    def _save_snapshots(self, table: str, rows: list[dict[str, Any]], columns: list[str]):
        if not rows:
            return
        placeholders = ", ".join(f":{column}" for column in columns)
        column_sql = ", ".join(columns)
        conn = get_biz_db()
        conn.executemany(
            f"INSERT OR REPLACE INTO {table} ({column_sql}) VALUES ({placeholders})",
            [{column: row.get(column) for column in columns} for row in rows],
        )
        conn.commit()
        conn.close()

    def _query(self, table: str, trade_date: str | None = None, order_by: str = "trade_date ASC") -> list[dict[str, Any]]:
        conn = get_biz_db()
        sql = f"SELECT * FROM {table}"
        params: list[Any] = []
        if trade_date:
            sql += " WHERE trade_date = ?"
            params.append(trade_date)
        sql += f" ORDER BY {order_by}"
        rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
        conn.close()
        return rows
