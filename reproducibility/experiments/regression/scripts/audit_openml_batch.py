"""Materialize OpenML audit/profile files from a durable JSONL batch spec."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cpfi.regression.datasets import (
    audit_regression_frame,
    load_openml_regression_frame,
    render_audit_markdown,
)
from cpfi.regression.experiment import atomic_write_json, atomic_write_text
try:
    from profile_openml_regression_dataset import (
        build_profile,
        json_safe,
        openml_metadata,
        render_markdown,
    )
except ModuleNotFoundError:
    from experiments.regression.scripts.profile_openml_regression_dataset import (
        build_profile,
        json_safe,
        openml_metadata,
        render_markdown,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--spec",
        required=True,
        help="JSONL file with openml_id, target, dataset_id, and optional group_columns.",
    )
    parser.add_argument(
        "--out-dir",
        default="experiments/regression/audits",
        help="Root directory for generated audit/profile files.",
    )
    parser.add_argument("--max-description-chars", type=int, default=900)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def materialize_record(record: dict[str, Any], *, out_root: Path, description_chars: int) -> dict[str, Any]:
    dataset_id = record["dataset_id"]
    openml_id = int(record["openml_id"])
    target = record["target"]
    group_columns = record.get("group_columns", [])
    out_dir = out_root / dataset_id

    metadata = openml_metadata(openml_id, description_chars)
    df = load_openml_regression_frame(openml_id, target)

    audit = audit_regression_frame(df, target=target, dataset_id=dataset_id).to_dict()
    audit["openml_id"] = openml_id
    atomic_write_json(out_dir / "audit.json", audit)
    atomic_write_text(out_dir / "audit.md", render_audit_markdown(audit))

    profile = build_profile(
        df,
        dataset_id=dataset_id,
        target=target,
        group_columns=group_columns,
        metadata=metadata,
    )
    safe_profile = json_safe(profile)
    atomic_write_json(out_dir / "profile.json", safe_profile)
    atomic_write_text(out_dir / "profile.md", render_markdown(safe_profile))

    return {
        "dataset_id": dataset_id,
        "openml_id": openml_id,
        "audit_path": str(out_dir / "audit.json"),
        "profile_path": str(out_dir / "profile.json"),
    }


def main() -> None:
    args = parse_args()
    records = read_jsonl(Path(args.spec))
    outputs = [
        materialize_record(
            record,
            out_root=Path(args.out_dir),
            description_chars=args.max_description_chars,
        )
        for record in records
    ]
    print(json.dumps({"status": "ok", "materialized": len(outputs), "outputs": outputs}))


if __name__ == "__main__":
    main()
