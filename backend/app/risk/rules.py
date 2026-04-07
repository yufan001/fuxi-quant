from dataclasses import dataclass


@dataclass
class StopLossConfig:
    stock_stop_loss_pct: float = -5.0
    account_daily_stop_pct: float = -3.0
    trailing_stop_pct: float = -8.0


ST_KEYWORDS = ["ST", "*ST", "S*ST", "SST", "S"]
NEW_STOCK_MIN_DAYS = 60


class RiskRules:

    def __init__(self, stop_loss_config: StopLossConfig = None, blacklist: set = None):
        self.stop_loss = stop_loss_config or StopLossConfig()
        self.blacklist = blacklist or set()
        self.daily_start_equity = None
        self.trading_halted = False

    def set_daily_start_equity(self, equity: float):
        self.daily_start_equity = equity
        self.trading_halted = False

    def check_stock_stop_loss(self, code: str, cost_price: float, current_price: float) -> tuple[bool, str]:
        if cost_price <= 0:
            return False, ""
        pnl_pct = (current_price - cost_price) / cost_price * 100
        if pnl_pct <= self.stop_loss.stock_stop_loss_pct:
            return True, f"触发个股止损({pnl_pct:.1f}% <= {self.stop_loss.stock_stop_loss_pct}%)"
        return False, ""

    def check_trailing_stop(self, code: str, highest_price: float, current_price: float) -> tuple[bool, str]:
        if highest_price <= 0:
            return False, ""
        drawdown_pct = (current_price - highest_price) / highest_price * 100
        if drawdown_pct <= self.stop_loss.trailing_stop_pct:
            return True, f"触发追踪止损(从最高{highest_price:.2f}回撤{drawdown_pct:.1f}%)"
        return False, ""

    def check_account_stop(self, current_equity: float) -> tuple[bool, str]:
        if self.daily_start_equity is None or self.daily_start_equity <= 0:
            return False, ""
        daily_pnl_pct = (current_equity - self.daily_start_equity) / self.daily_start_equity * 100
        if daily_pnl_pct <= self.stop_loss.account_daily_stop_pct:
            self.trading_halted = True
            return True, f"触发账户日止损(当日亏损{daily_pnl_pct:.1f}%)"
        return False, ""

    def check_blacklist(self, code: str, name: str = "") -> tuple[bool, str]:
        if code in self.blacklist:
            return True, f"在黑名单中: {code}"
        for kw in ST_KEYWORDS:
            if name.startswith(kw):
                return True, f"ST股票禁止交易: {name}"
        return False, ""

    def check_new_stock(self, listed_days: int) -> tuple[bool, str]:
        if 0 < listed_days < NEW_STOCK_MIN_DAYS:
            return True, f"新股上市不满{NEW_STOCK_MIN_DAYS}天({listed_days}天)"
        return False, ""

    def check_limit(self, open_price: float, close: float, high: float, low: float) -> tuple[bool, str]:
        if open_price > 0 and high == low:
            return True, "一字涨跌停，无法交易"
        return False, ""
