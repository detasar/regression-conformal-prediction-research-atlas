"""Audit the AIF360 Law School GPA regression dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aif360.sklearn.datasets import fetch_lawschool_gpa

from cpfi.regression.datasets import audit_regression_frame, render_audit_markdown
from cpfi.regression.experiment import atomic_write_json, atomic_write_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-id", default="aif360_lawschool_gpa")
    parser.add_argument("--out-dir", default="experiments/regression/audits")
    parser.add_argument("--binary-race", action="store_true", default=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    X, y = fetch_lawschool_gpa(subset="all", binary_race=args.binary_race)
    df = X.reset_index(drop=True).copy()
    df[y.name] = y.reset_index(drop=True).astype(float)

    audit = audit_regression_frame(df, target=y.name, dataset_id=args.dataset_id)
    payload = audit.to_dict()
    payload["source"] = "aif360.sklearn.datasets.fetch_lawschool_gpa"
    payload["binary_race"] = bool(args.binary_race)

    out_dir = Path(args.out_dir) / args.dataset_id
    atomic_write_json(out_dir / "audit.json", payload)
    atomic_write_text(out_dir / "audit.md", render_audit_markdown(payload))
    print(json.dumps({"status": "ok", "audit_path": str(out_dir / "audit.json")}))


if __name__ == "__main__":
    main()
