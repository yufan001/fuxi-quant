from app.strategies.base import Strategy, Signal, Context


class RSIStrategy(Strategy):
    name = "rsi"
    params = {"period": 14, "overbought": 70, "oversold": 30}

    def _calc_rsi(self, closes, period):
        if len(closes) < period + 1:
            return None
        gains = []
        losses = []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))

        if len(gains) < period:
            return None

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def on_bar(self, bar: dict, context: Context) -> list[Signal]:
        signals = []
        history = context.history
        period = self.params["period"]

        if len(history) < period + 2:
            return signals

        closes = [h["close"] for h in history]
        rsi = self._calc_rsi(closes, period)
        prev_rsi = self._calc_rsi(closes[:-1], period)

        if rsi is None or prev_rsi is None:
            return signals

        code = bar["code"]
        price = bar["close"]
        in_position = code in context.positions

        if prev_rsi <= self.params["oversold"] and rsi > self.params["oversold"] and not in_position:
            amount = int(context.balance * 0.9 / price / 100) * 100
            if amount >= 100:
                signals.append(Signal(code=code, action="buy", price=price, amount=amount, reason=f"RSI从超卖区回升({rsi:.1f})"))

        elif prev_rsi >= self.params["overbought"] and rsi < self.params["overbought"] and in_position:
            pos = context.positions[code]
            signals.append(Signal(code=code, action="sell", price=price, amount=pos.amount, reason=f"RSI从超买区回落({rsi:.1f})"))

        return signals
