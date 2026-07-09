"""Streams historical bars and emits a MarketEvent per trading day."""
import numpy as np
import pandas as pd
import yfinance as yf
from .events import MarketEvent


class DataHandler:
    def __init__(self, events, symbols, start, end=None):
        self.events = events
        self.symbols = symbols
        series = {}
        for s in symbols:
            df = yf.download(s, start=start, end=end, auto_adjust=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                c = df["Close"]
                close = c[s] if s in c.columns else c.iloc[:, 0]
            else:
                close = df["Close"]
            series[s] = close.astype(float).dropna()
        idx = None
        for s in symbols:
            idx = series[s].index if idx is None else idx.intersection(series[s].index)
        idx = idx.sort_values()
        self.dates = list(idx)
        self.closes = {s: series[s].reindex(idx).values for s in symbols}
        self.i = -1
        self.current_dt = None
        self.continue_backtest = True

    def update_bars(self):
        self.i += 1
        if self.i >= len(self.dates):
            self.continue_backtest = False
            return
        self.current_dt = self.dates[self.i]
        self.events.put(MarketEvent())

    def get_latest_close(self, symbol):
        return float(self.closes[symbol][self.i])

    def get_latest_closes(self, symbol, n):
        lo = max(0, self.i - n + 1)
        return np.asarray(self.closes[symbol][lo:self.i + 1], dtype=float)
