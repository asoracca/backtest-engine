"""Orchestrates the event loop that drives the whole simulation."""
import queue
from .data import DataHandler
from .portfolio import Portfolio
from .execution import SimulatedExecutionHandler


class Backtest:
    def __init__(self, symbols, start, initial_capital, strategy_cls, end=None, **strat_kwargs):
        self.events = queue.Queue()
        self.data = DataHandler(self.events, symbols, start, end)
        self.strategy = strategy_cls(self.data, self.events, **strat_kwargs)
        self.portfolio = Portfolio(self.data, self.events, initial_capital)
        self.execution = SimulatedExecutionHandler(self.data, self.events)

    def run(self):
        while self.data.continue_backtest:
            self.data.update_bars()
            if not self.data.continue_backtest:
                break
            while True:
                try:
                    ev = self.events.get(False)
                except queue.Empty:
                    break
                if ev.type == "MARKET":
                    self.strategy.calculate_signals(ev)
                    self.portfolio.update_timeindex(ev)
                elif ev.type == "SIGNAL":
                    self.portfolio.update_signal(ev)
                elif ev.type == "ORDER":
                    self.execution.execute_order(ev)
                elif ev.type == "FILL":
                    self.portfolio.update_fill(ev)
        return self.portfolio.equity_curve
