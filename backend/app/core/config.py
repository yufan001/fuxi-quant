import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"
MARKET_DB_PATH = DATA_DIR / "market" / "market.db"
MARKET_PARQUET_DIR = DATA_DIR / "market" / "parquet"
MARKET_DAILY_PARQUET_DIR = MARKET_PARQUET_DIR / "stock_daily"
MARKET_WEEKLY_PARQUET_DIR = MARKET_PARQUET_DIR / "stock_weekly"
MARKET_MONTHLY_PARQUET_DIR = MARKET_PARQUET_DIR / "stock_monthly"
BIZ_DB_PATH = DATA_DIR / "db" / "business.db"

HOST = "0.0.0.0"
PORT = 8000

BAOSTOCK_QPS_LIMIT = 15

FRONTEND_DIR = BASE_DIR / "frontend"

DATA_START_DATE = "2015-01-01"
DAILY_UPDATE_HOUR = 15
DAILY_UPDATE_MINUTE = 30

os.makedirs(DATA_DIR / "market", exist_ok=True)
os.makedirs(DATA_DIR / "db", exist_ok=True)
os.makedirs(MARKET_DAILY_PARQUET_DIR, exist_ok=True)
os.makedirs(MARKET_WEEKLY_PARQUET_DIR, exist_ok=True)
os.makedirs(MARKET_MONTHLY_PARQUET_DIR, exist_ok=True)
