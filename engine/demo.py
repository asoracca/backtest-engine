"""Tiny synthetic accounting example; never downloads market data."""

from pathlib import Path

import pandas as pd

from .backtest import Backtest
from .events import SignalEvent
from .strategy import Strategy


class DemoStrategy(Strategy):
    def __init__(self, data, events):
        self.data, self.events = data, events

    def calculate_signals(self, event):
        if self.data.i == 0:
            # A reserves almost all cash; B competes for the remainder.
            for symbol in self.data.symbols:
                self.events.put(SignalEvent(symbol, event.dt, 1.0))
        elif self.data.i == 1:
            for symbol in self.data.symbols:
                self.events.put(SignalEvent(symbol, event.dt, 0.0))


def demo_data():
    path = Path(__file__).resolve().parents[1] / "fixtures/synthetic/ohlc.csv"
    frame = pd.read_csv(path, parse_dates=["date"])
    return {
        symbol: group.set_index("date").drop(columns="symbol")
        for symbol, group in frame.groupby("symbol", sort=False)
    }


def demo_backtest():
    return Backtest(
        ["A", "B"],
        price_data=demo_data(),
        initial_capital=100,
        strategy_cls=DemoStrategy,
        commission_per_share=0,
        minimum_commission=1,
        slippage_bps=10,
        provenance={"kind": "synthetic", "source": "fixtures/synthetic/ohlc.csv v1"},
    )


def render_demo(result):
    lines = [
        "SYNTHETIC OHLC: 2 symbols x 4 daily bars; initial cash 100.00",
        "Timing: close[t] signal -> next common open fill -> close mark.",
        "A's Jan 1 close is 10.00; its Jan 2 open is 12.00.",
    ]
    for name in ("orders", "rejections", "fills", "cash", "positions", "equity"):
        lines.extend([f"\n{name.upper()}", result[name].to_csv(index=False, float_format="%.6f").rstrip()])
    lines.append("\nTIMELINE")
    for row in result["cash"].itertuples():
        day = str(row.dt.date())
        fills = result["fills"]
        for fill in fills[fills.fill_dt == row.dt].itertuples():
            lines.append(
                f"{day} OPEN {fill.direction} {fill.quantity} {fill.symbol} at "
                f"{fill.fill_price:.3f}: cash flow {fill.cash_flow:.6f}"
            )
        lines.append(
            f"{day} CLOSE cash={row.cash:.6f} reserved={row.reserved_cash:.6f} equity={row.equity:.6f}"
        )
    return "\n".join(lines) + "\n"
