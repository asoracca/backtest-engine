import queue
import sqlite3
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import pandas as pd

from engine.backtest import Backtest
from engine.data import DataHandler
from engine.demo import DemoStrategy, demo_backtest, demo_data
from engine.experiments import record_run, replay
from engine.metrics import performance
from engine.reproducibility import canonical
from engine.storage import MemoryStore, SQLiteStore, snapshot
from engine.strategy import EqualWeightBuyAndHold


class ExperimentTests(unittest.TestCase):
    def test_memory_and_sqlite_roundtrip_and_exact_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.sqlite"
            bt = demo_backtest()
            memory = MemoryStore()
            results = record_run(bt, memory)
            experiment = memory.load(bt.run_id)
            with SQLiteStore(path) as sql:
                sql.save(experiment)
                sql.save(experiment)  # Idempotent; never duplicates rows.
                self.assertEqual(sql.load(bt.run_id), experiment)
                stats = sql.summary(bt.run_id)
                metrics, _ = performance(results["equity"], 100)
                for key in ("final_equity", "max_drawdown"):
                    self.assertAlmostEqual(stats[key], metrics[key])
                self.assertAlmostEqual(stats["commission"], results["fills"].commission.sum())
                self.assertAlmostEqual(stats["slippage_cost"], results["fills"].slippage_cost.sum())
                self.assertEqual(stats["fills"], len(results["fills"]))
                self.assertTrue(any("INDEX" in str(row) for row in sql.query_plan(bt.run_id)))
            with SQLiteStore(path) as reopened:
                for name, frame in replay(reopened, bt.run_id).items():
                    pd.testing.assert_frame_equal(frame, results[name])
            self.assertEqual(canonical(snapshot(bt, replay(memory, bt.run_id))), canonical(experiment))

    def test_hashes_and_events_are_deterministic_and_actual(self):
        first, second = demo_backtest(), demo_backtest()
        first.run()
        second.run()
        self.assertEqual(first.run_id, second.run_id)
        self.assertEqual(first.event_records, second.event_records)
        self.assertEqual([r.sequence for r in first.event_records], list(range(len(first.event_records))))
        fills = [r.event for r in first.event_records if r.event.type == "FILL_BOOKED"]
        self.assertEqual(fills[0].fill.quantity, 8)
        self.assertEqual(fills[0].fill.commission, 1)
        self.assertEqual(first.portfolio.positions, {"A": 0, "B": 0})
        with self.assertRaisesRegex(RuntimeError, "single-use"):
            first.run()

    def test_transaction_rolls_back_on_invalid_ledger(self):
        bt = demo_backtest()
        experiment = snapshot(bt, bt.run())
        experiment["ledgers"]["cash"][0]["cash"] = -100
        with SQLiteStore(":memory:") as sql:
            with self.assertRaises(sqlite3.IntegrityError):
                sql.save(experiment)
            for table in ("runs", "events", "ledgers"):
                self.assertEqual(sql.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0)
            self.assertEqual(sql.connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_integrity_and_identity_collision(self):
        bt = demo_backtest()
        experiment = snapshot(bt, bt.run())
        for store in (MemoryStore(), SQLiteStore(":memory:")):
            try:
                store.save(experiment)
                changed = deepcopy(experiment)
                changed["ledgers"]["cash"][0]["cash"] += 1
                with self.assertRaisesRegex(ValueError, "non-deterministic"):
                    store.save(changed)
                changed = deepcopy(experiment)
                changed["inputs"]["A"][0]["Open"] += 1
                with self.assertRaisesRegex(ValueError, "input hash"):
                    store.save(changed)
            finally:
                if isinstance(store, SQLiteStore):
                    store.close()
        with SQLiteStore(":memory:") as sql:
            sql.save(experiment)
            sql.connection.execute("DELETE FROM events WHERE run_id = ? AND sequence = 0", (bt.run_id,))
            with self.assertRaisesRegex(ValueError, "sequence"):
                sql.load(bt.run_id)

    def test_replay_rejects_unregistered_or_changed_strategy(self):
        bt = demo_backtest()
        store = MemoryStore()
        record_run(bt, store)
        with self.assertRaisesRegex(ValueError, "registered"):
            replay(store, bt.run_id, {})
        with self.assertRaisesRegex(ValueError, "matching"):
            replay(store, bt.run_id, {bt.config["strategy"]: EqualWeightBuyAndHold})

    def test_comparisons_and_cost_sensitivity(self):
        with SQLiteStore(":memory:") as sql:
            ids = []
            for bps in (0, 10):
                bt = Backtest(
                    ["A", "B"],
                    price_data=demo_data(),
                    strategy_cls=DemoStrategy,
                    initial_capital=100,
                    slippage_bps=bps,
                )
                record_run(bt, sql)
                ids.append(bt.run_id)
            with self.assertRaisesRegex(ValueError, "incompatible"):
                sql.compare(ids)
            sensitivity = sql.cost_sensitivity(ids[0])
            self.assertEqual([row["slippage_bps"] for row in sensitivity], [0, 10])
            self.assertGreater(sensitivity[0]["final_equity"], sensitivity[1]["final_equity"])
            hold = Backtest(
                ["A", "B"],
                price_data=demo_data(),
                strategy_cls=EqualWeightBuyAndHold,
                initial_capital=100,
                slippage_bps=0,
            )
            record_run(hold, sql)
            self.assertEqual(len(sql.compare([ids[0], hold.run_id])), 2)
            changed = demo_data()
            changed["A"].iloc[0, 0] += 1
            other = Backtest(
                ["A", "B"], price_data=changed, strategy_cls=DemoStrategy, initial_capital=100, slippage_bps=0
            )
            record_run(other, sql)
            with self.assertRaisesRegex(ValueError, "incompatible"):
                sql.compare([ids[0], other.run_id])
            with self.assertRaises(KeyError):
                sql.load("' OR 1=1 --")

    def test_drawdown_reconciles_on_falling_prices(self):
        data = demo_data()
        data["A"]["Close"] = [10, 8, 6, 4]
        bt = Backtest(["A"], price_data=data, initial_capital=100, strategy_cls=EqualWeightBuyAndHold)
        with SQLiteStore(":memory:") as sql:
            results = record_run(bt, sql)
            expected, _ = performance(results["equity"], 100)
            self.assertLess(expected["max_drawdown"], 0)
            self.assertAlmostEqual(sql.summary(bt.run_id)["max_drawdown"], expected["max_drawdown"])

    def test_common_calendar_replay_retains_exclusions(self):
        data = demo_data()
        data["B"] = data["B"].iloc[1:]
        bt = Backtest(["A", "B"], price_data=data, strategy_cls=DemoStrategy)
        store = MemoryStore()
        record_run(bt, store)
        self.assertEqual(bt.metadata["excluded_dates"]["A"], ["2024-01-01T00:00:00"])
        replay(store, bt.run_id)


class DataPolicyTests(unittest.TestCase):
    def test_missing_internal_or_delisted_tail_strict_fails(self):
        for index in (1, 3):
            data = demo_data()
            data["B"] = data["B"].drop(data["B"].index[index])
            with self.assertRaisesRegex(ValueError, "missing bars or delisting"):
                DataHandler(queue.Queue(), ["A", "B"], price_data=data, calendar_policy="strict")

    def test_nonfinite_duplicate_stale_and_actions_fail(self):
        for value in (float("nan"), float("inf"), 0, -1):
            data = demo_data()
            data["A"] = data["A"].astype(float)
            data["A"].iloc[1, 0] = value
            with self.assertRaises(ValueError):
                DataHandler(queue.Queue(), ["A"], price_data=data)
        for flag in ("Stale", "Delisted", "Dividends", "Stock Splits"):
            data = demo_data()
            data["A"][flag] = [0, 1, 0, 0]
            with self.assertRaisesRegex(ValueError, "unsupported data flag"):
                DataHandler(queue.Queue(), ["A"], price_data=data)
        data = demo_data()
        data["A"] = pd.concat([data["A"], data["A"].iloc[:1]])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            DataHandler(queue.Queue(), ["A"], price_data=data)

    def test_repeated_valid_prices_are_not_inferred_to_be_stale(self):
        data = demo_data()
        data["A"][["Open", "Close"]] = 10
        handler = DataHandler(queue.Queue(), ["A"], price_data=data, calendar_policy="strict")
        self.assertEqual(len(handler.dates), 4)

    def test_invalid_costs_and_capital(self):
        for config in (
            {"initial_capital": 0},
            {"initial_capital": float("inf")},
            {"slippage_bps": -1},
            {"slippage_bps": 10000},
            {"minimum_commission": float("nan")},
        ):
            with self.assertRaises(ValueError):
                Backtest(["A"], price_data=demo_data(), strategy_cls=DemoStrategy, **config)


class AccountingBoundaryTests(unittest.TestCase):
    def test_final_cancellation_releases_reserved_cash(self):
        from test_engine import BuyThenExit

        bt = Backtest(["A"], price_data=demo_data(), strategy_cls=BuyThenExit, strategy_kwargs={"buy_bar": 3})
        result = bt.run()
        self.assertTrue(result["fills"].empty)
        self.assertEqual(result["cash"].iloc[-1].reserved_cash, 0)
        self.assertEqual(bt.event_records[-1].event.reserved_cash, 0)
        self.assertEqual(result["orders"].iloc[-1].status, "cancelled")

    def test_partial_fill_uses_actual_per_share_fee(self):
        from test_engine import BuyThenExit, bars

        bt = Backtest(
            ["A"],
            price_data={"A": bars([1, 10], [1, 10])},
            strategy_cls=BuyThenExit,
            initial_capital=100,
            commission_per_share=1,
            minimum_commission=1,
            slippage_bps=0,
        )
        result = bt.run()
        fill = result["fills"].iloc[0]
        self.assertEqual(fill.quantity, 9)
        self.assertEqual(fill.commission, 9)
        self.assertEqual(result["cash"].iloc[-1].cash, 1)

    def test_sale_fee_cannot_create_negative_cash(self):
        from test_engine import BuyThenExit, bars

        bt = Backtest(
            ["A"],
            price_data={"A": bars([1, 1, 0.001], [1, 1, 0.001])},
            strategy_cls=BuyThenExit,
            strategy_kwargs={"exit_bar": 1, "weight": 1},
            initial_capital=100,
            commission_per_share=0,
            minimum_commission=10,
            slippage_bps=0,
        )
        result = bt.run()
        self.assertGreaterEqual(result["cash"].cash.min(), 0)
        self.assertIn("sale_cannot_cover_commission", result["rejections"].reason.values)
        self.assertGreater(result["positions"].iloc[-1].quantity, 0)

    def test_event_fills_reduce_to_ledger_cash_and_positions(self):
        bt = demo_backtest()
        bt.run()
        cash, positions = 100, {"A": 0, "B": 0}
        for record in bt.event_records:
            event = record.event
            if event.type == "FILL_BOOKED":
                fill = event.fill
                sign = 1 if fill.direction == "BUY" else -1
                positions[fill.symbol] += sign * fill.quantity
                cash -= sign * fill.quantity * fill.fill_price + fill.commission
                self.assertAlmostEqual(event.cash, cash)
                self.assertEqual(event.position, positions[fill.symbol])
                self.assertGreaterEqual(cash, 0)
            elif event.type == "VALUATION":
                marked = sum(positions[symbol] * close for symbol, quantity, close in event.positions)
                self.assertAlmostEqual(event.equity, cash + marked)
