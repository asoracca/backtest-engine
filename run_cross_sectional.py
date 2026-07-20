"""Run a transparent sector-ETF cross-sectional momentum experiment."""

from pathlib import Path

import pandas as pd

from engine.backtest import Backtest
from engine.data import download_price_data
from engine.metrics import performance
from engine.strategy import CrossSectionalMomentum, EqualWeightBuyAndHold


SYMBOLS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
CAPITAL = 100_000.0


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
        for label, result in (("momentum", momentum), ("equal_weight", equal_weight)):
            stats, curve = performance(result["equity"], CAPITAL)
            rows.append({"strategy": label, "cost_bps": bps, **stats, "fills": len(result["fills"])})
            if bps == 5:
                plotted[label] = curve["equity"]

        if bps == 5:
            for name, ledger in momentum.items():
                ledger.to_csv(output / f"momentum_{name}.csv", index=False)
            for name, ledger in equal_weight.items():
                ledger.to_csv(output / f"equal_weight_{name}.csv", index=False)

    sensitivity = pd.DataFrame(rows)
    sensitivity.to_csv(output / "cost_sensitivity.csv", index=False)
    ax = pd.DataFrame(plotted).plot(
        figsize=(11, 6),
        title="Sector ETFs: 12-1 momentum vs equal-weight buy-and-hold (5 bps)",
    )
    ax.set_ylabel("Portfolio value ($)")
    ax.figure.tight_layout()
    ax.figure.savefig(output / "equity_comparison.png", dpi=150)

    print(sensitivity.to_string(index=False))
    print(f"\nSaved results to {output}/")


if __name__ == "__main__":
    main()
