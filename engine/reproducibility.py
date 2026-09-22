"""Canonical, lossless JSON and content identities for reproducible experiments."""

import hashlib
import inspect
import json
import platform
import sqlite3
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

TIMING = "close-signal/next-common-open/close-mark-v1"


def canonical(value):
    def convert(item):
        if is_dataclass(item):
            return asdict(item)
        if isinstance(item, (datetime, pd.Timestamp)):
            return item.isoformat()
        if isinstance(item, np.generic):
            return item.item()
        raise TypeError(f"not serializable: {type(item).__name__}")

    return json.dumps(value, default=convert, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def engine_hash():
    return digest({p.name: p.read_text() for p in sorted(Path(__file__).parent.glob("*.py"))})


def strategy_hash(cls):
    try:
        return digest(inspect.getsource(cls))
    except (OSError, TypeError):
        return None  # Interactive classes still run; stored replay must register source explicitly.


def versions():
    return {
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "sqlite": sqlite3.sqlite_version,
    }


def encode_frames(frames):
    return {
        symbol: [
            {"dt": dt.isoformat(), **{c: float(v) for c, v in row.items()}} for dt, row in frame.iterrows()
        ]
        for symbol, frame in frames.items()
    }


def decode_frames(frames):
    return {
        symbol: pd.DataFrame(rows).assign(dt=lambda f: pd.to_datetime(f.dt)).set_index("dt")
        for symbol, rows in frames.items()
    }


def ledger_records(results):
    return {
        name: frame.astype(object).where(pd.notna(frame), None).to_dict("records")
        for name, frame in results.items()
    }
