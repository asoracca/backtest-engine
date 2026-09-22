"""Offline experiment storage, replay and comparable-run reporting."""

import argparse
import json

from engine.backtest import Backtest
from engine.demo import DemoStrategy, demo_data, render_demo
from engine.experiments import record_run, replay
from engine.storage import SQLiteStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="experiments.sqlite")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")
    replayer = sub.add_parser("replay")
    replayer.add_argument("run_id")
    compare = sub.add_parser("compare")
    compare.add_argument("run_ids", nargs="+")
    costs = sub.add_parser("costs")
    costs.add_argument("run_id")
    plan = sub.add_parser("plan")
    plan.add_argument("run_id")
    args = parser.parse_args()
    with SQLiteStore(args.db) as store:
        if args.command == "demo":
            for bps in (0, 1, 5, 10):
                bt = Backtest(
                    ["A", "B"],
                    price_data=demo_data(),
                    initial_capital=100,
                    strategy_cls=DemoStrategy,
                    commission_per_share=0,
                    minimum_commission=1,
                    slippage_bps=bps,
                    calendar_policy="strict",
                    provenance={"kind": "synthetic", "source": "fixtures/synthetic/ohlc.csv v1"},
                )
                result = record_run(bt, store)
                replay(store, bt.run_id)
                print(f"{bps} bps: {bt.run_id} (stored and exact replay verified)")
            print(render_demo(result))
            print(json.dumps(store.cost_sensitivity(bt.run_id), indent=2))
        elif args.command == "replay":
            replay(store, args.run_id)
            print(f"Exact replay verified: {args.run_id}")
        elif args.command == "compare":
            print(json.dumps(store.compare(args.run_ids), indent=2))
        elif args.command == "costs":
            print(json.dumps(store.cost_sensitivity(args.run_id), indent=2))
        else:
            print(json.dumps(store.query_plan(args.run_id), indent=2))


if __name__ == "__main__":
    main()
