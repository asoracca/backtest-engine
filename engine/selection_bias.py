"""Combinatorially symmetric cross-validation for strategy-selection bias."""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PBOResult:
    probability_of_backtest_overfitting: float
    median_logit_rank: float
    mean_selected_in_sample_sharpe: float
    mean_selected_out_of_sample_sharpe: float
    splits: int
    split_results: pd.DataFrame


def annualized_sharpe(returns: np.ndarray, periods_per_year: int = 12) -> np.ndarray:
    """Calculate column-wise annualized Sharpe ratios with a zero cash rate."""
    values = np.asarray(returns, dtype=float)
    if values.ndim == 1:
        values = values[:, None]
    if values.shape[0] < 2:
        raise ValueError("at least two return observations are required")
    means = values.mean(axis=0)
    volatility = values.std(axis=0, ddof=1)
    return np.divide(
        means * math.sqrt(periods_per_year),
        volatility,
        out=np.zeros_like(means),
        where=volatility > 0,
    )


def _relative_rank(value: float, population: np.ndarray) -> float:
    """Return a tie-aware rank strictly inside zero and one."""
    less = float(np.sum(population < value))
    equal = float(np.sum(population == value))
    return (less + 0.5 * equal) / len(population)


def combinatorially_symmetric_cv(
    returns: pd.DataFrame,
    n_slices: int = 8,
    periods_per_year: int = 12,
) -> PBOResult:
    """Estimate the probability that the in-sample winner ranks below median OOS.

    Time is divided into contiguous slices. Every combination of half the slices
    forms an in-sample set; the complement is its out-of-sample set. For each
    split, the best in-sample strategy is ranked among all strategies out of
    sample. PBO is the fraction of selected strategies whose OOS rank is at or
    below the median.
    """
    if not isinstance(returns, pd.DataFrame) or returns.empty:
        raise ValueError("returns must be a non-empty DataFrame")
    if returns.shape[1] < 2:
        raise ValueError("at least two strategy configurations are required")
    if returns.isna().any().any() or not np.isfinite(returns.to_numpy()).all():
        raise ValueError("returns must contain only finite values")
    if n_slices < 4 or n_slices % 2:
        raise ValueError("n_slices must be an even integer of at least four")
    if len(returns) < n_slices * 2:
        raise ValueError("not enough observations for the requested slices")

    blocks = tuple(np.array_split(np.arange(len(returns)), n_slices))
    values = returns.to_numpy(dtype=float)
    rows: list[dict[str, float | int | str]] = []
    half = n_slices // 2

    for split_number, selected_blocks in enumerate(combinations(range(n_slices), half)):
        selected = set(selected_blocks)
        in_indices = np.concatenate([blocks[index] for index in selected_blocks])
        out_indices = np.concatenate([blocks[index] for index in range(n_slices) if index not in selected])
        in_scores = annualized_sharpe(values[in_indices], periods_per_year)
        out_scores = annualized_sharpe(values[out_indices], periods_per_year)
        winner_index = int(np.argmax(in_scores))
        relative_rank = _relative_rank(out_scores[winner_index], out_scores)
        clipped_rank = min(1.0 - 1e-12, max(1e-12, relative_rank))
        logit_rank = math.log(clipped_rank / (1.0 - clipped_rank))
        rows.append(
            {
                "split": split_number,
                "selected_strategy": str(returns.columns[winner_index]),
                "in_sample_sharpe": float(in_scores[winner_index]),
                "out_of_sample_sharpe": float(out_scores[winner_index]),
                "out_of_sample_relative_rank": relative_rank,
                "logit_rank": logit_rank,
                "overfit": int(relative_rank <= 0.5),
            }
        )

    frame = pd.DataFrame(rows)
    return PBOResult(
        probability_of_backtest_overfitting=float(frame["overfit"].mean()),
        median_logit_rank=float(frame["logit_rank"].median()),
        mean_selected_in_sample_sharpe=float(frame["in_sample_sharpe"].mean()),
        mean_selected_out_of_sample_sharpe=float(frame["out_of_sample_sharpe"].mean()),
        splits=len(frame),
        split_results=frame,
    )


