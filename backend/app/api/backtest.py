from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.core.engine import BacktestEngine
from app.data.storage import MarketStorage

router = APIRouter()

STRATEGY_MAP = {
    "ma_cross": ("app.strategies.tech.ma_cross", "MACrossStrategy"),
    "macd": ("app.strategies.tech.macd", "MACDStrategy"),
    "rsi": ("app.strategies.tech.rsi", "RSIStrategy"),
    "bollinger": ("app.strategies.tech.bollinger", "BollingerStrategy"),
    "platform_breakout": ("app.strategies.pattern.platform_breakout", "PlatformBreakoutStrategy"),
}


class BacktestConfig(BaseModel):
    strategy: str
    code: str
    start_date: str
    end_date: str
    capital: float = 100000
    params: Optional[dict] = None


@router.post("/run")
def run_backtest(config: BacktestConfig):
    if config.strategy not in STRATEGY_MAP:
        return {"error": f"Unknown strategy: {config.strategy}"}

    module_path, class_name = STRATEGY_MAP[config.strategy]
    import importlib
    module = importlib.import_module(module_path)
    strategy_class = getattr(module, class_name)
    strategy = strategy_class(config.params)

    storage = MarketStorage()
    data = storage.get_daily(config.code, config.start_date, config.end_date)
    if not data:
        return {"error": "No data found for the given code and date range"}

    engine = BacktestEngine(capital=config.capital)
    result = engine.run(strategy, data, config.code)

    return {
        "data": {
            "metrics": result.metrics,
            "trades": result.trades,
            "equity_curve": result.equity_curve,
        }
    }


@router.get("/strategies")
def list_strategies():
    strategies = [
        {"id": "ma_cross", "name": "均线交叉", "params": {"short": 5, "long": 20}},
        {"id": "macd", "name": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9}},
        {"id": "rsi", "name": "RSI", "params": {"period": 14, "overbought": 70, "oversold": 30}},
        {"id": "bollinger", "name": "布林带突破", "params": {"period": 20, "std": 2}},
        {"id": "platform_breakout", "name": "强势平台启动", "params": {"days": 20, "amplitude": 10}},
    ]
    return {"data": strategies}
