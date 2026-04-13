import sys
import time
from datetime import datetime, timedelta
from app.data.baostock_provider import BaostockProvider
from app.data.storage import MarketStorage
from app.core.config import DATA_START_DATE


class DataDownloader:

    def __init__(self):
        self.provider = BaostockProvider()
        self.storage = MarketStorage()

    def download_stock_list(self):
        today = datetime.now().strftime("%Y-%m-%d")
        print(f"[下载] 股票列表 ({today})...")
        df = self.provider.get_stock_list(today)
        if df.empty:
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            df = self.provider.get_stock_list(yesterday)
        if df.empty:
            print("[警告] 无法获取股票列表")
            return 0

        records = []
        for _, row in df.iterrows():
            records.append({
                "code": row["code"],
                "name": row.get("name", ""),
                "industry": row.get("industry", ""),
                "listed_date": None,
                "delisted_date": None,
                "status": row.get("status", "1"),
            })
        self.storage.save_stock_info(records)
        print(f"[完成] 股票列表: {len(records)} 只")
        return len(records)

    def download_trade_calendar(self):
        today = datetime.now().strftime("%Y-%m-%d")
        print(f"[下载] 交易日历 ({DATA_START_DATE} ~ {today})...")
        df = self.provider.get_trade_calendar(DATA_START_DATE, today)
        if df.empty:
            print("[警告] 无法获取交易日历")
            return 0

        records = [{"date": row["date"], "is_trading_day": int(row["is_trading_day"])} for _, row in df.iterrows()]
        self.storage.save_trade_calendar(records)
        print(f"[完成] 交易日历: {len(records)} 天")
        return len(records)

    def download_daily_data(self, codes: list[str] = None, start_date: str = None, end_date: str = None):
        if codes is None:
            codes = self.storage.get_all_stock_codes()
        if not codes:
            print("[错误] 没有股票代码，请先下载股票列表")
            return

        if start_date is None:
            start_date = DATA_START_DATE
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        total = len(codes)
        downloaded = 0
        failed = []
        updated_codes = []

        print(f"[下载] 日线数据: {total} 只股票 ({start_date} ~ {end_date})")

        for i, code in enumerate(codes):
            existing_latest = self.storage.get_latest_date(code)
            actual_start = start_date
            if existing_latest:
                next_day = (datetime.strptime(existing_latest, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                if next_day > end_date:
                    downloaded += 1
                    continue
                actual_start = next_day

            try:
                df = self.provider.get_daily(code, actual_start, end_date)
                if not df.empty:
                    records = df.to_dict("records")
                    self.storage.save_stock_daily(records)
                    updated_codes.append(code)
                    downloaded += 1
                else:
                    downloaded += 1
            except Exception as e:
                failed.append((code, str(e)))

            progress = (i + 1) / total * 100
            sys.stdout.write(f"\r[进度] {i+1}/{total} ({progress:.1f}%) - 已完成: {downloaded}, 失败: {len(failed)}")
            sys.stdout.flush()

        print()
        print(f"[完成] 下载完成: {downloaded} 成功, {len(failed)} 失败")
        if updated_codes:
            self.storage.rebuild_aggregates(sorted(set(updated_codes)), periods=["weekly", "monthly"])
        if failed:
            print(f"[失败列表] {failed[:10]}{'...' if len(failed) > 10 else ''}")

    def incremental_update(self):
        today = datetime.now().strftime("%Y-%m-%d")
        print(f"[增量更新] {today}")
        self.download_stock_list()
        self.download_trade_calendar()
        codes = self.storage.get_all_stock_codes()
        self.download_daily_data(codes=codes, end_date=today)

    def full_download(self):
        print("=" * 50)
        print("全量数据下载")
        print("=" * 50)
        self.download_stock_list()
        self.download_trade_calendar()
        self.download_daily_data()
        self.provider.logout()
        print("=" * 50)
        print("全量下载完成")
        print("=" * 50)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="量化数据下载工具")
    parser.add_argument("--mode", choices=["full", "update", "test"], default="test", help="下载模式")
    parser.add_argument("--codes", nargs="+", help="指定股票代码")
    args = parser.parse_args()

    downloader = DataDownloader()

    try:
        if args.mode == "full":
            downloader.full_download()
        elif args.mode == "update":
            downloader.incremental_update()
        elif args.mode == "test":
            print("[测试模式] 下载少量数据验证功能")
            downloader.download_stock_list()
            downloader.download_trade_calendar()
            test_codes = args.codes or ["sh.600000", "sh.600036", "sz.000001"]
            downloader.download_daily_data(codes=test_codes)
    finally:
        downloader.provider.logout()


if __name__ == "__main__":
    main()