def simulate_null_strategies(
    observations: int,
    strategies: int,
    rng: np.random.Generator,
    common_correlation: float = 0.25,
    monthly_volatility: float = 0.04,
) -> pd.DataFrame:
    """Generate correlated zero-alpha strategy returns under a global null."""
    if observations < 16 or strategies < 2:
        raise ValueError("simulation requires at least 16 observations and 2 strategies")
    if not 0 <= common_correlation < 1 or monthly_volatility <= 0:
        raise ValueError("invalid correlation or volatility")
    common = rng.normal(size=(observations, 1))
    independent = rng.normal(size=(observations, strategies))
    standardized = math.sqrt(common_correlation) * common + math.sqrt(1.0 - common_correlation) * independent
    return pd.DataFrame(
        monthly_volatility * standardized,
        columns=[f"strategy_{index:03d}" for index in range(strategies)],
    )


@dataclass(frozen=True)
class DevelopmentSelection:
    selected_strategy: str
    selected_sharpe: float
    pbo: PBOResult


def select_on_development(development: pd.DataFrame, n_slices: int = 8) -> DevelopmentSelection:
    """Freeze the winner and diagnostic using development observations only."""
    if development.columns.has_duplicates:
        raise ValueError("strategy names must be unique")
    pbo = combinatorially_symmetric_cv(development, n_slices=n_slices)
    scores = annualized_sharpe(development.to_numpy())
    winner = int(np.argmax(scores))
    return DevelopmentSelection(str(development.columns[winner]), float(scores[winner]), pbo)


def run_selection_bias_experiment(
    candidate_counts: tuple[int, ...] = (5, 20, 100),
    repetitions: int = 40,
    observations: int = 240,
    n_slices: int = 8,
    seed: int = 17,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Measure how trying more zero-alpha strategies manufactures winners."""
    if repetitions < 2:
        raise ValueError("at least two repetitions are required")
    if not candidate_counts or any(count < 2 for count in candidate_counts):
        raise ValueError("candidate counts must contain values of at least two")
    rng = np.random.default_rng(seed)
    # The deliberately leaky negative control never shares evaluation observations.
    control_rng = np.random.default_rng(np.random.SeedSequence([seed, 1]))
    rows: list[dict[str, float | int | str]] = []

    for candidate_count in candidate_counts:
        for repetition in range(repetitions):
            returns = simulate_null_strategies(observations, candidate_count, rng)
            midpoint = observations // 2
            selection = select_on_development(returns.iloc[:midpoint], n_slices=n_slices)
            # Only the frozen winner is evaluated on the reserved second half.
            holdout_score = annualized_sharpe(
                returns.loc[returns.index[midpoint:], selection.selected_strategy].to_numpy()
            )[0]
            negative_control = simulate_null_strategies(observations, candidate_count, control_rng)
            full_scores = annualized_sharpe(negative_control.to_numpy())
            winner = int(np.argmax(full_scores))
            rows.append(
                {
                    "candidate_count": candidate_count,
                    "repetition": repetition,
                    "naive_best_full_sample_sharpe": float(full_scores[winner]),
                    "selected_strategy": selection.selected_strategy,
                    "development_observations": midpoint,
                    "evaluation_observations": observations - midpoint,
                    "first_half_selected_sharpe": selection.selected_sharpe,
                    "selected_holdout_sharpe": float(holdout_score),
                    "pbo": selection.pbo.probability_of_backtest_overfitting,
                }
            )

    raw = pd.DataFrame(rows)
    summaries: list[dict[str, float | int]] = []
    for candidate_count in candidate_counts:
        selected = raw[raw["candidate_count"] == candidate_count]
        row: dict[str, float | int] = {
            "candidate_count": candidate_count,
            "repetitions": len(selected),
        }
        for output_name, column in (
            ("naive_best_sharpe", "naive_best_full_sample_sharpe"),
            ("first_half_selected_sharpe", "first_half_selected_sharpe"),
            ("selected_holdout_sharpe", "selected_holdout_sharpe"),
            ("pbo", "pbo"),
        ):
            mean, low, high = _sample_mean_interval(selected[column].to_numpy())
            row[f"mean_{output_name}"] = mean
            row[f"{output_name}_ci95_low"] = low
            row[f"{output_name}_ci95_high"] = high
        summaries.append(row)
    summary = pd.DataFrame(summaries)
    return raw, summary


def _sample_mean_interval(values: np.ndarray) -> tuple[float, float, float]:
    if len(values) < 2:
        raise ValueError("at least two values are required")
    mean = float(np.mean(values))
    margin = 1.96 * float(np.std(values, ddof=1)) / math.sqrt(len(values))
    return mean, mean - margin, mean + margin
