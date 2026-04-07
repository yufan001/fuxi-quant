from app.strategies.base import Strategy, Signal, Context


class MACDStrategy(Strategy):
    name = "macd"
    params = {"fast": 12, "slow": 26, "signal": 9}

    def _ema(self, values, period):
        if len(values) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = sum(values[:period]) / period
        for v in values[period:]:
            ema = (v - ema) * multiplier + ema
        return ema

    def on_bar(self, bar: dict, context: Context) -> list[Signal]:
        signals = []
        history = context.history
        slow_p = self.params["slow"]
        signal_p = self.params["signal"]
        needed = slow_p + signal_p + 1

        if len(history) < needed:
            return signals

        closes = [h["close"] for h in history]

        def calc_macd(cls):
            fast_ema = self._ema(cls, self.params["fast"])
            slow_ema = self._ema(cls, self.params["slow"])
            if fast_ema is None or slow_ema is None:
                return None, None
            dif = fast_ema - slow_ema
            return dif, None

        difs = []
        for i in range(slow_p, len(closes) + 1):
            sub = closes[:i]
            fast_ema = self._ema(sub, self.params["fast"])
            slow_ema = self._ema(sub, self.params["slow"])
            if fast_ema is not None and slow_ema is not None:
                difs.append(fast_ema - slow_ema)

        if len(difs) < signal_p + 1:
            return signals

        dea = self._ema(difs, signal_p)
        prev_dea = self._ema(difs[:-1], signal_p)
        dif = difs[-1]
        prev_dif = difs[-2]

        if dea is None or prev_dea is None:
            return signals

        code = bar["code"]
        price = bar["close"]
        in_position = code in context.positions

        if prev_dif <= prev_dea and dif > dea and not in_position:
            amount = int(context.balance * 0.9 / price / 100) * 100
            if amount >= 100:
                signals.append(Signal(code=code, action="buy", price=price, amount=amount, reason="MACD金叉"))

        elif prev_dif >= prev_dea and dif < dea and in_position:
            pos = context.positions[code]
            signals.append(Signal(code=code, action="sell", price=price, amount=pos.amount, reason="MACD死叉"))

        return signals
