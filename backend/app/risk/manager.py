from app.risk.position import PositionManager, PositionConfig
from app.risk.rules import RiskRules, StopLossConfig
from app.strategies.base import Signal


class RiskManager:

    def __init__(self, position_config: PositionConfig = None, stop_loss_config: StopLossConfig = None, blacklist: set = None):
        self.position_mgr = PositionManager(position_config)
        self.rules = RiskRules(stop_loss_config, blacklist)

    def reset_daily(self, equity: float):
        self.position_mgr.reset_daily()
        self.rules.set_daily_start_equity(equity)

    def check_buy_signal(self, signal: Signal, total_value: float, positions: dict, stock_name: str = "") -> tuple[bool, str]:
        if self.rules.trading_halted:
            return False, "当日交易已暂停（账户止损）"

        blocked, reason = self.rules.check_blacklist(signal.code, stock_name)
        if blocked:
            return False, reason

        ok, reason = self.position_mgr.check_buy(signal.code, signal.price, signal.amount, total_value, positions)
        if not ok:
            return False, reason

        return True, ""

    def check_sell_signal(self, signal: Signal) -> tuple[bool, str]:
        return True, ""

    def check_stop_loss(self, positions: dict, current_equity: float) -> list[Signal]:
        stop_signals = []

        halted, reason = self.rules.check_account_stop(current_equity)
        if halted:
            for code, pos in positions.items():
                stop_signals.append(Signal(code=code, action="sell", price=pos.current_price, amount=pos.amount, reason=reason))
            return stop_signals

        for code, pos in positions.items():
            triggered, reason = self.rules.check_stock_stop_loss(code, pos.cost_price, pos.current_price)
            if triggered:
                stop_signals.append(Signal(code=code, action="sell", price=pos.current_price, amount=pos.amount, reason=reason))
                continue

            triggered, reason = self.rules.check_trailing_stop(code, pos.highest_price, pos.current_price)
            if triggered:
                stop_signals.append(Signal(code=code, action="sell", price=pos.current_price, amount=pos.amount, reason=reason))

        return stop_signals

    def on_trade_executed(self, amount: float):
        self.position_mgr.record_trade(abs(amount))
