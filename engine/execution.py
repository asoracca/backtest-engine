"""Simulated broker: fills orders at close with slippage + commission."""
from .events import FillEvent


class SimulatedExecutionHandler:
    def __init__(self, data, events, commission_per_share=0.005, slippage_bps=1.0):
        self.data = data
        self.events = events
        self.commission_per_share = commission_per_share
        self.slippage_bps = slippage_bps

    def execute_order(self, event):
        s = event.symbol
        price = self.data.get_latest_close(s)
        sign = 1.0 if event.direction == "BUY" else -1.0
        fill_price = price * (1.0 + sign * self.slippage_bps / 10000.0)
        commission = max(1.0, event.quantity * self.commission_per_share)
        self.events.put(FillEvent(self.data.current_dt, s, event.quantity, event.direction, fill_price, commission))
