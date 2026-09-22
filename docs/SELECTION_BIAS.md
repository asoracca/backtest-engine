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

- an intentionally biased hindsight winner on a separate synthetic control dataset;
- the Sharpe of the first-half winner in the first half;
- that selected strategy's Sharpe in the untouched second half;
- probability of backtest overfitting estimated with combinatorially symmetric
  cross-validation (CSCV) on development data only.

## CSCV and PBO

Only the first 120 monthly observations (development data) are divided into eight contiguous slices. Every choice of four
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

## Evaluation boundary and negative control

The development selector receives only the first half of each 240-month dataset.
It freezes the winning strategy name and computes CSCV/PBO within that half.
Only then is that one strategy scored on the reserved final 120 months. No
holdout ranking, threshold tuning or PBO calculation feeds back into selection.
Tests change all holdout returns and assert that the selected name, development
score and development PBO remain identical.

The hindsight comparison is a deliberately invalid research procedure applied
to a **separate** 240-month synthetic dataset, using a separate random stream
(`SeedSequence([seed, 1])`). It selects and scores a winner on the same control
observations. This known-zero-alpha negative control demonstrates selection
bias without exposing the legitimate experiment's evaluation data. Its stored
column remains `naive_best_full_sample_sharpe`; it is not the full sample of the
holdout experiment. The main experiment uses `default_rng(seed)`.

Candidate counts, split, seed and repetitions are fixed before the run. This
simulation demonstrates a method; repeatedly inspecting its results does not
create evidence of untouched historical or live trading performance. CSCV is
symmetric development diagnostics, not chronological walk-forward validation.
Normal-approximation intervals describe Monte Carlo means across independent
repetitions, not uncertainty about real-world alpha.

The runner saves raw selected names, split sizes, summary CSVs and a manifest
with configuration, dependency versions, source hash and output checksums.
Use `MPLBACKEND=Agg python run_overfitting_study.py` offline after installation.
See [NumPy's random-stream documentation](https://numpy.org/doc/stable/reference/random/parallel.html)
for the independent seeded control construction.
