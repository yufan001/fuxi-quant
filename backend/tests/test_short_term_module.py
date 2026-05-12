import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.jobs import (
    ShortTermBacktestRequest,
    ShortTermDateJobRequest,
    ShortTermImportCsvRequest,
    submit_short_term_backtest_job,
    submit_short_term_import_csv_job,
    submit_short_term_score_auction_job,
)
from app.core.job_handlers import register_job_handlers
from app.models.db import init_biz_db
from app.short_term.data_sources.csv_source import CsvShortTermSource
from app.short_term.ocr.parser import parse_rank_rows
from app.short_term.strategy.candidate_filter import build_candidates
from app.short_term.strategy.scoring import score_candidate


class FakeManager:
    def __init__(self):
        self.calls = []
        self.registered = []

    def submit(self, job_type, payload, callback=None, run_async=True):
        self.calls.append({"job_type": job_type, "payload": payload, "callback": callback, "run_async": run_async})
        return "job_short_term_1"

    def register(self, job_type, handler):
        self.registered.append(job_type)


class ShortTermCandidateFilterTests(unittest.TestCase):
    def test_build_candidates_keeps_visible_weak_board_only(self):
        rows = [
            {
                "code": "sh.600001",
                "trade_date": "2026-05-11",
                "name": "样例一",
                "sector": "机器人",
                "touched_limit": "1",
                "limit_hit_count": "2",
                "limit_open_count": "3",
                "visible_open_seconds": "90",
                "closed_at_limit": "1",
            },
            {
                "code": "sz.000001",
                "trade_date": "2026-05-11",
                "touched_limit": "1",
                "limit_hit_count": "1",
                "limit_open_count": "1",
                "visible_open_seconds": "0",
            },
        ]

        candidates = build_candidates(rows)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["code"], "sh.600001")
        self.assertEqual(candidates[0]["candidate_type"], "weak_sealed_board")
        self.assertGreaterEqual(candidates[0]["score_prev_day"], 20)


class ShortTermScoringTests(unittest.TestCase):
    def test_score_candidate_combines_auction_sector_rank_and_open_support(self):
        candidate = build_candidates([
            {
                "code": "sh.600001",
                "trade_date": "2026-05-11",
                "sector": "机器人",
                "touched_limit": "1",
                "limit_hit_count": "2",
                "limit_open_count": "3",
                "visible_open_seconds": "90",
                "closed_at_limit": "1",
            }
        ])[0]
        auction = {
            "code": "sh.600001",
            "trade_date": "2026-05-12",
            "sector": "机器人",
            "auction_gap_pct": 3.5,
            "auction_amount": 28_000_000,
            "auction_volume_vs_prev_day_pct": 2.0,
            "limit_buy_rank": 8,
        }
        sector = {"sector_name": "机器人", "trade_date": "2026-05-12", "sector_rank": 4, "sector_limit_up_count": 5}
        open_snapshot = {
            "code": "sh.600001",
            "trade_date": "2026-05-12",
            "hold_above_auction": 1,
            "hold_above_vwap": 1,
            "pullback_pct": 0.8,
            "amount_1m": 32_000_000,
        }

        score = score_candidate(candidate, auction, sector, open_snapshot, phase="open")

        self.assertEqual(score["trade_date"], "2026-05-12")
        self.assertEqual(score["score_breakdown"]["buy_order_rank"], 15)
        self.assertGreaterEqual(score["total_score"], 80)
        self.assertTrue(any("竞价涨停委买榜" in reason for reason in score["reasons"]))


class ShortTermCsvSourceTests(unittest.TestCase):
    def test_csv_source_parses_candidate_and_auction_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            candidate_path = Path(tmpdir) / "candidates.csv"
            candidate_path.write_text(
                "code,trade_date,touched_limit,limit_hit_count,limit_open_count,visible_open_seconds,closed_at_limit\n"
                "sh.600001,2026-05-11,1,2,3,90,1\n",
                encoding="utf-8",
            )
            auction_path = Path(tmpdir) / "auction.csv"
            auction_path.write_text(
                "code,trade_date,auction_price,prev_close,auction_amount,auction_volume_vs_prev_day_pct,limit_buy_rank\n"
                "sh.600001,2026-05-12,10.35,10.00,28000000,2.0,8\n",
                encoding="utf-8",
            )

            source = CsvShortTermSource()
            candidates = source.read("candidates", candidate_path)
            auctions = source.read("auction", auction_path)

        self.assertEqual(len(candidates), 1)
        self.assertAlmostEqual(auctions[0]["auction_gap_pct"], 3.5)
        self.assertEqual(auctions[0]["limit_buy_rank"], 8)


class ShortTermOcrParserTests(unittest.TestCase):
    def test_parse_rank_rows_marks_unparsed_rows_for_review(self):
        rows = parse_rank_rows("1 600001 样例一\n无法识别的一行")

        self.assertEqual(rows[0]["rank"], "1")
        self.assertEqual(rows[0]["code"], "600001")
        self.assertEqual(rows[1]["data_quality"], "needs_review")


class ShortTermDbTests(unittest.TestCase):
    def test_init_biz_db_creates_short_term_tables(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()

        def make_conn():
            conn = sqlite3.connect(tmp.name)
            conn.row_factory = sqlite3.Row
            return conn

        try:
            with patch("app.models.db.get_biz_db", side_effect=make_conn):
                init_biz_db()
            conn = make_conn()
            names = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            conn.close()
        finally:
            os.unlink(tmp.name)

        self.assertIn("short_term_candidates", names)
        self.assertIn("short_term_scores", names)
        self.assertIn("short_term_alerts", names)


class ShortTermJobApiTests(unittest.TestCase):
    def test_short_term_job_handlers_are_registered(self):
        manager = FakeManager()
        register_job_handlers(manager)

        self.assertIn("short_term_import_csv", manager.registered)
        self.assertIn("short_term_score_auction", manager.registered)
        self.assertIn("short_term_backtest", manager.registered)

    def test_short_term_import_endpoint_enqueues_job(self):
        manager = FakeManager()
        request = ShortTermImportCsvRequest(data_type="auction", source_path="data/short_term/sample_auction.csv")

        with patch("app.api.jobs.get_job_manager", return_value=manager):
            response = submit_short_term_import_csv_job(request)

        self.assertEqual(response["data"]["job_id"], "job_short_term_1")
        self.assertEqual(manager.calls[0]["job_type"], "short_term_import_csv")
        self.assertEqual(manager.calls[0]["payload"]["data_type"], "auction")

    def test_short_term_score_and_backtest_endpoints_enqueue_jobs(self):
        manager = FakeManager()

        with patch("app.api.jobs.get_job_manager", return_value=manager):
            submit_short_term_score_auction_job(ShortTermDateJobRequest(trade_date="2026-05-12", candidate_date="2026-05-11"))
            submit_short_term_backtest_job(ShortTermBacktestRequest(start_date="2026-05-01", end_date="2026-05-31"))

        self.assertEqual(manager.calls[0]["job_type"], "short_term_score_auction")
        self.assertEqual(manager.calls[1]["job_type"], "short_term_backtest")


if __name__ == "__main__":
    unittest.main()
