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

