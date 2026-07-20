"""Strategy interfaces and deliberately small reference strategies."""

from __future__ import annotations

import math

import numpy as np

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


class EqualWeightBuyAndHold(Strategy):
    """Invest once in an equal-weight basket and then leave it untouched."""

    def __init__(self, data, events, gross_allocation=0.90):
        if not 0 < gross_allocation <= 1:
            raise ValueError("gross_allocation must be in (0, 1]")
        self.data = data
        self.events = events
        self.weight = gross_allocation / len(data.symbols)
        self.invested = False

    def calculate_signals(self, event) -> None:
        if event.type != "MARKET" or self.invested:
            return
        for symbol in self.data.symbols:
            self.events.put(SignalEvent(symbol, event.dt, self.weight))
        self.invested = True


class CrossSectionalMomentum(Strategy):
    """Periodically hold the strongest assets by trailing return.

    A score observed at close[t] uses prices from t-lookback through t-skip.
    Target-weight orders fill no earlier than open[t+1].
    """

    def __init__(
        self,
        data,
        events,
        lookback=252,
        skip=21,
        rebalance_every=21,
        top_fraction=1 / 3,
        gross_allocation=0.90,
    ):
        if lookback < 1:
            raise ValueError("lookback must be positive")
        if not 0 <= skip < lookback:
            raise ValueError("skip must satisfy 0 <= skip < lookback")
        if rebalance_every < 1:
            raise ValueError("rebalance_every must be positive")
        if not 0 < top_fraction <= 1:
            raise ValueError("top_fraction must be in (0, 1]")
        if not 0 < gross_allocation <= 1:
            raise ValueError("gross_allocation must be in (0, 1]")

        self.data = data
        self.events = events
        self.lookback = int(lookback)
        self.skip = int(skip)
        self.rebalance_every = int(rebalance_every)
        self.top_fraction = float(top_fraction)
        self.gross_allocation = float(gross_allocation)
        self.targets = {symbol: 0.0 for symbol in data.symbols}
        self.rebalance_log = []

    def _score(self, symbol):
        closes = self.data.get_latest_closes(symbol, self.lookback + 1)
        if len(closes) < self.lookback + 1:
            return None
        start = float(closes[0])
        end = float(closes[-self.skip - 1]) if self.skip else float(closes[-1])
        score = end / start - 1.0
        return score if np.isfinite(score) else None

    def calculate_signals(self, event) -> None:
        if event.type != "MARKET" or self.data.i < self.lookback:
            return
        if (self.data.i - self.lookback) % self.rebalance_every:
            return

        scores = {symbol: score for symbol in self.data.symbols if (score := self._score(symbol)) is not None}
        if not scores:
            return

        count = max(1, math.ceil(len(scores) * self.top_fraction))
        winners = set(sorted(scores, key=lambda symbol: (-scores[symbol], symbol))[:count])
        weight = self.gross_allocation / len(winners)
        new_targets = {symbol: weight if symbol in winners else 0.0 for symbol in self.data.symbols}

        # Submit reductions first so their conservative expected proceeds can
        # fund purchases. The broker preserves this order at the next open.
        changed = [
            symbol
            for symbol in self.data.symbols
            if not math.isclose(new_targets[symbol], self.targets[symbol], abs_tol=1e-12)
        ]
        changed.sort(key=lambda symbol: new_targets[symbol] - self.targets[symbol])
        for symbol in changed:
            self.events.put(SignalEvent(symbol, event.dt, new_targets[symbol]))

        self.rebalance_log.append(
            {
                "dt": event.dt,
                "winners": tuple(sorted(winners)),
                "scores": scores.copy(),
                "targets": new_targets.copy(),
            }
        )
        self.targets = new_targets
