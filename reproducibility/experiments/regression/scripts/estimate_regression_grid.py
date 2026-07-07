"""Estimate regression experiment grid sizes before launching long runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_regression_pilot import _allowed, iter_model_configs, iter_runs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="experiments/regression/configs/pilot.yaml")
    parser.add_argument("--dataset", action="append", default=None)
    parser.add_argument("--model-id", action="append", default=None)
    parser.add_argument("--cp-method", action="append", default=None)
    parser.add_argument("--seed", action="append", type=int, default=None)
    parser.add_argument("--alpha", action="append", type=float, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    model_configs = [
        {"model_id": model_id, "family": family, "params": params}
        for model_id, family, params in iter_model_configs(config)
        if _allowed(model_id, args.model_id)
    ]
    runs = list(iter_runs(config, args))
    payload = {
        "config": args.config,
        "datasets": [
            dataset for dataset in config["datasets"] if _allowed(dataset, args.dataset)
        ],
        "seeds": [seed for seed in config["random_seeds"] if _allowed(seed, args.seed)],
        "alphas": [alpha for alpha in config["alphas"] if _allowed(float(alpha), args.alpha)],
        "cp_methods": [
            method for method in config["cp_methods"] if _allowed(method, args.cp_method)
        ],
        "model_config_count": len(model_configs),
        "run_count": len(runs),
        "first_runs": [
            {
                "dataset_id": dataset_id,
                "model_id": model_id,
                "family": family,
                "params": params,
                "cp_method": cp_method,
                "alpha": alpha,
                "seed": seed,
            }
            for dataset_id, model_id, family, params, cp_method, alpha, seed in runs[:5]
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
