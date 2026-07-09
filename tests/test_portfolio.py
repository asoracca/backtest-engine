"""Unit tests for portfolio accounting — run: python tests/test_portfolio.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import queue
from engine.events import FillEvent
from engine.portfolio import Portfolio


class StubData:
    symbols = ["X"]
    current_dt = "2020-01-01"

    def get_latest_close(self, s):
        return 100.0


def test_accounting():
    p = Portfolio(StubData(), queue.Queue(), initial_capital=100000.0)
    p.update_fill(FillEvent("2020-01-01", "X", 10, "BUY", 100.0, 1.0))
    assert p.positions["X"] == 10
    assert abs(p.cash - (100000 - 1000 - 1)) < 1e-6
    p.update_timeindex(None)
    _, eq = p.equity_curve[-1]
    assert abs(eq - (p.cash + 10 * 100)) < 1e-6
    p.update_fill(FillEvent("2020-01-02", "X", 10, "SELL", 100.0, 1.0))
    assert p.positions["X"] == 0
    assert abs(p.cash - (100000 - 2)) < 1e-6
    print("all portfolio tests passed")


if __name__ == "__main__":
    test_accounting()
