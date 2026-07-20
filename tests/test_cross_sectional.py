import unittest

import pandas as pd

from engine.backtest import Backtest
from engine.strategy import CrossSectionalMomentum


def bars(closes, start="2024-01-01"):
    index = pd.date_range(start, periods=len(closes), freq="D")
    return pd.DataFrame({"Open": closes, "Close": closes}, index=index)


class CrossSectionalMomentumTests(unittest.TestCase):
    def run_bt(self, price_data, **strategy_kwargs):
        return Backtest(
            symbols=list(price_data),
            price_data=price_data,
            initial_capital=10_000,
            strategy_cls=CrossSectionalMomentum,
            strategy_kwargs=strategy_kwargs,
            commission_per_share=0,
            minimum_commission=0,
            slippage_bps=0,
        ).run()

    def test_selects_top_assets_and_fills_next_bar(self):
        data = {
            "A": bars([10, 11, 13, 14, 15, 16]),
            "B": bars([10, 11, 12, 12, 12, 12]),
            "C": bars([10, 9, 8, 8, 8, 8]),
            "D": bars([10, 10, 10, 10, 10, 10]),
        }
        result = self.run_bt(
            data,
            lookback=3,
            skip=1,
            rebalance_every=99,
            top_fraction=0.5,
            gross_allocation=0.8,
        )

        fills = result["fills"]
        self.assertEqual(set(fills["symbol"]), {"A", "B"})
        self.assertTrue((fills["submitted_dt"] < fills["fill_dt"]).all())
        self.assertEqual(set(fills["fill_dt"]), {data["A"].index[4]})

    def test_rotation_sells_before_buy_and_preserves_nonnegative_cash(self):
        data = {
            "A": bars([10, 12, 14, 14, 14, 14]),
            "B": bars([10, 10, 10, 20, 30, 40]),
        }
        result = self.run_bt(
            data,
            lookback=2,
            skip=0,
            rebalance_every=1,
            top_fraction=0.5,
            gross_allocation=0.9,
        )

        fills = result["fills"].reset_index(drop=True)
        rotation = fills[fills["fill_dt"] == data["A"].index[4]]
        self.assertEqual(list(rotation["direction"]), ["SELL", "BUY"])
        self.assertEqual(list(rotation["symbol"]), ["A", "B"])
        self.assertGreaterEqual(result["cash"]["cash"].min(), 0)
        final_b = result["positions"].query("symbol == 'B'").iloc[-1]
        self.assertGreater(final_b["quantity"], 0)

    def test_skip_excludes_most_recent_return_from_rank(self):
        data = {
            "STEADY": bars([10, 12, 14, 14, 14]),
            "JUMP": bars([10, 10, 10, 100, 100]),
        }
        result = self.run_bt(
            data,
            lookback=3,
            skip=1,
            rebalance_every=99,
            top_fraction=0.5,
        )
        self.assertEqual(set(result["fills"]["symbol"]), {"STEADY"})

    def test_rejects_invalid_configuration(self):
        data = {"A": bars([10, 11]), "B": bars([10, 11])}
        with self.assertRaises(ValueError):
            Backtest(
                symbols=list(data),
                price_data=data,
                strategy_cls=CrossSectionalMomentum,
                strategy_kwargs={"lookback": 2, "skip": 2},
            )


if __name__ == "__main__":
    unittest.main()
