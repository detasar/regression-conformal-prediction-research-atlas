"""Audit one OpenML regression dataset and write durable metadata.

Example:
    conda run -n ml python experiments/regression/scripts/audit_openml_dataset.py \
        --openml-id 43939 --target median_house_value --dataset-id openml_california_housing
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cpfi.regression.datasets import (
    audit_regression_frame,
    load_openml_regression_frame,
    render_audit_markdown,
)
from cpfi.regression.experiment import atomic_write_json, atomic_write_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openml-id", type=int, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument(
        "--out-dir",
        default="experiments/regression/audits",
        help="Directory for JSON and markdown audit outputs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir) / args.dataset_id
    df = load_openml_regression_frame(args.openml_id, args.target)
    audit = audit_regression_frame(df, target=args.target, dataset_id=args.dataset_id)
    payload = audit.to_dict()
    payload["openml_id"] = args.openml_id

    atomic_write_json(out_dir / "audit.json", payload)
    atomic_write_text(out_dir / "audit.md", render_audit_markdown(payload))
    print(json.dumps({"status": "ok", "audit_path": str(out_dir / "audit.json")}))


if __name__ == "__main__":
    main()
