"""Atomic experiment storage behind a two-method persistence protocol."""

import json
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import Protocol

from .reproducibility import canonical, digest, ledger_records

SQL = Path(__file__).with_name("sql")
LEDGERS = ("equity", "orders", "fills", "trades", "positions", "cash", "rejections")


class ExperimentStore(Protocol):
    def save(self, experiment: dict) -> None: ...
    def load(self, run_id: str) -> dict: ...


def snapshot(backtest, results):
    return json.loads(
        canonical(
            {
                "run_id": backtest.run_id,
                "metadata": backtest.metadata,
                "inputs": backtest.input_snapshot,
                "events": backtest.event_records,
                "ledgers": ledger_records(results),
            }
        )
    )


def validate(experiment):
    metadata = experiment["metadata"]
    if digest(metadata) != experiment["run_id"]:
        raise ValueError("run identity mismatch")
    if digest(metadata["config"]) != metadata["config_hash"]:
        raise ValueError("configuration hash mismatch")
    if digest(experiment["inputs"]) != metadata["data_hash"]:
        raise ValueError("input hash mismatch")
    if set(experiment["ledgers"]) != set(LEDGERS):
        raise ValueError("incomplete ledger set")
    for i, event in enumerate(experiment["events"]):
        if event["sequence"] != i or event["run_id"] != experiment["run_id"]:
            raise ValueError("event sequence or run identity mismatch")


def comparison_key(metadata, sensitivity=False):
    config = deepcopy(metadata["config"])
    if sensitivity:
        config.pop("slippage_bps")
    else:
        config.pop("strategy")
        config.pop("strategy_kwargs")
    return digest(
        {
            "config": config,
            "data_hash": metadata["data_hash"],
            "timing": metadata["timing"],
            "engine_hash": metadata["engine_hash"],
            "versions": metadata["versions"],
            "provenance": metadata["provenance"],
            "strategy_hash": metadata["strategy_hash"] if sensitivity else None,
        }
    )


class MemoryStore:
    def __init__(self):
        self._runs = {}

    def save(self, experiment):
        validate(experiment)
        run_id = experiment["run_id"]
        if run_id in self._runs and self._runs[run_id] != experiment:
            raise ValueError("non-deterministic result for existing run identity")
        self._runs[run_id] = deepcopy(experiment)

    def load(self, run_id):
        return deepcopy(self._runs[run_id])


class SQLiteStore:
    def __init__(self, path):
        self.connection = sqlite3.connect(path, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def _migrate(self):
        # Lock before inspecting the version so concurrent openers cannot race.
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            version = self.connection.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise ValueError("database schema is newer than this engine")
            if version == 0:
                statement = ""
                for line in (SQL / "001_initial.sql").read_text().splitlines(True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        self.connection.execute(statement)
                        statement = ""
                self.connection.execute("PRAGMA user_version = 1")
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def save(self, experiment):
        validate(experiment)
        run_id, metadata = experiment["run_id"], experiment["metadata"]
        manifest = digest(experiment)
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            existing = self.connection.execute(
                "SELECT manifest_hash FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if existing:
                if existing[0] != manifest:
                    raise ValueError("non-deterministic result for existing run identity")
                self.connection.commit()
                return
            self.connection.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    metadata["data_hash"],
                    metadata["config_hash"],
                    comparison_key(metadata),
                    comparison_key(metadata, True),
                    metadata["config"]["slippage_bps"],
                    canonical(metadata),
                    canonical(experiment["inputs"]),
                    manifest,
                ),
            )
            self.connection.executemany(
                "INSERT INTO events VALUES (?, ?, ?, ?)",
                (
                    (run_id, e["sequence"], e["event"]["type"], canonical(e["event"]))
                    for e in experiment["events"]
                ),
            )
            self.connection.executemany(
                "INSERT INTO ledgers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    (
                        run_id,
                        name,
                        i,
                        row.get("dt", row.get("fill_dt", row.get("submitted_dt"))),
                        row.get("equity"),
                        row.get("cash"),
                        row.get("commission"),
                        row.get("slippage_cost"),
                        canonical(row),
                    )
                    for name, rows in experiment["ledgers"].items()
                    for i, row in enumerate(rows)
                ),
            )
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def load(self, run_id):
        row = self.connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        result = {
            "run_id": run_id,
            "metadata": json.loads(row["metadata"]),
            "inputs": json.loads(row["inputs"]),
            "events": [],
            "ledgers": {name: [] for name in LEDGERS},
        }
        for event in self.connection.execute(
            "SELECT sequence, payload FROM events WHERE run_id = ? ORDER BY sequence", (run_id,)
        ):
            result["events"].append({"run_id": run_id, "sequence": event[0], "event": json.loads(event[1])})
        for ledger in self.connection.execute(
            "SELECT ledger, payload, row_number FROM ledgers WHERE run_id = ? ORDER BY ledger, row_number",
            (run_id,),
        ):
            if ledger[2] != len(result["ledgers"][ledger[0]]):
                raise ValueError("stored ledger ordering mismatch")
            result["ledgers"][ledger[0]].append(json.loads(ledger[1]))
        validate(result)
        if digest(result) != row["manifest_hash"]:
            raise ValueError("stored experiment integrity check failed")
        return result

    def summary(self, run_id):
        self.load(run_id)  # Validate stored content before using the report projections.
        return dict(self.connection.execute((SQL / "summary.sql").read_text(), {"run_id": run_id}).fetchone())

    def compare(self, run_ids, sensitivity=False):
        if not run_ids:
            raise ValueError("at least one run is required")
        runs = [self.load(run_id) for run_id in run_ids]
        if len({comparison_key(run["metadata"], sensitivity) for run in runs}) != 1:
            raise ValueError("incompatible data, timing, capital, costs, provenance or engine versions")
        return [
            dict(
                run_id=r["run_id"],
                slippage_bps=r["metadata"]["config"]["slippage_bps"],
                **self.summary(r["run_id"]),
            )
            for r in runs
        ]

    def cost_sensitivity(self, run_id):
        run = self.load(run_id)
        ids = [
            row[0]
            for row in self.connection.execute(
                "SELECT run_id FROM runs WHERE sensitivity_key = ? ORDER BY slippage_bps, run_id",
                (comparison_key(run["metadata"], True),),
            )
        ]
        return self.compare(ids, sensitivity=True)

    def query_plan(self, run_id):
        return [
            tuple(row)
            for row in self.connection.execute(
                "EXPLAIN QUERY PLAN " + (SQL / "summary.sql").read_text(), {"run_id": run_id}
            )
        ]
