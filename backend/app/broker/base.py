from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class Order:
    order_id: str
    code: str
    action: str  # "buy" | "sell"
    price: float
    amount: int
    status: str = "pending"  # pending, filled, partial, cancelled, failed
    filled_amount: int = 0
    filled_price: float = 0.0
    create_time: str = ""
    message: str = ""


@dataclass
class Balance:
    total: float
    available: float
    frozen: float = 0.0


class Broker(ABC):

    @abstractmethod
    def buy(self, code: str, price: float, amount: int) -> Order:
        ...

    @abstractmethod
    def sell(self, code: str, price: float, amount: int) -> Order:
        ...

    @abstractmethod
    def get_positions(self) -> list[dict]:
        ...

    @abstractmethod
    def get_balance(self) -> Balance:
        ...

    @abstractmethod
    def get_orders(self, date: str = None) -> list[Order]:
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        ...
