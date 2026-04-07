import time
import baostock as bs
import pandas as pd
from app.data.provider import DataProvider
from app.core.config import BAOSTOCK_QPS_LIMIT


class BaostockProvider(DataProvider):

    def __init__(self):
        self._logged_in = False
        self._last_request_time = 0.0
        self._min_interval = 1.0 / BAOSTOCK_QPS_LIMIT

    def login(self):
        if not self._logged_in:
            lg = bs.login()
            if lg.error_code != "0":
                raise RuntimeError(f"baostock login failed: {lg.error_msg}")
            self._logged_in = True

    def logout(self):
        if self._logged_in:
            bs.logout()
            self._logged_in = False

    def _throttle(self):
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _rs_to_df(self, rs) -> pd.DataFrame:
        if rs.error_code != "0":
            raise RuntimeError(f"baostock query error: {rs.error_msg}")
        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        return pd.DataFrame(rows, columns=rs.fields)

    def get_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        self.login()
        self._throttle()
        rs = bs.query_history_k_data_plus(
            code,
            "date,code,open,high,low,close,volume,amount,turn,peTTM,pbMRQ,psTTM,pcfNcfTTM",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3",
        )
        df = self._rs_to_df(rs)
        if df.empty:
            return df

        numeric_cols = ["open", "high", "low", "close", "volume", "amount", "turn", "peTTM", "pbMRQ", "psTTM", "pcfNcfTTM"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def get_stock_list(self, date: str) -> pd.DataFrame:
        self.login()
        self._throttle()
        rs = bs.query_all_stock(day=date)
        df = self._rs_to_df(rs)
        if df.empty:
            return df
        # baostock returns: code, tradeStatus, code_name
        df = df.rename(columns={"code_name": "name", "tradeStatus": "status"})
        df["industry"] = ""
        return df[["code", "name", "industry", "status"]]

    def get_trade_calendar(self, start_date: str, end_date: str) -> pd.DataFrame:
        self.login()
        self._throttle()
        rs = bs.query_trade_dates(start_date=start_date, end_date=end_date)
        df = self._rs_to_df(rs)
        if df.empty:
            return df
        df.columns = ["date", "is_trading_day"]
        df["is_trading_day"] = df["is_trading_day"].astype(int)
        return df
