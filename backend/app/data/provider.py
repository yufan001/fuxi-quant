from abc import ABC, abstractmethod
import pandas as pd


class DataProvider(ABC):

    @abstractmethod
    def get_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        ...

    @abstractmethod
    def get_stock_list(self, date: str) -> pd.DataFrame:
        ...

    @abstractmethod
    def get_trade_calendar(self, start_date: str, end_date: str) -> pd.DataFrame:
        ...
