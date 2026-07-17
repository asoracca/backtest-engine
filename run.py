"""Reproducible example, benchmark, and transaction-cost sensitivity study."""

from pathlib import Path

import pandas as pd

from engine.backtest import Backtest
from engine.data import download_price_data
from engine.metrics import buy_and_hold, performance
from engine.strategy import MovingAverageCross


def main():
    symbol, capital = "SPY", 100_000.0
    price_data = download_price_data([symbol], "2015-01-01", "2025-01-01")
    output = Path("data")
    output.mkdir(exist_ok=True)

    curves = {}
    sensitivity = []
    for bps in (0, 1, 5, 10):
        result = Backtest(
            [symbol],
            price_data=price_data,
            initial_capital=capital,
            strategy_cls=MovingAverageCross,
            strategy_kwargs={"short": 20, "long": 50, "gross_allocation": .90},
            slippage_bps=bps,
        ).run()
        stats, curve = performance(result["equity"], capital)
        curves[f"MA 20/50 ({bps} bps)"] = curve["equity"]
        sensitivity.append({"slippage_bps": bps, **stats, "fills": len(result["fills"])})
        if bps == 1:
            for name, ledger in result.items():
                ledger.to_csv(output / f"{name}.csv", index=False)

    benchmark = buy_and_hold(price_data[symbol], capital, slippage_bps=1)
    benchmark_stats, benchmark_curve = performance(benchmark, capital)
    curves["Buy & hold (1 bps)"] = benchmark_curve["equity"]
    pd.DataFrame(sensitivity).to_csv(output / "cost_sensitivity.csv", index=False)

    ax = pd.DataFrame(curves).plot(figsize=(11, 6), title="SPY: MA(20/50) vs cost-matched buy & hold")
    ax.set_ylabel("Portfolio value ($)")
    ax.figure.tight_layout()
    ax.figure.savefig(output / "equity_curve.png", dpi=150)
    print(pd.DataFrame(sensitivity).to_string(index=False))
    print("\nBuy & hold (1 bps):", benchmark_stats)
    print("\nSaved ledgers, sensitivity results, and chart to data/")


if __name__ == "__main__":
    main()
