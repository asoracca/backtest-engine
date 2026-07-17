"""Historical bar data with network-free DataFrame injection for tests."""

from __future__ import annotations

from collections.abc import Mapping
from queue import Queue

import numpy as np
import pandas as pd

from .events import MarketEvent


def download_price_data(symbols, start, end=None) -> dict[str, pd.DataFrame]:
    """Download adjusted OHLC bars. Imported lazily so tests need no network."""
    import yfinance as yf

    output: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        raw = yf.download(
            symbol,
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
        )
        if raw.empty:
            raise ValueError(f"no price data returned for {symbol}")
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        output[symbol] = raw[["Open", "Close"]].copy()
    return output


class DataHandler:
    """Streams a common calendar of Open/Close bars one timestamp at a time."""

    def __init__(
        self,
        events: Queue,
        symbols,
        start=None,
        end=None,
        price_data: Mapping[str, pd.DataFrame] | None = None,
    ):
        self.events = events
        self.symbols = list(symbols)
        if not self.symbols:
            raise ValueError("at least one symbol is required")

        source = (
            dict(price_data)
            if price_data is not None
            else download_price_data(self.symbols, start, end)
        )
        missing = set(self.symbols).difference(source)
        if missing:
            raise ValueError(f"missing price data for: {sorted(missing)}")

        self.frames = {symbol: self._normalize(source[symbol], symbol) for symbol in self.symbols}
        common = self.frames[self.symbols[0]].index
        for symbol in self.symbols[1:]:
            common = common.intersection(self.frames[symbol].index)
        common = common.sort_values()
        if len(common) < 2:
            raise ValueError("symbols need at least two common bars")

        self.frames = {symbol: frame.loc[common].copy() for symbol, frame in self.frames.items()}
        self.dates = list(common)
        self.i = -1
        self.current_dt = None
        self.continue_backtest = True

    @staticmethod
    def _normalize(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
        if not isinstance(frame, pd.DataFrame):
            raise TypeError(f"price_data[{symbol!r}] must be a DataFrame")
        renamed = frame.rename(columns={str(c).lower(): str(c).title() for c in frame.columns})
        if not {"Open", "Close"}.issubset(renamed.columns):
            raise ValueError(f"{symbol} requires Open and Close columns")
        out = renamed[["Open", "Close"]].copy()
        out.index = pd.DatetimeIndex(pd.to_datetime(out.index)).tz_localize(None)
        out = out[~out.index.duplicated(keep="last")].sort_index().astype(float).dropna()
        if (out <= 0).any().any():
            raise ValueError(f"{symbol} contains non-positive prices")
        return out

    def update_bars(self) -> None:
        self.i += 1
        if self.i >= len(self.dates):
            self.continue_backtest = False
            return
        self.current_dt = self.dates[self.i]
        self.events.put(MarketEvent(self.current_dt.to_pydatetime()))

    def get_latest_open(self, symbol: str) -> float:
        return float(self.frames[symbol].iloc[self.i]["Open"])

    def get_latest_close(self, symbol: str) -> float:
        return float(self.frames[symbol].iloc[self.i]["Close"])

    def get_latest_closes(self, symbol: str, n: int) -> np.ndarray:
        lo = max(0, self.i - n + 1)
        return self.frames[symbol]["Close"].iloc[lo : self.i + 1].to_numpy(dtype=float)

    def frame(self, symbol: str) -> pd.DataFrame:
        return self.frames[symbol].copy()

