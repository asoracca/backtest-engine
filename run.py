"""Example: run a 20/50 moving-average crossover through the engine."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from engine.backtest import Backtest
from engine.strategy import MovingAverageCross
from engine.metrics import performance


def main():
    symbols, cap = ["AAPL"], 100000.0
    bt = Backtest(symbols, "2018-01-01", cap, MovingAverageCross, short=20, long=50)
    equity = bt.run()
    stats, df = performance(equity, cap)
    print("Moving-average crossover (20/50) on %s" % symbols[0])
    print("  Final equity:  $%s" % format(stats["final_equity"], ",.0f"))
    print("  Total return:  %+.1f%%" % (stats["total_return"] * 100))
    print("  Annual return: %+.1f%%" % (stats["annual_return"] * 100))
    print("  Sharpe:        %.2f" % stats["sharpe"])
    print("  Max drawdown:  %.1f%%" % (stats["max_drawdown"] * 100))
    plt.figure(figsize=(10, 5))
    plt.plot(df.index, df["equity"])
    plt.title("Equity curve — MA(20/50) on %s" % symbols[0])
    plt.grid(alpha=0.3); plt.tight_layout()
    os.makedirs("data", exist_ok=True)
    plt.savefig("data/equity_curve.png", dpi=110)
    print("  Saved: data/equity_curve.png")


if __name__ == "__main__":
    main()
