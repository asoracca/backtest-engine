"""Strategy interface + a moving-average crossover example."""
from .events import SignalEvent


class Strategy:
    def calculate_signals(self, event):
        raise NotImplementedError


class MovingAverageCross(Strategy):
    def __init__(self, data, events, short=20, long=50):
        self.data = data
        self.events = events
        self.short = short
        self.long = long
        self.invested = {s: False for s in data.symbols}

    def calculate_signals(self, event):
        if event.type != "MARKET":
            return
        for s in self.data.symbols:
            closes = self.data.get_latest_closes(s, self.long)
            if len(closes) < self.long:
                continue
            sma_s = closes[-self.short:].mean()
            sma_l = closes.mean()
            dt = self.data.current_dt
            if sma_s > sma_l and not self.invested[s]:
                self.events.put(SignalEvent(s, dt, "LONG"))
                self.invested[s] = True
            elif sma_s < sma_l and self.invested[s]:
                self.events.put(SignalEvent(s, dt, "EXIT"))
                self.invested[s] = False
