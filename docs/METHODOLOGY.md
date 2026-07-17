# Methodology

## Timing convention

A strategy may use information through `close[t]`. Its order becomes eligible at `open[t+1]`. Portfolio equity is marked at `close[t+1]`. The test suite asserts the signal timestamp is earlier than the fill timestamp.

## Costs

Market orders receive adverse slippage: buys pay above the open and sells receive below it. Commissions are the greater of a minimum charge and a per-share charge. `run.py` repeats the experiment at 0, 1, 5, and 10 basis points.

## Comparison

The example compares the one included moving-average rule with buy-and-hold. Both start with identical capital and use the same entry commission/slippage assumptions. This is a baseline, not evidence of a profitable strategy.

## Research discipline

For strategy research beyond the example, split data chronologically into training, validation, and untouched test periods. Choose rules only with training/validation, report the untouched result once, and examine sensitivity across parameters, costs, and market regimes. Walk-forward evaluation should retrain only on information available at each historical date.
