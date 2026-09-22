"""Seeded offline benchmark; correctness checks run before any measurements."""

import argparse
import cProfile
import json
import os
import platform
import resource
import statistics
import subprocess
import tempfile
import time
import tracemalloc
from pathlib import Path

import numpy as np
import pandas as pd

from engine.backtest import Backtest
from engine.reproducibility import digest, ledger_records, versions
from engine.storage import SQLiteStore, snapshot
from engine.strategy import MovingAverageCross


def generate_data(symbols, bars, seed):
    if symbols < 1 or bars < 31:
        raise ValueError("benchmark requires at least one symbol and 31 bars")
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2000-01-03", periods=bars)
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, (bars, symbols)), axis=0))
    opens = np.vstack([closes[0], closes[:-1]]) * np.exp(rng.normal(0, 0.002, (bars, symbols)))
    return {
        f"S{i:03}": pd.DataFrame({"Open": opens[:, i], "Close": closes[:, i]}, index=dates)
        for i in range(symbols)
    }


def make_backtest(data, seed):
    return Backtest(
        list(data),
        price_data=data,
        strategy_cls=MovingAverageCross,
        strategy_kwargs={"short": 5, "long": 30},
        initial_capital=1_000_000,
        calendar_policy="strict",
        provenance={"kind": "synthetic", "seed": seed, "source": "benchmark.generate_data v1"},
    )


def check_accounting(result, initial):
    fills = result["fills"]
    if not fills.empty:
        if not (fills.fill_dt > fills.submitted_dt).all():
            raise AssertionError("same-bar fill")
        flows = fills.groupby("fill_dt").cash_flow.sum()
    else:
        flows = pd.Series(dtype=float)
    cash = result["cash"].set_index("dt")
    expected_cash = initial + flows.reindex(cash.index, fill_value=0).cumsum()
    np.testing.assert_allclose(cash.cash, expected_cash, rtol=1e-12, atol=1e-7)
    marked = result["positions"].groupby("dt").market_value.sum()
    np.testing.assert_allclose(cash.equity, cash.cash + marked, rtol=1e-12, atol=1e-7)
    if cash.cash.min() < -1e-8 or result["positions"].quantity.min() < 0:
        raise AssertionError("negative cash or short position")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", type=int, default=20)
    parser.add_argument("--bars", type=int, default=2520)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--profile", type=Path)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    data = generate_data(args.symbols, args.bars, args.seed)

    # Untimed correctness run precedes throughput, allocation and profiling runs.
    baseline = make_backtest(data, args.seed)
    result = baseline.run()
    check_accounting(result, 1_000_000)
    expected = digest(ledger_records(result))
    event_count = len(baseline.event_records)
    ledger_rows = sum(len(frame) for frame in result.values())
    del baseline, result
    seconds = []
    for _ in range(args.repeats):
        started = time.perf_counter()
        bt = make_backtest(data, args.seed)
        result = bt.run()
        seconds.append(time.perf_counter() - started)
        if digest(ledger_records(result)) != expected:
            raise AssertionError("benchmark replay mismatch")
        del bt, result

    # Separate allocation measurement so tracemalloc does not distort throughput.
    tracemalloc.start()
    bt = make_backtest(data, args.seed)
    result = bt.run()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    started = time.perf_counter()
    experiment = snapshot(bt, result)
    snapshot_seconds = time.perf_counter() - started
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "benchmark.sqlite"
        with SQLiteStore(path) as store:
            started = time.perf_counter()
            store.save(experiment)
            save_seconds = time.perf_counter() - started
            started = time.perf_counter()
            store.load(bt.run_id)
            load_seconds = time.perf_counter() - started
            plan = store.query_plan(bt.run_id)
        db_bytes = path.stat().st_size
    if args.profile:
        args.profile.parent.mkdir(parents=True, exist_ok=True)
        profiler = cProfile.Profile()
        profiler.enable()
        profiled = make_backtest(data, args.seed)
        profiled.run()
        profiler.disable()
        profiler.dump_stats(args.profile)
    cpu = platform.processor() or platform.machine()
    if platform.system() == "Darwin":
        try:
            cpu = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"], text=True, stderr=subprocess.DEVNULL
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            cpu += " (CPU model unavailable in sandbox)"
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_bytes = rss if platform.system() == "Darwin" else rss * 1024
    report = {
        "kind": "synthetic",
        "seed": args.seed,
        "symbols": args.symbols,
        "bars_per_symbol": args.bars,
        "input_rows": args.symbols * args.bars,
        "consumed_columns": ["Open", "Close"],
        "events": event_count,
        "ledger_rows": ledger_rows,
        "repeats": args.repeats,
        "seconds": seconds,
        "median_seconds": statistics.median(seconds),
        "events_per_second": event_count / statistics.median(seconds),
        "tracemalloc_peak_bytes": peak,
        "process_peak_rss_bytes": rss_bytes,
        "snapshot_seconds": snapshot_seconds,
        "sqlite_save_seconds": save_seconds,
        "sqlite_load_seconds": load_seconds,
        "database_bytes": db_bytes,
        "ledger_hash": expected,
        "versions": versions(),
        "hardware": {"os": platform.platform(), "cpu": cpu, "logical_cpus": os.cpu_count()},
        "query_plan": plan,
        "measurement_scope": "Throughput includes Backtest construction, input hashing and run; excludes "
        "data generation, validation, persistence, profiling and allocation tracing. Allocation peak "
        "is a separate constructor/run; RSS is process lifetime and includes other passes.",
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
