"""Audit one UCI regression dataset and write durable metadata.

Example:
    conda run -n ml python experiments/regression/scripts/audit_uci_dataset.py \
        --uci-id 9 --target mpg --dataset-id uci_auto_mpg
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ucimlrepo import fetch_ucirepo

from cpfi.regression.datasets import audit_regression_frame, render_audit_markdown
from cpfi.regression.experiment import atomic_write_json, atomic_write_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uci-id", type=int, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument(
        "--out-dir",
        default="experiments/regression/audits",
        help="Directory for JSON and markdown audit outputs.",
    )
    return parser.parse_args()


def load_uci_frame(uci_id: int, target: str):
    dataset = fetch_ucirepo(id=uci_id)
    df = dataset.data.features.copy()
    targets = dataset.data.targets.copy()
    if target not in targets.columns:
        raise ValueError(
            f"target {target!r} not found; available targets: {list(targets.columns)}"
        )
    df[target] = targets[target]
    return df, dataset.metadata


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir) / args.dataset_id
    df, metadata = load_uci_frame(args.uci_id, args.target)
    audit = audit_regression_frame(df, target=args.target, dataset_id=args.dataset_id)
    payload = audit.to_dict()
    payload["uci_id"] = args.uci_id
    payload["source_name"] = getattr(metadata, "name", None)

    atomic_write_json(out_dir / "audit.json", payload)
    atomic_write_text(out_dir / "audit.md", render_audit_markdown(payload))
    print(json.dumps({"status": "ok", "audit_path": str(out_dir / "audit.json")}))


if __name__ == "__main__":
    main()
