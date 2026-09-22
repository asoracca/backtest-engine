import unittest

from benchmark import check_accounting, generate_data, make_backtest
from engine.reproducibility import digest, ledger_records


class BenchmarkTests(unittest.TestCase):
    def test_seeded_workload_is_reproducible_and_conserves_cash(self):
        data = generate_data(3, 90, 17)
        first = make_backtest(data, 17).run()
        second = make_backtest(generate_data(3, 90, 17), 17).run()
        check_accounting(first, 1_000_000)
        self.assertEqual(digest(ledger_records(first)), digest(ledger_records(second)))
        self.assertGreater(len(first["fills"]), 0)
