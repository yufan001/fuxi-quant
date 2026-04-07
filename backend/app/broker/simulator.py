import uuid
from datetime import datetime
from app.broker.base import Broker, Order, Balance


class SimBroker(Broker):
    """模拟券商，用于回测和模拟交易"""

    COMMISSION_RATE = 0.00025
    MIN_COMMISSION = 5.0
    STAMP_TAX_RATE = 0.001
    TRANSFER_FEE_RATE = 0.00001

    def __init__(self, initial_capital: float = 100000):
        self.balance_available = initial_capital
        self.balance_frozen = 0.0
        self.positions: dict[str, dict] = {}
        self.orders: list[Order] = []

    def buy(self, code: str, price: float, amount: int) -> Order:
        total = price * amount
        commission = max(total * self.COMMISSION_RATE, self.MIN_COMMISSION)
        transfer_fee = total * self.TRANSFER_FEE_RATE
        cost = total + commission + transfer_fee

        order = Order(
            order_id=str(uuid.uuid4())[:8],
            code=code, action="buy", price=price, amount=amount,
            create_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        if cost > self.balance_available:
            order.status = "failed"
            order.message = "资金不足"
            self.orders.append(order)
            return order

        self.balance_available -= cost
        order.status = "filled"
        order.filled_amount = amount
        order.filled_price = price

        if code in self.positions:
            pos = self.positions[code]
            total_amount = pos["amount"] + amount
            pos["cost_price"] = (pos["cost_price"] * pos["amount"] + price * amount) / total_amount
            pos["amount"] = total_amount
        else:
            self.positions[code] = {"code": code, "amount": amount, "cost_price": price, "current_price": price}

        self.orders.append(order)
        return order

    def sell(self, code: str, price: float, amount: int) -> Order:
        order = Order(
            order_id=str(uuid.uuid4())[:8],
            code=code, action="sell", price=price, amount=amount,
            create_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        if code not in self.positions or self.positions[code]["amount"] < amount:
            order.status = "failed"
            order.message = "持仓不足"
            self.orders.append(order)
            return order

        total = price * amount
        commission = max(total * self.COMMISSION_RATE, self.MIN_COMMISSION)
        stamp_tax = total * self.STAMP_TAX_RATE
        transfer_fee = total * self.TRANSFER_FEE_RATE

        self.balance_available += total - commission - stamp_tax - transfer_fee
        order.status = "filled"
        order.filled_amount = amount
        order.filled_price = price

        self.positions[code]["amount"] -= amount
        if self.positions[code]["amount"] <= 0:
            del self.positions[code]

        self.orders.append(order)
        return order

    def get_positions(self) -> list[dict]:
        return list(self.positions.values())

    def get_balance(self) -> Balance:
        total = self.balance_available + sum(p["current_price"] * p["amount"] for p in self.positions.values())
        return Balance(total=total, available=self.balance_available, frozen=self.balance_frozen)

    def get_orders(self, date: str = None) -> list[Order]:
        if date:
            return [o for o in self.orders if o.create_time.startswith(date)]
        return self.orders

    def cancel_order(self, order_id: str) -> bool:
        for order in self.orders:
            if order.order_id == order_id and order.status == "pending":
                order.status = "cancelled"
                return True
        return False
