from app.strategies.base import Strategy, Signal, Context


class BollingerStrategy(Strategy):
    name = "bollinger"
    params = {"period": 20, "std": 2}

    def on_bar(self, bar: dict, context: Context) -> list[Signal]:
        signals = []
        history = context.history
        period = self.params["period"]

        if len(history) < period + 1:
            return signals

        closes = [h["close"] for h in history[-period:]]
        ma = sum(closes) / period
        variance = sum((c - ma) ** 2 for c in closes) / period
        std = variance ** 0.5
        upper = ma + self.params["std"] * std
        lower = ma - self.params["std"] * std

        code = bar["code"]
        price = bar["close"]
        prev_price = history[-2]["close"]
        in_position = code in context.positions

        if prev_price >= lower and price < lower and not in_position:
            # Price breaks below lower band — potential reversal buy
            pass
        if prev_price <= lower and price > lower and not in_position:
            amount = int(context.balance * 0.9 / price / 100) * 100
            if amount >= 100:
                signals.append(Signal(code=code, action="buy", price=price, amount=amount, reason=f"突破布林带下轨({lower:.2f})"))

        elif prev_price <= upper and price > upper and in_position:
            pos = context.positions[code]
            signals.append(Signal(code=code, action="sell", price=price, amount=pos.amount, reason=f"触及布林带上轨({upper:.2f})"))

        return signals
