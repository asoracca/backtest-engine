# Replayable experiments

## Architecture and public API

`Backtest(...).run()` still returns the original seven pandas ledgers. Existing
strategy classes and injected DataFrames continue to work. `event_records`,
`run_id`, `config`, `input_snapshot` and `metadata` are additional attributes.
Instances are single-use; create a fresh instance for each run.

The queue retains MarketEvent, SignalEvent, OrderEvent and FillEvent. The audit
stream uses immutable records for signals, accepted orders, rejected quantities,
booked fills and valuations. Accepted records contain the order and total cash
reservation; broker fill proposals become booked fill events only after actual
cash/position checks. This distinction prevents replay from booking a rejected
or reduced quantity as if it filled. Sequence numbers start at zero and order
all records within a run; timestamps alone cannot order events on the same day.
A final cancellation releases reservations and emits a terminal valuation at the
last timestamp, without adding another return observation.

The portfolio remains the sole accounting implementation. The store receives a
completed experiment through `ExperimentStore.save` and retrieves it through
`load`; neither implementation computes trades. MemoryStore provides isolated
copies for tests. SQLiteStore implements the same boundary with explicit SQL.
There is no service, ORM, broker integration or production database connection.

## Identity and reproducibility

SHA-256 run IDs address canonical JSON containing the configuration, normalized
input hash, engine source hash, strategy source hash, dependency versions, timing,
provenance and excluded dates. Ordered symbols are part of configuration because
competing orders consume cash in that order. Configuration and data also have
separate hashes. Identical inputs in the identical environment reproduce the
same ID. Different costs, versions, source or provenance produce different IDs;
an ID is a reproducible experiment identity, not a timestamped execution attempt.

The database retains every normalized Open/Close observation before calendar
intersection, plus the excluded-date list and provenance. Replay uses these
stored observations, never a fresh download or the current fixture file. High,
Low and unused input columns are not part of the consumed dataset. Preserve an
external raw-data artifact if those columns are needed for separate research.

Use `provenance={"kind": "synthetic", "source": "...", "seed": 17}` for synthetic
inputs and identify source, adjustment conventions and dates for historical
inputs. An unspecified injected frame is labeled `injected`, not claimed to be
historical. The downloader uses adjusted historical prices. No live feed is
implemented. Callers are responsible for truthful source labels.

`replay` requires matching engine source, strategy source and Python/pandas/NumPy/
SQLite versions, then checks every event and ledger against the saved manifest.
The CLI permits only named built-in strategies; the Python API can accept an
explicit registry for custom strategies. Database text is never imported or
executed. Interactive classes without inspectable source may run but cannot be
exactly replayed. Configuration and provenance must be JSON-serializable.
Custom strategy determinism remains the caller's responsibility: source hashing
does not capture arbitrary external files, global state or helper dependencies.

## Storage and queries

`engine/sql/001_initial.sql` creates runs, events and ledgers, keyed by run ID.
Foreign keys, event-kind checks, JSON validity, nonnegative accounting fields,
unique sequence/row keys and projection-to-JSON checks constrain storage. SQL
report columns are checked against their complete JSON records to avoid divergent
copies. Indexes cover run comparison groups, slippage groups, event kinds and
ledger timelines. `PRAGMA user_version` tracks the migration. Initialization and
whole-run saves use explicit transactions; failure rolls back the entire run.
Newer unknown schema versions fail. A repeated identical save is idempotent;
different output for the same ID fails. There is no partial-run resume support.

`summary.sql` computes drawdown with a running MAX window and sums actual fill
commissions and slippage. Tests reconcile these with `engine.metrics.performance`
and pandas fill totals, including a declining equity curve. Queries bind run IDs
and comparison hashes as parameters. `plan` runs SQLite's real EXPLAIN QUERY PLAN;
see [measured performance](PERFORMANCE.md) for an observed plan.

```bash
python run_experiments.py --db experiments.sqlite demo
python run_experiments.py --db experiments.sqlite replay RUN_ID
python run_experiments.py --db experiments.sqlite compare RUN_ID_A RUN_ID_B
python run_experiments.py --db experiments.sqlite costs RUN_ID
python run_experiments.py --db experiments.sqlite plan RUN_ID
```

Copy IDs printed by `demo`. It stores and verifies replay for 0, 1, 5 and 10 bps.
`compare` requires identical inputs, timing, initial capital, costs, source labels,
calendar policy and engine/dependency versions; only strategy/configuration may
vary. `costs` holds strategy/configuration constant and permits only slippage to
vary. It reports separate reruns, not a post-hoc fee subtraction from one ledger.
Comparisons are accounting reports, not selection or untouched evaluation claims.

## Data policy and limits

- `calendar_policy="common"` preserves the original intersection policy. A next
  bar means the next date shared by every symbol, potentially several days later.
  Excluded dates are retained in metadata. This can truncate a delisted symbol's
  tail for the whole portfolio and is unsuitable for delisting research.
- `calendar_policy="strict"` requires identical dates and is used by the stored
  demo and benchmark. Missing internal bars or unequal tails fail before trading.
  Neither policy forward-fills or invents an open. There is no exchange calendar:
  a date missing from every symbol cannot be detected automatically. Daily
  timestamps are session labels; timezone information is stripped for legacy
  compatibility. Callers must align session labels across markets before injection.
- Duplicate/invalid timestamps, nonfinite/missing prices and nonpositive prices
  fail. Explicit nonzero `Stale`, `Delisted`, `Dividends` or `Stock Splits` columns
  fail as unsupported. Repeated prices alone cannot establish staleness. Supply
  quality flags or validate freshness upstream. Unflagged corporate actions
  cannot be inferred reliably from price changes. The engine does not process
  action cash flows, share adjustments or delisting recoveries.
- A last-bar order is cancelled; positions already held remain marked at the
  last observed close. There is no invented terminal liquidation.
- Buy affordability uses commission on actual filled quantity. A reduced fill
  still pays the configured minimum. A sale whose proceeds plus cash cannot
  cover commission is rejected and the position remains held. These fix edge
  cases where the earlier implementation prorated away minimum fees or allowed
  negative cash on a collapsed-price sale.
- Accounting uses floating-point currency and integer shares; tests use explicit
  tolerances. No shorting, financing, borrow, margin, partial liquidity or taxes.
- Completed runs, events, snapshots and ledgers remain in memory. This is a daily
  research engine, not an unbounded streaming storage system. Database manifests
  detect accidental corruption; they are not signatures against malicious edits.

## Validation and references

The original offline tests remain in CI, alongside the golden fixture, event
reduction, replay, constraints, rollback, missing/stale-bar, fee and comparison
tests. Benchmarking follows these correctness tests and has no machine-specific
speed threshold. Installation requires dependency downloads once; all demos,
replay, tests and benchmarks then work without network access or credentials.

Implementation references: [Python 3.12 sqlite3 transactions and parameters](https://docs.python.org/3.12/library/sqlite3.html),
[SQLite window functions](https://www.sqlite.org/windowfunctions.html),
[pandas 3.0 DataFrame records](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_dict.html),
and [NumPy Generator](https://numpy.org/doc/stable/reference/random/generator.html).
