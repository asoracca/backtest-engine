# Seeded performance baseline

This is an observed local measurement, not a speed guarantee. No performance
optimization was applied. Correctness checks and deterministic result-hash
comparison precede profiling. CI runs a small correctness/performance smoke
workload without a hardware-specific speed threshold.

## Reproduce

After installing the project dependencies, from the repository root:

```bash
python -m unittest discover -s tests -v
python benchmark.py --symbols 20 --bars 2520 --seed 17 --repeats 3 \
  --profile /tmp/backtest-profile.pstats > /tmp/backtest-benchmark.json
python -c 'import pstats; pstats.Stats("/tmp/backtest-profile.pstats").strip_dirs().sort_stats("cumulative").print_stats(12)'
```

The seeded workload is synthetic lognormal prices with overnight gaps, 20
symbols, 2,520 business-date bars per symbol, 50,400 input rows and two consumed
columns (Open/Close). It uses the existing 5/30 moving-average strategy, one
million starting capital, default 1 bp slippage and default commission. It is
not a model calibrated to historical markets. The date grid is not an exchange
calendar. Runs retain complete event and ledger histories.

## Observed run

Recorded September 22, 2026 UTC on macOS 26.5.1, Apple M5, 10 logical CPUs and
16 GiB RAM. Hardware was independently read with
`sysctl -n machdep.cpu.brand_string hw.memsize hw.logicalcpu`; the benchmark's
sandbox could report architecture and CPU count but not the CPU model.
Python 3.12.14, pandas 3.0.6, NumPy 2.5.3 and SQLite 3.53.1 were used.
Full installed package versions are in [environment.txt](measurements/environment.txt).
The accounting source at measurement was local commit `8923562`; the benchmark
script accompanies this report.

| Measurement | Observed value |
|---|---:|
| Audit events | 9,838 |
| Total rows across all seven ledgers | 62,756 |
| Three constructor/run timings | 4.791, 4.820, 6.405 seconds |
| Median constructor/run time | 4.820 seconds |
| Audit-event throughput | 2,041 events/second |
| Separate traced allocation peak | 50,021,681 bytes (47.7 MiB) |
| Whole-process peak RSS | 382,484,480 bytes (364.8 MiB) |
| Canonical snapshot conversion | 0.870 seconds |
| Atomic SQLite save | 1.343 seconds |
| Validated SQLite load | 0.596 seconds |
| SQLite file size | 39,616,512 bytes (37.8 MiB) |

[Raw measurements and query plan](measurements/benchmark.json) include the exact
ledger hash. Throughput includes construction, normalization, input hashing,
strategy execution and ledger construction. It excludes data generation,
validation, persistence, profiling and allocation tracing. Tracemalloc runs
separately and excludes the pre-existing input frames; it may not capture all
native allocations. RSS is the process lifetime maximum, including validation,
serialization, persistence and profiling passes. Disk timings are a single local
sample and are sensitive to caches and filesystem behavior. Other machine load,
thermal state and scheduler effects were not controlled. These results do not
establish linear scaling or intraday capacity.

## Profile and SQL plan

The separate [cProfile pass](measurements/profile.txt) took 16.836 seconds under
instrumentation. It reported 202,419 `get_latest_close` calls taking 8.838 seconds
cumulatively, with pandas positional indexing prominent. Instrumented time is
not the throughput timing, and cumulative rows overlap. Caching price arrays
could be investigated later with the same correctness suite and input hash;
this baseline does not claim that optimization has been performed.

The observed summary query plan searches the composite primary-key index:

```text
SEARCH ledgers USING INDEX sqlite_autoindex_ledgers_1 (run_id=? AND ledger=?)
MATERIALIZE curve
USE TEMP B-TREE FOR ORDER BY
```

The index selects one run and ledger, then orders its rows for the running peak
window. SQLite materializes that curve because both final equity and drawdown
consume it; the final descending lookup uses a temporary sort. This is expected
for this small report and is not described as an index-only query. Inspect a
stored experiment directly using `python run_experiments.py plan RUN_ID`.
