"""Monitor progress of a regression experiment ledger against its config grid."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_regression_pilot import iter_runs
from summarize_regression_results import load_ledger, summarize_ledger_metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="experiments/regression/configs/pilot.yaml")
    parser.add_argument("--ledger", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    ledger = Path(args.ledger or config["logging"]["ledger"])
    total = len(list(iter_runs(config, argparse.Namespace(
        dataset=None,
        model_id=None,
        cp_method=None,
        seed=None,
        alpha=None,
    ))))
    df = load_ledger(ledger)
    metadata = summarize_ledger_metadata(df)
    completed = metadata["status_counts"].get("completed", 0)
    payload = {
        "config": args.config,
        "ledger": str(ledger),
        "estimated_total_runs": total,
        "ledger_rows": metadata["ledger_rows"],
        "unique_run_rows": metadata["unique_run_rows"],
        "status_counts": metadata["status_counts"],
        "raw_status_counts": metadata["raw_status_counts"],
        "dataset_counts": metadata["dataset_counts"],
        "completed_fraction": completed / total if total else None,
        "last_record": df.tail(1).to_dict(orient="records")[0] if not df.empty else None,
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
