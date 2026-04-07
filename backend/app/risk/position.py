from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PositionConfig:
    max_single_position_pct: float = 0.20  # 单只股票最大仓位比例
    max_daily_trade_pct: float = 0.50      # 每日最大交易金额比例
    max_holding_count: int = 10            # 最大持仓数量


@dataclass
class StopLossConfig:
    stock_stop_loss_pct: float = -5.0      # 个股止损百分比
    account_daily_stop_pct: float = -3.0   # 账户当日止损百分比
    trailing_stop_pct: float = -8.0        # 追踪止损百分比


class PositionManager:

    def __init__(self, config: PositionConfig = None):
        self.config = config or PositionConfig()
        self.daily_traded_amount = 0.0

    def reset_daily(self):
        self.daily_traded_amount = 0.0

    def check_buy(self, code: str, price: float, amount: int, total_value: float, positions: dict) -> tuple[bool, str]:
        trade_amount = price * amount

        if len(positions) >= self.config.max_holding_count and code not in positions:
            return False, f"超过最大持仓数量限制({self.config.max_holding_count})"

        max_single = total_value * self.config.max_single_position_pct
        existing_value = 0
        if code in positions:
            existing_value = positions[code].current_price * positions[code].amount
        if existing_value + trade_amount > max_single:
            return False, f"超过单只股票最大仓位({self.config.max_single_position_pct*100:.0f}%={max_single:.0f})"

        max_daily = total_value * self.config.max_daily_trade_pct
        if self.daily_traded_amount + trade_amount > max_daily:
            return False, f"超过每日最大交易金额({self.config.max_daily_trade_pct*100:.0f}%={max_daily:.0f})"

        return True, ""

    def record_trade(self, amount: float):
        self.daily_traded_amount += amount
