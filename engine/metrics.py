"""Performance statistics from the equity curve."""
import numpy as np
import pandas as pd


def performance(equity_curve, initial_capital):
    df = pd.DataFrame(equity_curve, columns=["dt", "equity"]).set_index("dt")
    df["returns"] = df["equity"].pct_change().fillna(0.0)
    days = max(len(df), 1)
    final = df["equity"].iloc[-1]
    total = final / initial_capital - 1.0
    ann = (final / initial_capital) ** (252.0 / days) - 1.0
    sharpe = np.sqrt(252) * df["returns"].mean() / df["returns"].std() if df["returns"].std() > 0 else 0.0
    cummax = df["equity"].cummax()
    maxdd = (df["equity"] / cummax - 1.0).min()
    return {"final_equity": final, "total_return": total, "annual_return": ann, "sharpe": sharpe, "max_drawdown": maxdd}, df
