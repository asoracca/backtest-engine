"""Demonstrate strategy-selection bias under a controlled zero-alpha null."""

from pathlib import Path

import matplotlib.pyplot as plt

from engine.selection_bias import run_selection_bias_experiment


def main():
    output = Path("data/selection_bias")
    output.mkdir(parents=True, exist_ok=True)
    raw, summary = run_selection_bias_experiment()
    raw.to_csv(output / "simulation_runs.csv", index=False)
    summary.to_csv(output / "summary.csv", index=False)

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    axes[0].errorbar(
        summary["candidate_count"],
        summary["mean_naive_best_sharpe"],
        yerr=[
            summary["mean_naive_best_sharpe"] - summary["naive_best_sharpe_ci95_low"],
            summary["naive_best_sharpe_ci95_high"] - summary["mean_naive_best_sharpe"],
        ],
        marker="o",
        capsize=4,
        label="Best full-sample Sharpe",
    )
    axes[0].errorbar(
        summary["candidate_count"],
        summary["mean_selected_holdout_sharpe"],
        yerr=[
            summary["mean_selected_holdout_sharpe"] - summary["selected_holdout_sharpe_ci95_low"],
            summary["selected_holdout_sharpe_ci95_high"] - summary["mean_selected_holdout_sharpe"],
        ],
        marker="s",
        capsize=4,
        label="Selected strategy holdout Sharpe",
    )
    axes[0].axhline(0, color="black", linewidth=0.8)
    axes[0].set_xscale("log")
    axes[0].set_xlabel("Number of strategies tried")
    axes[0].set_ylabel("Mean annualized Sharpe")
    axes[0].set_title("Selection manufactures an in-sample winner")
    axes[0].legend()

    axes[1].errorbar(
        summary["candidate_count"],
        summary["mean_pbo"],
        yerr=[
            summary["mean_pbo"] - summary["pbo_ci95_low"],
            summary["pbo_ci95_high"] - summary["mean_pbo"],
        ],
        marker="o",
        capsize=4,
        color="#d9472b",
    )
    axes[1].axhline(0.5, color="black", linewidth=0.8, linestyle="--")
    axes[1].set_xscale("log")
    axes[1].set_ylim(0, 1)
    axes[1].set_xlabel("Number of strategies tried")
    axes[1].set_ylabel("Mean probability of backtest overfitting")
    axes[1].set_title("CSCV out-of-sample rank failure")
    figure.tight_layout()
    figure.savefig(output / "selection_bias.png", dpi=180)
    documentation = Path("docs/assets/selection_bias.png")
    documentation.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(documentation, dpi=180)
    plt.close(figure)

    print("ZERO-ALPHA STRATEGY-SELECTION EXPERIMENT")
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print(f"\nSaved results to {output}/")


if __name__ == "__main__":
    main()
