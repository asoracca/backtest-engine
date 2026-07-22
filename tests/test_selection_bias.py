import unittest

import numpy as np
import pandas as pd

from engine.selection_bias import (
    annualized_sharpe,
    combinatorially_symmetric_cv,
    run_selection_bias_experiment,
    simulate_null_strategies,
)


class SelectionBiasTests(unittest.TestCase):
    def test_annualized_sharpe_is_columnwise(self):
        returns = np.array([[0.01, -0.01], [0.02, 0.01], [0.00, 0.00]])
        scores = annualized_sharpe(returns)
        self.assertEqual(scores.shape, (2,))
        self.assertGreater(scores[0], scores[1])

    def test_cscv_has_all_symmetric_splits(self):
        rng = np.random.default_rng(4)
        returns = pd.DataFrame(rng.normal(size=(40, 3)))
        result = combinatorially_symmetric_cv(returns, n_slices=4)
        self.assertEqual(result.splits, 6)
        self.assertTrue(0 <= result.probability_of_backtest_overfitting <= 1)
        self.assertEqual(len(result.split_results), 6)

    def test_stable_signal_has_low_overfitting_probability(self):
        alternating = np.tile([0.009, 0.011], 40)
        returns = pd.DataFrame(
            {
                "stable": alternating,
                "unstable_a": np.r_[np.full(40, 0.03), np.full(40, -0.03)],
                "unstable_b": np.r_[np.full(40, -0.02), np.full(40, 0.02)],
            }
        )
        result = combinatorially_symmetric_cv(returns, n_slices=8)
        self.assertLess(result.probability_of_backtest_overfitting, 0.25)

    def test_null_simulation_is_reproducible(self):
        first = simulate_null_strategies(20, 4, np.random.default_rng(9))
        second = simulate_null_strategies(20, 4, np.random.default_rng(9))
        pd.testing.assert_frame_equal(first, second)

    def test_experiment_is_reproducible(self):
        first = run_selection_bias_experiment(
            candidate_counts=(3, 6), repetitions=3, observations=40, n_slices=4
        )
        second = run_selection_bias_experiment(
            candidate_counts=(3, 6), repetitions=3, observations=40, n_slices=4
        )
        pd.testing.assert_frame_equal(first[0], second[0])
        pd.testing.assert_frame_equal(first[1], second[1])

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            combinatorially_symmetric_cv(pd.DataFrame({"only": [0.0] * 20}))
        with self.assertRaises(ValueError):
            combinatorially_symmetric_cv(pd.DataFrame({"a": [0.0] * 20, "b": [0.0] * 20}), n_slices=3)


if __name__ == "__main__":
    unittest.main()
