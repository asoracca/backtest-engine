"""A deterministic simulated broker with next-open fills."""

from __future__ import annotations

import math

from .events import FillEvent


class SimulatedExecutionHandler:
    def __init__(
        self,
        data,
        events,
        commission_per_share=0.005,
        minimum_commission=1.0,
        slippage_bps=1.0,
    ):
        self.data = data
        self.events = events
        self.commission_per_share = float(commission_per_share)
        self.minimum_commission = float(minimum_commission)
        self.slippage_bps = float(slippage_bps)
        if any(
            not math.isfinite(v) or v < 0
            for v in (self.commission_per_share, self.minimum_commission, self.slippage_bps)
        ):
            raise ValueError("costs must be finite and nonnegative")
        if self.slippage_bps >= 10_000:
            raise ValueError("slippage_bps must be below 10000")
        self.pending_orders = []

    def commission(self, quantity):
        return max(self.minimum_commission, quantity * self.commission_per_share)

    def execute_order(self, event) -> None:
        self.pending_orders.append(event)

    def on_market(self, event) -> None:
        pending, self.pending_orders = self.pending_orders, []
        for order in pending:
            if event.dt <= order.submitted_dt:
                raise ValueError("fill must be strictly after signal timestamp")
            open_price = self.data.get_latest_open(order.symbol)
            sign = 1.0 if order.direction == "BUY" else -1.0
            fill_price = open_price * (1.0 + sign * self.slippage_bps / 10_000.0)
            commission = self.commission(order.quantity)
            self.events.put(
                FillEvent(
                    order_id=order.order_id,
                    submitted_dt=order.submitted_dt,
                    dt=event.dt,
                    symbol=order.symbol,
                    quantity=order.quantity,
                    direction=order.direction,
                    reference_price=open_price,
                    fill_price=fill_price,
                    commission=commission,
                    slippage_cost=abs(fill_price - open_price) * order.quantity,
                )
            )

    def cancel_all(self):
        pending, self.pending_orders = self.pending_orders, []
        return pending
