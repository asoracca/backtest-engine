"""Tracks cash, positions, and equity; turns signals into orders and fills into P&L."""
from .events import OrderEvent


class Portfolio:
    def __init__(self, data, events, initial_capital=100000.0):
        self.data = data
        self.events = events
        self.symbols = data.symbols
        self.initial_capital = float(initial_capital)
        self.cash = float(initial_capital)
        self.positions = {s: 0 for s in self.symbols}
        self.equity_curve = []

    def update_timeindex(self, event):
        mv = sum(self.positions[s] * self.data.get_latest_close(s) for s in self.symbols)
        self.equity_curve.append((self.data.current_dt, self.cash + mv))

    def update_signal(self, event):
        s = event.symbol
        price = self.data.get_latest_close(s)
        if price <= 0:
            return
        if event.direction == "LONG":
            qty = int((self.cash * 0.95) // price)
            if qty > 0:
                self.events.put(OrderEvent(s, qty, "BUY"))
        elif event.direction in ("EXIT", "SHORT"):
            qty = self.positions[s]
            if qty > 0:
                self.events.put(OrderEvent(s, qty, "SELL"))

    def update_fill(self, event):
        s = event.symbol
        if event.direction == "BUY":
            self.positions[s] += event.quantity
            self.cash -= event.quantity * event.fill_price + event.commission
        else:
            self.positions[s] -= event.quantity
            self.cash += event.quantity * event.fill_price - event.commission
