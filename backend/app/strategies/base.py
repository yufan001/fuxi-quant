from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Signal:
    code: str
    action: str  # "buy" | "sell"
    price: float
    amount: int
    reason: str = ""


@dataclass
class Position:
    code: str
    amount: int
    cost_price: float
    current_price: float = 0.0
    highest_price: float = 0.0

    @property
    def market_value(self):
        return self.amount * self.current_price

    @property
    def pnl(self):
        return (self.current_price - self.cost_price) * self.amount

    @property
    def pnl_pct(self):
        if self.cost_price == 0:
            return 0
        return (self.current_price - self.cost_price) / self.cost_price * 100


@dataclass
class Context:
    positions: dict = field(default_factory=dict)
    balance: float = 0.0
    total_value: float = 0.0
    history: list = field(default_factory=list)
    date: str = ""
    code: str = ""


class Strategy(ABC):
    name: str = "base"
    params: dict = {}

    def __init__(self, params: dict = None):
        if params:
            self.params = {**self.params, **params}

    @abstractmethod
    def on_bar(self, bar: dict, context: Context) -> list[Signal]:
        ...
