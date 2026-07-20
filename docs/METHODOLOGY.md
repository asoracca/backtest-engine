# Methodology

## Timing convention

A strategy may use information through `close[t]`. Its order becomes eligible at `open[t+1]`. Portfolio equity is marked at `close[t+1]`. The test suite asserts the signal timestamp is earlier than the fill timestamp.

## Costs

Market orders receive adverse slippage: buys pay above the open and sells receive below it. Commissions are the greater of a minimum charge and a per-share charge. `run.py` repeats the experiment at 0, 1, 5, and 10 basis points.

## Comparison

The example compares the one included moving-average rule with buy-and-hold. Both start with identical capital and use the same entry commission/slippage assumptions. This is a baseline, not evidence of a profitable strategy.

## Cross-sectional momentum example

`run_cross_sectional.py` uses nine sector ETFs to demonstrate multi-asset target
weights without individual-stock survivorship selection. At each scheduled
rebalance close, the strategy ranks trailing returns from approximately
`t-252` through `t-21`, assigns 90% gross capital equally to the top third, and
fills changes at the following open. Reductions are submitted before increases;
conservative expected sale proceeds may reserve replacement buys, while actual
next-open affordability still determines final fills.

The equal-weight comparison runs through the same portfolio, execution, fee,
and marking components. The cost table varies adverse slippage but holds the
commission schedule fixed. This is an integration example rather than a new
independent momentum discovery test; repeated inspection of the same interval
must not be described as untouched evaluation.

## Research discipline

For strategy research beyond the example, split data chronologically into training, validation, and untouched test periods. Choose rules only with training/validation, report the untouched result once, and examine sensitivity across parameters, costs, and market regimes. Walk-forward evaluation should retrain only on information available at each historical date.
