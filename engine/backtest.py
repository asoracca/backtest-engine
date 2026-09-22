"""Event-loop orchestration with explicit close-signal/next-open execution."""

from __future__ import annotations

import math
import queue
from dataclasses import replace

import pandas as pd

from .data import DataHandler
from .events import EventRecord
from .execution import SimulatedExecutionHandler
from .portfolio import Portfolio
from .reproducibility import TIMING, digest, encode_frames, engine_hash, strategy_hash, versions


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
        calendar_policy="common",
        provenance=None,
        **legacy_strategy_kwargs,
    ):
        if strategy_cls is None:
            raise ValueError("strategy_cls is required")
        if not math.isfinite(initial_capital) or initial_capital <= 0:
            raise ValueError("initial_capital must be finite and positive")
        self.event_records = []
        self.events = queue.Queue()
        self.data = DataHandler(
            self.events, symbols, start, end, price_data=price_data, calendar_policy=calendar_policy
        )
        kwargs = dict(strategy_kwargs or {})
        kwargs.update(legacy_strategy_kwargs)
        self.strategy = strategy_cls(self.data, self.events, **kwargs)

        self.execution = SimulatedExecutionHandler(
            self.data,
            self.events,
            commission_per_share=commission_per_share,
            minimum_commission=minimum_commission,
            slippage_bps=slippage_bps,
        )

        self.portfolio = Portfolio(
            self.data, self.events, initial_capital, record=self._record, commission=self.execution.commission
        )
        self.config = {
            "symbols": self.data.symbols,
            "initial_capital": float(initial_capital),
            "strategy": f"{strategy_cls.__module__}:{strategy_cls.__qualname__}",
            "strategy_kwargs": kwargs,
            "commission_per_share": float(commission_per_share),
            "minimum_commission": float(minimum_commission),
            "slippage_bps": float(slippage_bps),
            "calendar_policy": calendar_policy,
        }
        self.input_snapshot = encode_frames(self.data.source_frames)
        self.provenance = provenance or {
            "kind": "injected" if price_data is not None else "historical",
            "source": "caller DataFrames" if price_data is not None else "yfinance",
            "requested_start": start,
            "requested_end": end,
        }
        self.metadata = {
            "config": self.config,
            "data_hash": digest(self.input_snapshot),
            "config_hash": digest(self.config),
            "timing": TIMING,
            "engine_hash": engine_hash(),
            "strategy_hash": strategy_hash(strategy_cls),
            "versions": versions(),
            "provenance": self.provenance,
            "excluded_dates": self.data.excluded_dates,
        }
        self.run_id = digest(self.metadata)
        self._has_run = False

    def _record(self, event):
        self.event_records.append(EventRecord(self.run_id, len(self.event_records), event))

    def run(self):
        if self._has_run:
            raise RuntimeError("Backtest instances are single-use; construct a fresh run for replay")
        self._has_run = True
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
                    self._record(event)
                    self.portfolio.update_signal(event)
                elif event.type == "ORDER":
                    self.execution.execute_order(event)
                elif event.type == "FILL":
                    self.portfolio.update_fill(event)
            if market_event is not None:
                self.portfolio.mark_to_market(market_event)

        final_valuation = self.event_records[-1].event
        cancelled = self.execution.cancel_all()
        for order in cancelled:
            self.portfolio.cancel_order(order)
        if cancelled:
            # End-of-data cancellation changes reservations, not marked equity.
            self.portfolio.cash_ledger[-1]["reserved_cash"] = self.portfolio.reserved_cash
            self._record(replace(final_valuation, reserved_cash=self.portfolio.reserved_cash))
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
