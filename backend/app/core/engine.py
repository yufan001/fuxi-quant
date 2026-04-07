from dataclasses import dataclass, field
from app.strategies.base import Strategy, Context, Position, Signal
from app.risk.manager import RiskManager
from app.risk.position import PositionConfig
from app.risk.rules import StopLossConfig
import math


@dataclass
class Trade:
    date: str
    code: str
    action: str
    price: float
    amount: int
    cost: float = 0.0
    pnl: float = None


@dataclass
class BacktestResult:
    metrics: dict = field(default_factory=dict)
    trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)


class BacktestEngine:
    COMMISSION_RATE = 0.00025  # 万2.5
    MIN_COMMISSION = 5.0
    STAMP_TAX_RATE = 0.001    # 千1 (卖出)
    TRANSFER_FEE_RATE = 0.00001  # 十万分之一
    SLIPPAGE = 0.001  # 0.1%

    def __init__(self, capital: float = 100000, risk_enabled: bool = True):
        self.initial_capital = capital
        self.balance = capital
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []
        self.equity_curve: list[dict] = []
        self.peak_equity = capital
        self.risk_enabled = risk_enabled
        if risk_enabled:
            # For single-stock backtests, relax position limits
            backtest_position_config = PositionConfig(
                max_single_position_pct=0.95,
                max_daily_trade_pct=0.95,
            )
            self.risk_manager = RiskManager(position_config=backtest_position_config)
        else:
            self.risk_manager = None

    def _calc_buy_cost(self, price: float, amount: int) -> float:
        total = price * amount
        commission = max(total * self.COMMISSION_RATE, self.MIN_COMMISSION)
        transfer = total * self.TRANSFER_FEE_RATE
        return commission + transfer

    def _calc_sell_cost(self, price: float, amount: int) -> float:
        total = price * amount
        commission = max(total * self.COMMISSION_RATE, self.MIN_COMMISSION)
        stamp_tax = total * self.STAMP_TAX_RATE
        transfer = total * self.TRANSFER_FEE_RATE
        return commission + stamp_tax + transfer

    def _execute_buy(self, signal: Signal, bar: dict):
        exec_price = signal.price * (1 + self.SLIPPAGE)
        total = exec_price * signal.amount
        cost = self._calc_buy_cost(exec_price, signal.amount)

        if total + cost > self.balance:
            affordable = int(self.balance / (exec_price * (1 + self.COMMISSION_RATE + self.TRANSFER_FEE_RATE)) / 100) * 100
            if affordable < 100:
                return
            signal.amount = affordable
            total = exec_price * signal.amount
            cost = self._calc_buy_cost(exec_price, signal.amount)

        self.balance -= (total + cost)

        if signal.code in self.positions:
            pos = self.positions[signal.code]
            total_amount = pos.amount + signal.amount
            pos.cost_price = (pos.cost_price * pos.amount + exec_price * signal.amount) / total_amount
            pos.amount = total_amount
        else:
            self.positions[signal.code] = Position(
                code=signal.code, amount=signal.amount,
                cost_price=exec_price, current_price=exec_price,
                highest_price=exec_price,
            )

        self.trades.append(Trade(
            date=bar["date"], code=signal.code, action="buy",
            price=exec_price, amount=signal.amount, cost=cost,
        ))

    def _execute_sell(self, signal: Signal, bar: dict):
        if signal.code not in self.positions:
            return
        pos = self.positions[signal.code]
        sell_amount = min(signal.amount, pos.amount)
        exec_price = signal.price * (1 - self.SLIPPAGE)
        total = exec_price * sell_amount
        cost = self._calc_sell_cost(exec_price, sell_amount)
        pnl = (exec_price - pos.cost_price) * sell_amount - cost

        self.balance += (total - cost)

        self.trades.append(Trade(
            date=bar["date"], code=signal.code, action="sell",
            price=exec_price, amount=sell_amount, cost=cost, pnl=pnl,
        ))

        pos.amount -= sell_amount
        if pos.amount <= 0:
            del self.positions[signal.code]

    def _total_equity(self):
        equity = self.balance
        for pos in self.positions.values():
            equity += pos.current_price * pos.amount
        return equity

    def run(self, strategy: Strategy, data: list[dict], code: str) -> BacktestResult:
        context = Context(balance=self.balance, code=code)
        history = []
        last_date = None

        for i, bar in enumerate(data):
            bar["code"] = code
            history.append(bar)
            context.history = history
            context.balance = self.balance
            context.positions = self.positions
            context.date = bar["date"]

            # Reset daily risk counters on new trading day
            if self.risk_manager and bar["date"] != last_date:
                self.risk_manager.reset_daily(self._total_equity())
                last_date = bar["date"]

            for pos in self.positions.values():
                pos.current_price = bar["close"]
                pos.highest_price = max(pos.highest_price, bar["close"])

            equity = self._total_equity()
            context.total_value = equity

            # Check stop loss signals from risk manager
            if self.risk_manager and self.positions:
                stop_signals = self.risk_manager.check_stop_loss(self.positions, equity)
                for signal in stop_signals:
                    self._execute_sell(signal, bar)

            # Get strategy signals
            signals = strategy.on_bar(bar, context)

            for signal in signals:
                if signal.action == "buy":
                    if self.risk_manager:
                        ok, reason = self.risk_manager.check_buy_signal(signal, self._total_equity(), self.positions)
                        if not ok:
                            continue
                    self._execute_buy(signal, bar)
                    if self.risk_manager:
                        self.risk_manager.on_trade_executed(signal.price * signal.amount)
                elif signal.action == "sell":
                    self._execute_sell(signal, bar)

            equity = self._total_equity()
            self.peak_equity = max(self.peak_equity, equity)

            self.equity_curve.append({
                "date": bar["date"],
                "equity": equity,
                "benchmark": data[0]["close"] and (bar["close"] / data[0]["close"] * self.initial_capital) or equity,
            })

        return self._build_result(data)

    def _build_result(self, data) -> BacktestResult:
        sell_trades = [t for t in self.trades if t.action == "sell" and t.pnl is not None]

        total_return = (self._total_equity() - self.initial_capital) / self.initial_capital * 100

        if len(data) > 1:
            days = len(data)
            years = days / 252
            annual_return = ((1 + total_return / 100) ** (1 / max(years, 0.01)) - 1) * 100 if years > 0 else 0
        else:
            annual_return = 0

        max_drawdown = 0
        peak = self.initial_capital
        for point in self.equity_curve:
            peak = max(peak, point["equity"])
            dd = (peak - point["equity"]) / peak * 100
            max_drawdown = max(max_drawdown, dd)

        win_trades = [t for t in sell_trades if t.pnl > 0]
        win_rate = len(win_trades) / len(sell_trades) * 100 if sell_trades else 0

        avg_win = sum(t.pnl for t in win_trades) / len(win_trades) if win_trades else 0
        lose_trades = [t for t in sell_trades if t.pnl <= 0]
        avg_loss = abs(sum(t.pnl for t in lose_trades) / len(lose_trades)) if lose_trades else 1
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        daily_returns = []
        for i in range(1, len(self.equity_curve)):
            prev = self.equity_curve[i - 1]["equity"]
            curr = self.equity_curve[i]["equity"]
            daily_returns.append((curr - prev) / prev if prev > 0 else 0)

        if daily_returns:
            avg_ret = sum(daily_returns) / len(daily_returns)
            std_ret = (sum((r - avg_ret) ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5
            sharpe_ratio = (avg_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0
        else:
            sharpe_ratio = 0

        metrics = {
            "total_return": round(total_return, 2),
            "annual_return": round(annual_return, 2),
            "max_drawdown": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "win_rate": round(win_rate, 1),
            "profit_loss_ratio": round(profit_loss_ratio, 2),
            "total_trades": len(self.trades),
            "final_equity": round(self._total_equity(), 2),
        }

        trades = [
            {
                "date": t.date, "code": t.code, "action": t.action,
                "price": round(t.price, 2), "amount": t.amount,
                "pnl": round(t.pnl, 2) if t.pnl is not None else None,
            }
            for t in self.trades
        ]

        return BacktestResult(metrics=metrics, trades=trades, equity_curve=self.equity_curve)
