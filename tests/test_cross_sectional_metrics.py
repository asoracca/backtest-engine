import unittest

import pandas as pd

from run_cross_sectional import active_performance, annualized_turnover


class CrossSectionalMetricTests(unittest.TestCase):
    def test_annualized_turnover_uses_notional_and_equity(self):
        dates = pd.date_range("2024-01-01", periods=3)
        result = {
            "equity": pd.DataFrame({"dt": dates, "equity": [1_000, 1_000, 1_000]}),
            "fills": pd.DataFrame(
                {
                    "fill_dt": [dates[1], dates[2]],
                    "quantity": [5, 10],
                    "fill_price": [20, 10],
                }
            ),
        }
        self.assertAlmostEqual(annualized_turnover(result), 25.2)

    def test_active_performance_matches_manual_calculation(self):
        dates = pd.date_range("2024-01-01", periods=4)
        momentum = pd.DataFrame({"dt": dates, "equity": [100, 102, 101, 104]})
        benchmark = pd.DataFrame({"dt": dates, "equity": [100, 101, 102, 103]})
        result = active_performance(momentum, benchmark)

        joined = pd.DataFrame(
            {
                "momentum": momentum["equity"].pct_change(),
                "benchmark": benchmark["equity"].pct_change(),
            }
        ).dropna()
        active = joined["momentum"] - joined["benchmark"]
        expected_return = active.mean() * 252
        expected_te = active.std(ddof=1) * (252**0.5)

        self.assertAlmostEqual(result["annualized_active_return"], expected_return)
        self.assertAlmostEqual(result["tracking_error"], expected_te)
        self.assertAlmostEqual(
            result["information_ratio"],
            expected_return / expected_te,
        )

    def test_empty_fills_have_zero_turnover(self):
        result = {
            "equity": pd.DataFrame(
                {
                    "dt": pd.date_range("2024-01-01", periods=2),
                    "equity": [1_000, 1_010],
                }
            ),
            "fills": pd.DataFrame(),
        }
        self.assertEqual(annualized_turnover(result), 0.0)


if __name__ == "__main__":
    unittest.main()
