"""Store and reproduce runs without importing executable names from a database."""

from .backtest import Backtest
from .demo import DemoStrategy
from .reproducibility import decode_frames, digest, engine_hash, strategy_hash, versions
from .storage import ExperimentStore, snapshot, validate
from .strategy import CrossSectionalMomentum, EqualWeightBuyAndHold, MovingAverageCross

STRATEGIES = {
    f"{cls.__module__}:{cls.__qualname__}": cls
    for cls in (DemoStrategy, CrossSectionalMomentum, EqualWeightBuyAndHold, MovingAverageCross)
}


def record_run(backtest: Backtest, store: ExperimentStore):
    result = backtest.run()
    store.save(snapshot(backtest, result))
    return result


def replay(store: ExperimentStore, run_id: str, registry=None):
    saved = store.load(run_id)
    validate(saved)
    metadata = saved["metadata"]
    config = dict(metadata["config"])
    name = config.pop("strategy")
    strategies = STRATEGIES if registry is None else registry
    if name not in strategies:
        raise ValueError(f"strategy must be explicitly registered for replay: {name}")
    cls = strategies[name]
    if (
        metadata["engine_hash"] != engine_hash()
        or metadata["versions"] != versions()
        or metadata["strategy_hash"] is None
        or metadata["strategy_hash"] != strategy_hash(cls)
    ):
        raise ValueError(
            "exact replay requires matching engine source, strategy source and dependency versions"
        )
    bt = Backtest(
        **config,
        strategy_cls=cls,
        price_data=decode_frames(saved["inputs"]),
        provenance=metadata["provenance"],
    )
    result = bt.run()
    if digest(snapshot(bt, result)) != digest(saved):
        raise ValueError("deterministic replay mismatch")
    return result
