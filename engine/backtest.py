"""Event-loop orchestration with explicit close-signal/next-open execution."""

from __future__ import annotations

import queue

import pandas as pd

from .data import DataHandler
from .execution import SimulatedExecutionHandler
from .portfolio import Portfolio


class Backtest:
    def __init__(
        self,
        symbols,
        start=None,
        initial_capital=100_000.0,
        strategy_cls=None,
        end=None,
        price_data=None,
        commission_per_share=0.005,
        minimum_commission=1.0,
        slippage_bps=1.0,
        strategy_kwargs=None,
        **legacy_strategy_kwargs,
    ):
        if strategy_cls is None:
            raise ValueError("strategy_cls is required")
        self.events = queue.Queue()
        self.data = DataHandler(self.events, symbols, start, end, price_data=price_data)
        kwargs = dict(strategy_kwargs or {})
        kwargs.update(legacy_strategy_kwargs)
        self.strategy = strategy_cls(self.data, self.events, **kwargs)
        self.portfolio = Portfolio(self.data, self.events, initial_capital)
        self.execution = SimulatedExecutionHandler(
            self.data,
            self.events,
            commission_per_share=commission_per_share,
            minimum_commission=minimum_commission,
            slippage_bps=slippage_bps,
        )

    def run(self):
        while self.data.continue_backtest:
            self.data.update_bars()
            if not self.data.continue_backtest:
                break
            market_event = None
            while True:
                try:
                    event = self.events.get_nowait()
                except queue.Empty:
                    break
                if event.type == "MARKET":
                    market_event = event
                    self.execution.on_market(event)
                    self.strategy.calculate_signals(event)
                elif event.type == "SIGNAL":
                    self.portfolio.update_signal(event)
                elif event.type == "ORDER":
                    self.execution.execute_order(event)
                elif event.type == "FILL":
                    self.portfolio.update_fill(event)
            if market_event is not None:
                self.portfolio.mark_to_market(market_event)

        for order in self.execution.cancel_all():
            self.portfolio.cancel_order(order)
        return self.results()

    def results(self):
        return {
            "equity": pd.DataFrame(self.portfolio.equity_curve),
            "orders": pd.DataFrame(self.portfolio.orders),
            "fills": pd.DataFrame(self.portfolio.fills),
            "trades": pd.DataFrame(self.portfolio.trades),
            "positions": pd.DataFrame(self.portfolio.positions_ledger),
            "cash": pd.DataFrame(self.portfolio.cash_ledger),
            "rejections": pd.DataFrame(self.portfolio.rejections),
        }
