import queue
import unittest

import pandas as pd

from engine.backtest import Backtest
from engine.data import DataHandler
from engine.events import SignalEvent
from engine.execution import SimulatedExecutionHandler
from engine.strategy import Strategy


def bars(opens, closes, start="2024-01-01"):
    index = pd.date_range(start, periods=len(opens), freq="D")
    return pd.DataFrame({"Open": opens, "Close": closes}, index=index)


class BuyThenExit(Strategy):
    def __init__(self, data, events, buy_bar=0, exit_bar=None, weight=0.9):
        self.data, self.events = data, events
        self.buy_bar, self.exit_bar, self.weight = buy_bar, exit_bar, weight

    def calculate_signals(self, event):
        if self.data.i == self.buy_bar:
            for symbol in self.data.symbols:
                self.events.put(SignalEvent(symbol, event.dt, self.weight / len(self.data.symbols)))
        if self.exit_bar is not None and self.data.i == self.exit_bar:
            for symbol in self.data.symbols:
                self.events.put(SignalEvent(symbol, event.dt, 0.0))


class EngineTests(unittest.TestCase):
    def run_bt(self, price_data, **kwargs):
        return Backtest(
            symbols=list(price_data),
            price_data=price_data,
            initial_capital=kwargs.pop("initial_capital", 1_000.0),
            strategy_cls=BuyThenExit,
            strategy_kwargs=kwargs.pop("strategy_kwargs", {}),
            **kwargs,
        ).run()

    def test_signal_at_close_fills_next_open(self):
        results = self.run_bt({"X": bars([10, 20, 30], [12, 21, 31])}, slippage_bps=0)
        fill = results["fills"].iloc[0]
        self.assertLess(fill.submitted_dt, fill.fill_dt)
        self.assertEqual(fill.fill_price, 20)

    def test_event_order_fill_precedes_same_bar_exit_signal(self):
        results = self.run_bt(
            {"X": bars([10, 20, 30, 40], [12, 21, 31, 41])},
            slippage_bps=0,
            strategy_kwargs={"exit_bar": 1},
        )
        self.assertEqual(list(results["fills"]["direction"]), ["BUY", "SELL"])
        self.assertEqual(list(results["fills"]["fill_price"]), [20, 30])

    def test_insufficient_cash_never_goes_negative(self):
        results = self.run_bt(
            {"X": bars([1, 1_000, 1_000], [1, 1_000, 1_000])},
            initial_capital=100,
            slippage_bps=0,
        )
        self.assertGreaterEqual(results["cash"]["cash"].min(), 0)
        self.assertIn("gap_exceeded_cash", set(results["rejections"]["reason"]))

    def test_multiple_symbols_reserve_cash(self):
        data = {
            "A": bars([10, 10, 10], [10, 10, 10]),
            "B": bars([20, 20, 20], [20, 20, 20]),
        }
        results = self.run_bt(data, slippage_bps=0)
        self.assertGreaterEqual(results["cash"]["cash"].min(), 0)
        self.assertEqual(set(results["fills"]["symbol"]), {"A", "B"})

    def test_commission_and_directional_slippage(self):
        events = queue.Queue()
        data = DataHandler(events, ["X"], price_data={"X": bars([100, 100], [100, 100])})
        broker = SimulatedExecutionHandler(data, events, commission_per_share=.01, minimum_commission=1, slippage_bps=10)
        data.update_bars()
        events.get()
        from engine.events import OrderEvent
        buy = OrderEvent("O1", "X", 200, "BUY", data.current_dt, 100)
        broker.execute_order(buy)
        data.update_bars()
        market = events.get()
        broker.on_market(market)
        fill = events.get()
        self.assertAlmostEqual(fill.fill_price, 100.1)
        self.assertEqual(fill.commission, 2.0)

    def test_missing_bars_use_common_calendar(self):
        a = bars([10, 11, 12], [10, 11, 12])
        b = bars([20, 22], [20, 22], start="2024-01-02")
        handler = DataHandler(queue.Queue(), ["A", "B"], price_data={"A": a, "B": b})
        self.assertEqual(len(handler.dates), 2)

    def test_final_mark_and_ledgers(self):
        results = self.run_bt({"X": bars([10, 10, 10], [10, 11, 12])}, slippage_bps=0)
        final_cash = results["cash"].iloc[-1]["cash"]
        final_position = results["positions"].iloc[-1]["quantity"]
        self.assertAlmostEqual(results["equity"].iloc[-1]["equity"], final_cash + final_position * 12)
        for ledger in ("orders", "fills", "positions", "cash", "equity", "trades"):
            self.assertFalse(results[ledger].empty, ledger)

    def test_last_bar_order_is_cancelled(self):
        results = self.run_bt(
            {"X": bars([10, 10], [10, 10])},
            strategy_kwargs={"buy_bar": 1},
        )
        self.assertEqual(results["orders"].iloc[0]["status"], "cancelled")
        self.assertIn("end_of_data", set(results["rejections"]["reason"]))


if __name__ == "__main__":
    unittest.main()
