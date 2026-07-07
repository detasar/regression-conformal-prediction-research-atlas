"""Discover OpenML supervised-regression datasets.

This is a metadata discovery helper, not a training script. It writes JSONL
records incrementally so interruption does not destroy progress. Feature-name
inspection is optional because it requires one metadata request per dataset.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable

import openml

from cpfi.regression.datasets import sensitive_name_matches
from cpfi.regression.experiment import append_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--min-instances", type=int, default=None)
    parser.add_argument("--max-instances", type=int, default=None)
    parser.add_argument(
        "--inspect-features",
        action="store_true",
        help="Fetch each OpenML dataset metadata object and inspect feature names.",
    )
    parser.add_argument(
        "--only-sensitive-hits",
        action="store_true",
        help="Write only records with fairness/sensitive name hits.",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_false",
        dest="skip_existing",
        help="Do not skip OpenML ids already present in the output JSONL.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Remove the output JSONL before writing fresh discovery records.",
    )
    parser.add_argument(
        "--out",
        default="experiments/regression/catalogs/openml_discovery.jsonl",
    )
    parser.add_argument(
        "--flush-every",
        type=int,
        default=25,
        help="Number of records to fsync per JSONL append batch.",
    )
    parser.set_defaults(skip_existing=True)
    return parser.parse_args()


def clean_scalar(value):
    if hasattr(value, "item"):
        value = value.item()
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def match_sensitive_terms(values: Iterable[str]) -> list[str]:
    hits = set()
    for value in values:
        if sensitive_name_matches(str(value)):
            hits.add(str(value))
    return sorted(hits)


def load_existing_openml_ids(path: Path) -> set[int]:
    if not path.exists():
        return set()
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        openml_id = record.get("openml_id")
        if openml_id is not None:
            ids.add(int(openml_id))
    return ids


def dataset_feature_names(dataset) -> list[str]:
    names = []
    for _, feature in sorted(dataset.features.items()):
        name = getattr(feature, "name", None)
        names.append(str(name if name is not None else feature))
    return names


def task_record(row, inspect_features: bool) -> dict:
    openml_id = int(row["did"])
    metadata_values = [
        row.get("name"),
        row.get("target_feature"),
        row.get("task_type"),
        row.get("evaluation_measures"),
    ]
    metadata_hits = match_sensitive_terms(str(value) for value in metadata_values if value is not None)
    feature_hits: list[str] = []
    feature_names: list[str] = []
    feature_status = "not_inspected"
    if inspect_features:
        try:
            dataset = openml.datasets.get_dataset(
                openml_id,
                download_data=False,
                download_features_meta_data=True,
            )
            feature_names = dataset_feature_names(dataset)
            feature_hits = match_sensitive_terms(feature_names)
            feature_status = "inspected"
        except Exception as exc:
            feature_status = f"metadata_error: {exc}"

    sensitive_hits = sorted(set(metadata_hits + feature_hits))
    return {
        "openml_id": openml_id,
        "openml_task_id": int(row["tid"]),
        "name": clean_scalar(row.get("name")),
        "source_url": f"https://www.openml.org/d/{openml_id}",
        "task_type": clean_scalar(row.get("task_type")),
        "task_status": clean_scalar(row.get("status")),
        "target_feature": clean_scalar(row.get("target_feature")),
        "estimation_procedure": clean_scalar(row.get("estimation_procedure")),
        "evaluation_measures": clean_scalar(row.get("evaluation_measures")),
        "n_instances": clean_scalar(row.get("NumberOfInstances")),
        "n_features": clean_scalar(row.get("NumberOfFeatures")),
        "n_numeric_features": clean_scalar(row.get("NumberOfNumericFeatures")),
        "n_symbolic_features": clean_scalar(row.get("NumberOfSymbolicFeatures")),
        "n_instances_with_missing": clean_scalar(row.get("NumberOfInstancesWithMissingValues")),
        "n_missing_values": clean_scalar(row.get("NumberOfMissingValues")),
        "metadata_sensitive_hits": metadata_hits,
        "feature_sensitive_hits": feature_hits,
        "sensitive_name_hits": sensitive_hits,
        "feature_inspection_status": feature_status,
        "feature_names_sample": feature_names[:50],
        "status": (
            "candidate_needs_manual_review"
            if sensitive_hits
            else "metadata_only_needs_manual_review"
        ),
    }


def main() -> None:
    args = parse_args()
    out_path = Path(args.out)
    if args.overwrite and out_path.exists():
        out_path.unlink()
    tasks = openml.tasks.list_tasks(
        task_type=openml.tasks.TaskType.SUPERVISED_REGRESSION,
        size=args.limit,
        output_format="dataframe",
    )
    if args.min_instances is not None:
        tasks = tasks[tasks["NumberOfInstances"] >= args.min_instances]
    if args.max_instances is not None:
        tasks = tasks[tasks["NumberOfInstances"] <= args.max_instances]

    existing_ids = load_existing_openml_ids(out_path) if args.skip_existing else set()
    records = []
    written = 0
    seen_ids = set()
    for _, row in tasks.iterrows():
        openml_id = int(row["did"])
        if openml_id in seen_ids or openml_id in existing_ids:
            continue
        seen_ids.add(openml_id)
        record = task_record(row, inspect_features=args.inspect_features)
        if args.only_sensitive_hits and not record["sensitive_name_hits"]:
            continue
        records.append(record)
        if len(records) >= args.flush_every:
            append_jsonl(out_path, records)
            written += len(records)
            records = []

    if records:
        append_jsonl(out_path, records)
        written += len(records)
    print(
        json.dumps(
            {
                "status": "ok",
                "records_written": written,
                "skipped_existing": len(existing_ids),
                "feature_inspection": args.inspect_features,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
