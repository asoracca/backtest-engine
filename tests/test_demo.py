import unittest
from pathlib import Path

from engine.demo import demo_backtest, render_demo


class DemoTests(unittest.TestCase):
    def test_golden_output_and_conservation(self):
        result = demo_backtest().run()
        expected = Path(__file__).resolve().parents[1] / "fixtures/synthetic/expected.txt"
        self.assertEqual(render_demo(result), expected.read_text())
        self.assertIn("insufficient_cash", set(result["rejections"].reason))
        self.assertEqual(list(result["fills"].direction), ["BUY", "SELL"])
        cash = 100.0
        for row in result["cash"].itertuples():
            cash += result["fills"].loc[result["fills"].fill_dt == row.dt, "cash_flow"].sum()
            self.assertAlmostEqual(row.cash, cash)
            marked = result["positions"].loc[result["positions"].dt == row.dt, "market_value"].sum()
            self.assertAlmostEqual(row.equity, cash + marked)
