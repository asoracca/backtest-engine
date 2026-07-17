"""Strategy interface and one deliberately simple moving-average example."""

from __future__ import annotations

from .events import SignalEvent


class Strategy:
    def calculate_signals(self, event) -> None:
        raise NotImplementedError


class MovingAverageCross(Strategy):
    """Emit target weights at the close; fills occur on the next bar."""

    def __init__(self, data, events, short=20, long=50, gross_allocation=0.90):
        if not 0 < short < long:
            raise ValueError("require 0 < short < long")
        if not 0 < gross_allocation <= 1:
            raise ValueError("gross_allocation must be in (0, 1]")
        self.data = data
        self.events = events
        self.short = short
        self.long = long
        self.weight_when_long = gross_allocation / len(data.symbols)
        self.targets = {symbol: 0.0 for symbol in data.symbols}

    def calculate_signals(self, event) -> None:
        if event.type != "MARKET":
            return
        for symbol in self.data.symbols:
            closes = self.data.get_latest_closes(symbol, self.long)
            if len(closes) < self.long:
                continue
            short_average = closes[-self.short :].mean()
            long_average = closes.mean()
            target = self.weight_when_long if short_average > long_average else 0.0
            if target != self.targets[symbol]:
                self.events.put(SignalEvent(symbol, event.dt, target))
                self.targets[symbol] = target
