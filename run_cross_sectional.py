"""Run a transparent sector-ETF cross-sectional momentum experiment."""

from pathlib import Path

import numpy as np
import pandas as pd

from engine.backtest import Backtest
from engine.data import download_price_data
from engine.metrics import performance
from engine.strategy import CrossSectionalMomentum, EqualWeightBuyAndHold


SYMBOLS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
CAPITAL = 100_000.0


def annualized_turnover(result, periods_per_year=252):
    """Annualized traded notional divided by same-day portfolio equity."""
    fills = result["fills"]
    equity = result["equity"].copy()
    if fills.empty or len(equity) < 2:
        return 0.0

    equity["dt"] = pd.to_datetime(equity["dt"])
    equity_by_date = equity.set_index("dt")["equity"]
    traded = fills.copy()
    traded["fill_dt"] = pd.to_datetime(traded["fill_dt"])
    traded["notional"] = traded["quantity"].abs() * traded["fill_price"]
    daily_notional = traded.groupby("fill_dt")["notional"].sum()
    daily_turnover = daily_notional / equity_by_date.reindex(daily_notional.index)
    periods = len(equity_by_date) - 1
    return float(daily_turnover.sum() * periods_per_year / periods)


def active_performance(momentum_equity, benchmark_equity, periods_per_year=252):
    """Return active mean, tracking error, and information ratio."""
    curves = []
    for name, frame in (
        ("momentum", momentum_equity),
        ("benchmark", benchmark_equity),
    ):
        curve = frame.copy()
        curve["dt"] = pd.to_datetime(curve["dt"])
        curves.append(curve.set_index("dt")["equity"].rename(name))

    aligned = pd.concat(curves, axis=1, join="inner").dropna()
    returns = aligned.pct_change().dropna()
    active = returns["momentum"] - returns["benchmark"]
    if active.empty:
        return {
            "annualized_active_return": 0.0,
            "tracking_error": 0.0,
            "information_ratio": 0.0,
        }

    annualized_active_return = float(active.mean() * periods_per_year)
    tracking_error = float(active.std(ddof=1) * np.sqrt(periods_per_year))
    information_ratio = annualized_active_return / tracking_error if tracking_error > 0 else 0.0
    return {
        "annualized_active_return": annualized_active_return,
        "tracking_error": tracking_error,
        "information_ratio": information_ratio,
    }


def run_strategy(price_data, strategy_cls, bps, strategy_kwargs):
    return Backtest(
        SYMBOLS,
        price_data=price_data,
        initial_capital=CAPITAL,
        strategy_cls=strategy_cls,
        strategy_kwargs=strategy_kwargs,
        commission_per_share=0.005,
        minimum_commission=1.0,
        slippage_bps=bps,
    ).run()


def main():
    output = Path("data/cross_sectional")
    output.mkdir(parents=True, exist_ok=True)
    price_data = download_price_data(SYMBOLS, "2010-01-01", "2025-01-01")

    strategy_kwargs = {
        "lookback": 252,
        "skip": 21,
        "rebalance_every": 21,
        "top_fraction": 1 / 3,
        "gross_allocation": 0.90,
    }
    benchmark_kwargs = {"gross_allocation": 0.90}
    rows = []
    active_rows = []
    plotted = {}

    for bps in (0, 5, 10, 25):
        momentum = run_strategy(
            price_data,
            CrossSectionalMomentum,
            bps,
            strategy_kwargs,
        )
        equal_weight = run_strategy(
            price_data,
            EqualWeightBuyAndHold,
            bps,
            benchmark_kwargs,
        )
        pair = (("momentum", momentum), ("equal_weight", equal_weight))
        for label, result in pair:
            stats, curve = performance(result["equity"], CAPITAL)
            rows.append(
                {
                    "strategy": label,
                    "cost_bps": bps,
                    **stats,
                    "annualized_turnover": annualized_turnover(result),
                    "fills": len(result["fills"]),
                }
            )
            if bps == 5:
                plotted[label] = curve["equity"]

        active_rows.append(
            {
                "cost_bps": bps,
                **active_performance(momentum["equity"], equal_weight["equity"]),
                "ending_wealth_difference": float(
                    momentum["equity"].iloc[-1]["equity"] - equal_weight["equity"].iloc[-1]["equity"]
                ),
            }
        )

        if bps == 5:
            for name, ledger in momentum.items():
                ledger.to_csv(output / f"momentum_{name}.csv", index=False)
            for name, ledger in equal_weight.items():
                ledger.to_csv(output / f"equal_weight_{name}.csv", index=False)

    sensitivity = pd.DataFrame(rows)
    active_summary = pd.DataFrame(active_rows)
    sensitivity.to_csv(output / "cost_sensitivity.csv", index=False)
    active_summary.to_csv(output / "active_performance.csv", index=False)
    ax = pd.DataFrame(plotted).plot(
        figsize=(11, 6),
        title="Sector ETFs: 12-1 momentum vs equal-weight buy-and-hold (5 bps)",
    )
    ax.set_ylabel("Portfolio value ($)")
    ax.figure.tight_layout()
    ax.figure.savefig(output / "equity_comparison.png", dpi=150)

    print("STRATEGY RESULTS")
    print(sensitivity.to_string(index=False))
    print("\nACTIVE PERFORMANCE VS EQUAL WEIGHT")
    print(active_summary.to_string(index=False))
    print(f"\nSaved results to {output}/")


if __name__ == "__main__":
    main()
