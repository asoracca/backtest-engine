"""Typed events passed through the backtest queue."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class MarketEvent:
    dt: datetime
    type: str = field(default="MARKET", init=False)


@dataclass(frozen=True)
class SignalEvent:
    symbol: str
    dt: datetime
    target_weight: float
    type: str = field(default="SIGNAL", init=False)


@dataclass(frozen=True)
class OrderEvent:
    order_id: str
    symbol: str
    quantity: int
    direction: str
    submitted_dt: datetime
    reference_price: float
    type: str = field(default="ORDER", init=False)


@dataclass(frozen=True)
class FillEvent:
    order_id: str
    submitted_dt: datetime
    dt: datetime
    symbol: str
    quantity: int
    direction: str
    reference_price: float
    fill_price: float
    commission: float
    slippage_cost: float
    type: str = field(default="FILL", init=False)


@dataclass(frozen=True)
class OrderAcceptedEvent:
    order: OrderEvent
    reserved_cash: float
    type: str = field(default="ORDER_ACCEPTED", init=False)


@dataclass(frozen=True)
class OrderRejectedEvent:
    dt: datetime
    order_id: str | None
    symbol: str
    quantity: int
    reason: str
    type: str = field(default="ORDER_REJECTED", init=False)


@dataclass(frozen=True)
class AccountingFillEvent:
    """Actual booked fill, after affordability checks (not a broker proposal)."""

    fill: FillEvent
    cash_flow: float
    cash: float
    position: int
    type: str = field(default="FILL_BOOKED", init=False)


@dataclass(frozen=True)
class ValuationEvent:
    dt: datetime
    cash: float
    reserved_cash: float
    equity: float
    positions: tuple[tuple[str, int, float], ...]
    type: str = field(default="VALUATION", init=False)


@dataclass(frozen=True)
class EventRecord:
    run_id: str
    sequence: int
    event: SignalEvent | OrderAcceptedEvent | OrderRejectedEvent | AccountingFillEvent | ValuationEvent
