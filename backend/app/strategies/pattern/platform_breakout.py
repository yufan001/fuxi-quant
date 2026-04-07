from app.strategies.base import Strategy, Signal, Context


class PlatformBreakoutStrategy(Strategy):
    name = "platform_breakout"
    params = {"days": 20, "amplitude": 10}

    def on_bar(self, bar: dict, context: Context) -> list[Signal]:
        signals = []
        history = context.history
        days = self.params["days"]
        amplitude = self.params["amplitude"]

        if len(history) < days + 5:
            return signals

        platform = history[-(days + 1):-1]
        highs = [h["high"] for h in platform]
        lows = [h["low"] for h in platform]
        platform_high = max(highs)
        platform_low = min(lows)

        if platform_low == 0:
            return signals

        range_pct = (platform_high - platform_low) / platform_low * 100

        if range_pct > amplitude:
            return signals

        code = bar["code"]
        price = bar["close"]
        in_position = code in context.positions

        if price > platform_high and not in_position:
            amount = int(context.balance * 0.9 / price / 100) * 100
            if amount >= 100:
                signals.append(Signal(
                    code=code, action="buy", price=price, amount=amount,
                    reason=f"强势平台突破(整理{days}日,振幅{range_pct:.1f}%,突破{platform_high:.2f})"
                ))

        elif in_position:
            pos = context.positions[code]
            if price < platform_low:
                signals.append(Signal(
                    code=code, action="sell", price=price, amount=pos.amount,
                    reason=f"跌破平台下沿({platform_low:.2f})"
                ))

        return signals
