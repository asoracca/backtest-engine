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

Run the SPY example (this step downloads market data):

```bash
python run.py
```

Outputs are saved under `data/`, including every ledger, the cost-sensitivity table, and an equity chart.

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
