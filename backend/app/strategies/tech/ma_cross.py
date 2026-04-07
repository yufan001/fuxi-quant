from app.strategies.base import Strategy, Signal, Context


class MACrossStrategy(Strategy):
    name = "ma_cross"
    params = {"short": 5, "long": 20}

    def on_bar(self, bar: dict, context: Context) -> list[Signal]:
        signals = []
        history = context.history
        short_p = self.params["short"]
        long_p = self.params["long"]

        if len(history) < long_p:
            return signals

        closes = [h["close"] for h in history[-long_p:]]
        ma_short = sum(closes[-short_p:]) / short_p
        ma_long = sum(closes) / long_p

        prev_closes = [h["close"] for h in history[-(long_p + 1):-1]]
        if len(prev_closes) < long_p:
            return signals
        prev_ma_short = sum(prev_closes[-short_p:]) / short_p
        prev_ma_long = sum(prev_closes) / long_p

        code = bar["code"]
        price = bar["close"]
        in_position = code in context.positions

        if prev_ma_short <= prev_ma_long and ma_short > ma_long and not in_position:
            amount = int(context.balance * 0.9 / price / 100) * 100
            if amount >= 100:
                signals.append(Signal(code=code, action="buy", price=price, amount=amount, reason=f"MA{short_p}上穿MA{long_p}"))

        elif prev_ma_short >= prev_ma_long and ma_short < ma_long and in_position:
            pos = context.positions[code]
            signals.append(Signal(code=code, action="sell", price=price, amount=pos.amount, reason=f"MA{short_p}下穿MA{long_p}"))

        return signals
