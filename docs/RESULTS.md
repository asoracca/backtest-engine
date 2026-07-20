# Results

`python run.py` downloads SPY daily bars from 2015 through 2024, runs a 20/50-day moving-average rule, compares it with cost-matched buy-and-hold, and writes reproducible outputs to `data/`.

Expected files:

- `equity_curve.png`
- `cost_sensitivity.csv`
- `orders.csv`, `fills.csv`, `trades.csv`
- `positions.csv`, `cash.csv`, `equity.csv`, `rejections.csv`

Numerical results are deliberately generated rather than hard-coded because the upstream adjusted dataset can change. Interpret the study as an engine demonstration. A simple moving-average result can depend heavily on the chosen period, parameters, market regime, and assumed costs; it is not investment advice or a claim of deployable alpha.

The most important version-one result is structural: automated tests verify next-bar execution, event order, cost direction, cash constraints, multi-symbol reservations, exits, common-calendar handling, final marking, and end-of-data cancellation.

## Cross-sectional momentum snapshot

The following is the observed July 20, 2026 run of
`python run_cross_sectional.py`. The requested data interval ends January 1,
2025. Because Yahoo Finance can revise adjusted history, generated CSV files
remain the source of truth for a fresh run.

| Strategy | Cost | Annual return | Sharpe | Max drawdown | Final equity | Fills |
|---|---:|---:|---:|---:|---:|---:|
| Momentum | 0 bps | 11.28% | 0.750 | -31.86% | $495,681 | 189 |
| Equal weight | 0 bps | 11.89% | 0.792 | -33.52% | $537,320 | 9 |
| Momentum | 5 bps | 11.08% | 0.738 | -31.90% | $482,234 | 189 |
| Equal weight | 5 bps | 11.88% | 0.792 | -33.53% | $537,275 | 9 |
| Momentum | 10 bps | 10.88% | 0.726 | -31.94% | $469,139 | 189 |
| Equal weight | 10 bps | 11.88% | 0.792 | -33.53% | $537,230 | 9 |
| Momentum | 25 bps | 10.26% | 0.690 | -32.07% | $431,687 | 189 |
| Equal weight | 25 bps | 11.88% | 0.792 | -33.55% | $537,095 | 9 |

### Interpretation

The fixed 12-1 sector momentum rule did not improve return or Sharpe relative
to equal-weight buy-and-hold in this sample. It reduced maximum drawdown by
roughly 1.6 percentage points, but required far more trading. As assumed costs
rose, that turnover widened the performance deficit. This is a useful negative
result: the tested rule did not demonstrate an implementable advantage over the
simpler alternative.

The experiment now also writes annualized turnover plus
`active_performance.csv`, containing annualized active mean return, tracking
error, information ratio, and ending-wealth difference at each cost level.
Those statistics measure the strategy against equal weight; they do not turn
this full-period comparison into an untouched test.

Do not tune the lookback, skip, selection fraction, or sample dates in response
to this table and then describe the same interval as out of sample. Any future
variant should be declared first and evaluated on genuinely new data or through
a separately designed robustness study.
