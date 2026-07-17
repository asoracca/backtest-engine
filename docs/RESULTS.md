# Results

`python run.py` downloads SPY daily bars from 2015 through 2024, runs a 20/50-day moving-average rule, compares it with cost-matched buy-and-hold, and writes reproducible outputs to `data/`.

Expected files:

- `equity_curve.png`
- `cost_sensitivity.csv`
- `orders.csv`, `fills.csv`, `trades.csv`
- `positions.csv`, `cash.csv`, `equity.csv`, `rejections.csv`

Numerical results are deliberately generated rather than hard-coded because the upstream adjusted dataset can change. Interpret the study as an engine demonstration. A simple moving-average result can depend heavily on the chosen period, parameters, market regime, and assumed costs; it is not investment advice or a claim of deployable alpha.

The most important version-one result is structural: automated tests verify next-bar execution, event order, cost direction, cash constraints, multi-symbol reservations, exits, common-calendar handling, final marking, and end-of-data cancellation.
