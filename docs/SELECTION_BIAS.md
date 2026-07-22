# Strategy-selection bias study

## Research question

If every tested strategy has zero true alpha, how does trying more alternatives
change the best reported Sharpe ratio and its out-of-sample performance?

## Controlled experiment

The runner generates correlated monthly returns under a global zero-alpha null.
It repeats the experiment for 5, 20, and 100 candidate strategies. Every
candidate has the same volatility and no expected excess return; a common shock
creates correlation between strategies.

For each simulated dataset the study reports:

- the best full-sample Sharpe selected with hindsight;
- the Sharpe of the first-half winner in the first half;
- that selected strategy's Sharpe in the untouched second half;
- probability of backtest overfitting estimated with combinatorially symmetric
  cross-validation (CSCV).

## CSCV and PBO

The time series is divided into eight contiguous slices. Every choice of four
slices forms an in-sample set, and the complement forms its out-of-sample set,
creating 70 symmetric splits. For each split, the highest in-sample Sharpe is
selected and ranked against all configurations out of sample. PBO is the fraction
of selected winners whose out-of-sample relative rank is at or below the median.

This follows the framework in Bailey et al., *The Probability of Backtest
Overfitting*: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253

## What the experiment can establish

Because the data-generating process sets every alpha to zero, any impressive
winner is known to be selection noise. The experiment isolates the multiple-
testing mechanism and tests whether holdout and CSCV diagnostics reveal it.

It does not estimate the PBO of every repository strategy. Applying CSCV to real
research requires recording the complete set of configurations attempted, not
only the configurations retained after looking at results.
