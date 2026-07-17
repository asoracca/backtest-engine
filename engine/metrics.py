"""Performance statistics and a cost-matched buy-and-hold benchmark."""

from __future__ import annotations

import numpy as np
import pandas as pd


def performance(equity, initial_capital):
    frame = equity.copy() if isinstance(equity, pd.DataFrame) else pd.DataFrame(equity)
    if frame.empty:
        raise ValueError("equity curve is empty")
    frame = frame.set_index("dt") if "dt" in frame.columns else frame
    frame["returns"] = frame["equity"].pct_change().fillna(0.0)
    final = float(frame["equity"].iloc[-1])
    total = final / initial_capital - 1.0
    periods = max(len(frame) - 1, 1)
    annual = (final / initial_capital) ** (252.0 / periods) - 1.0
    volatility = frame["returns"].std(ddof=0)
    sharpe = np.sqrt(252.0) * frame["returns"].mean() / volatility if volatility > 0 else 0.0
    drawdown = frame["equity"] / frame["equity"].cummax() - 1.0
    return {
        "final_equity": final,
        "total_return": total,
        "annual_return": annual,
        "sharpe": float(sharpe),
        "max_drawdown": float(drawdown.min()),
    }, frame


def buy_and_hold(frame, initial_capital, commission_per_share=0.005, minimum_commission=1.0, slippage_bps=1.0):
    """Buy at the first open and mark at every close using the same entry costs."""
    bars = frame.copy()
    entry = float(bars["Open"].iloc[0]) * (1.0 + slippage_bps / 10_000.0)
    quantity = int((initial_capital - minimum_commission) // entry)
    commission = max(minimum_commission, quantity * commission_per_share)
    while quantity > 0 and quantity * entry + commission > initial_capital:
        quantity -= 1
        commission = max(minimum_commission, quantity * commission_per_share)
    cash = initial_capital - quantity * entry - commission
    return pd.DataFrame({"dt": bars.index, "equity": cash + quantity * bars["Close"].to_numpy()})
