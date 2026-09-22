# Backtest Engine

A compact event-driven backtesting engine built from scratch in Python. Its main research rule is explicit: **signals are generated at `close[t]`, filled at `open[t+1]`, and marked at `close[t+1]`**. That prevents the same-close look-ahead error common in first backtests.

## What version 1 includes

- Injected pandas DataFrames for deterministic, network-free tests
- Target-weight sizing, cash reservation, and order rejection
- Directional slippage and per-share/minimum commissions
- Order, fill, trade, position, cash, rejection, and equity ledgers
- A cost-matched buy-and-hold benchmark
- Transaction-cost sensitivity at 0, 1, 5, and 10 bps
- Tests for timing, cash, multiple symbols, costs, exits, missing bars, and final marking

## Event flow

```text
bar opens -> pending orders fill -> bar closes -> strategy signals
     ^                                                |
     |                                                v
next bar <--- order waits in broker <--- portfolio target weights
```

## Install and test

```bash
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m unittest discover -s tests -v
```

## Offline accounting and stored replay

After installation, run from this repository's root:

```bash
python run_offline.py
python run_experiments.py --db experiments.sqlite demo
```

The first command prints a versioned synthetic OHLC fixture's expected ledgers
and timeline. The second stores four cost scenarios in SQLite and verifies exact
replay from stored configuration and prices. No credentials or network are used.

```text
Jan 1 close: signal A at 10.00; B rejected for insufficient cash
Jan 2 open:  buy 8 A at 12.012; commission 1.00; cash 2.904
Jan 2 close: 8 A marked at 13.00; equity 106.904
Jan 3 open:  exit A; final cash and equity 113.792
```

Today's close signal cannot receive today's price. The invented example is an
accounting demonstration, not a historical trading result. See the
[fixture and regeneration command](fixtures/synthetic/README.md),
[storage, architecture and data policies](docs/EXPERIMENTS.md), and
[measured benchmark](docs/PERFORMANCE.md).

`compare RUN_ID_A RUN_ID_B`, `costs RUN_ID`, `replay RUN_ID` and `plan RUN_ID`
are subcommands of `run_experiments.py`. Comparison rejects mismatched data,
timing or costs; the separate cost report varies only slippage. The original
`Backtest.run()` ledger API is preserved. Strict calendar validation is available;
the default retains the documented common-calendar policy.

## Historical examples

Run the SPY example (this step downloads market data):

```bash
python run.py
```

Run the cross-sectional sector-ETF example:

```bash
python run_cross_sectional.py
```

That experiment ranks nine US sector ETFs using a fixed 12-1 momentum signal,
holds the top third, and rebalances approximately every 21 trading days. It
compares the strategy with an equal-weight buy-and-hold basket through the same
event engine and cost model. Results at 0, 5, 10, and 25 bps are written to
`data/cross_sectional/`.

The implementation is intentionally long-only. Adding a negative target to a
long-only portfolio would not constitute a valid short simulation: borrow,
margin, short proceeds, financing, and forced-liquidation rules must be modeled
explicitly first.

Outputs are saved under `data/`, including every ledger, the cost-sensitivity table, and an equity chart.

## Strategy-selection bias research

Version 1.1 adds a controlled multiple-testing experiment and an implementation
of combinatorially symmetric cross-validation. It demonstrates how searching
more zero-alpha strategy variants can manufacture an impressive in-sample
winner whose holdout performance does not persist.

```bash
python run_overfitting_study.py
```

See [the selection-bias methodology](docs/SELECTION_BIAS.md) and
[recorded results](docs/SELECTION_BIAS_RESULTS.md). This diagnostic requires the
complete strategy/configuration set; applying it only to surviving backtests
would hide the selection process it is intended to measure.

## Minimal network-free use

```python
import pandas as pd
from engine.backtest import Backtest
from engine.strategy import MovingAverageCross

bars = pd.DataFrame(
    {"Open": [100, 101, 102], "Close": [101, 102, 103]},
    index=pd.date_range("2024-01-01", periods=3),
)
results = Backtest(
    ["TEST"],
    price_data={"TEST": bars},
    strategy_cls=MovingAverageCross,
    strategy_kwargs={"short": 1, "long": 2},
).run()
print(results["fills"])
```

## Scope and limitations

This is an educational daily-bar simulator, not a production trading system. It does not model partial market liquidity, limit orders, corporate-action edge cases, borrow, taxes, or intraday queue position. See [methodology](docs/METHODOLOGY.md), [design](docs/DESIGN.md), and [results](docs/RESULTS.md).
