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
        calendar_policy="common",
    ):
        if calendar_policy not in ("common", "strict"):
            raise ValueError("calendar_policy must be common or strict")
        self.calendar_policy = calendar_policy
        self.events = events
        self.symbols = list(symbols)
        if len(set(self.symbols)) != len(self.symbols):
            raise ValueError("symbols must be unique")
        if not self.symbols:
            raise ValueError("at least one symbol is required")

        source = dict(price_data) if price_data is not None else download_price_data(self.symbols, start, end)
        missing = set(self.symbols).difference(source)
        if missing:
            raise ValueError(f"missing price data for: {sorted(missing)}")

        self.frames = {symbol: self._normalize(source[symbol], symbol) for symbol in self.symbols}
        self.source_frames = self.frames.copy()
        common = self.frames[self.symbols[0]].index
        for symbol in self.symbols[1:]:
            common = common.intersection(self.frames[symbol].index)
        common = common.sort_values()
        self.excluded_dates = {
            symbol: [dt.isoformat() for dt in frame.index.difference(common)]
            for symbol, frame in self.frames.items()
        }
        if calendar_policy == "strict" and any(self.excluded_dates.values()):
            raise ValueError("missing bars or delisting: strict calendar requires identical dates")
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
        renamed = frame.rename(columns={c: str(c).title() for c in frame.columns})
        for column in ("Dividends", "Stock Splits", "Delisted", "Stale"):
            if column in renamed and (renamed[column].fillna(0) != 0).any():
                raise ValueError(f"{symbol}: unsupported data flag {column}")
        if not {"Open", "Close"}.issubset(renamed.columns):
            raise ValueError(f"{symbol} requires Open and Close columns")
        out = renamed[["Open", "Close"]].copy()
        out.index = pd.DatetimeIndex(pd.to_datetime(out.index)).tz_localize(None)
        if out.index.has_duplicates or out.index.isna().any():
            raise ValueError(f"{symbol}: duplicate or invalid timestamps")
        out = out.sort_index().astype(float)
        if not np.isfinite(out.to_numpy()).all():
            raise ValueError(f"{symbol}: prices must be finite; missing/stale bars cannot be filled")
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
