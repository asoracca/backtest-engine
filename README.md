# backtest-engine

An **event-driven backtesting engine, built from scratch** in Python — no
backtesting libraries doing the work. It mirrors the decoupled architecture real
trading systems use: components communicate only through events on a queue.

## Architecture

    DataHandler --MarketEvent--> Strategy --SignalEvent--> Portfolio
        ^                                                      |
        |                                                  OrderEvent
        |                                                      v
        +------------- FillEvent <--- ExecutionHandler <-------+

Each component is independent and swappable:

| Module | Responsibility |
|--------|----------------|
| `engine/data.py` | Streams historical bars, emits a `MarketEvent` per day |
| `engine/strategy.py` | Turns market data into `SignalEvent`s (example: MA crossover) |
| `engine/portfolio.py` | Tracks cash/positions/equity; sizes orders; books fills |
| `engine/execution.py` | Simulated broker with slippage + commission |
| `engine/backtest.py` | The event loop that drives everything |
| `engine/metrics.py` | Sharpe, drawdown, returns from the equity curve |

## Run

    pip install -r requirements.txt
    python run.py            # runs a 20/50 MA crossover on AAPL, saves the equity curve
    python tests/test_portfolio.py   # unit tests for portfolio accounting

## Extending it

Write a new strategy by subclassing `Strategy` and implementing
`calculate_signals(event)` — the rest of the engine is unchanged. That decoupling
is the whole point: the same engine can drive any strategy, and each component can
be tested in isolation.
