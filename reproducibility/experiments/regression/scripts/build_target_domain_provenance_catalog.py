"""Build target-domain natural-bound provenance catalog.

The catalog records source-backed target-domain bounds used by manuscript
bounded-support audits. It is a provenance artifact, not a validation result.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_target_domain_provenance_v1"
DEFAULT_OUT = Path("experiments/regression/catalogs/target_domain_provenance.json")

ROWS: list[dict[str, Any]] = [
    {
        "dataset_id": "nhanes_2017_2018_bmi",
        "target": "BMXBMI",
        "target_domain_class": "nonnegative",
        "natural_lower": 0.0,
        "natural_upper": None,
        "natural_bound_status": "lower_bound_provenance_present",
        "source_type": "local_dataset_audit_and_endpoint_policy",
        "source_urls": [],
        "source_artifacts": [
            "experiments/regression/audits/nhanes_2017_2018_bmi/audit.json",
            "experiments/regression/reports/duplicate_cluster_sensitivity_nhanes_2017_2018_bmi_identity_ridreth3_model_visible/endpoint_audit.json",
        ],
        "provenance_notes": [
            "BMI target is treated as a nonnegative identity-scale method-engineering target.",
            "Endpoint audits use lower_floor=0.0 for BMI bundles.",
        ],
        "target_transform_inverse_policy": "identity",
    },
    {
        "dataset_id": "nhanes_2017_2018_glycohemoglobin",
        "target": "LBXGH",
        "target_domain_class": "bounded_continuous",
        "natural_lower": 0.0,
        "natural_upper": 100.0,
        "natural_bound_status": "bounded_percentage_provenance_present",
        "source_type": "local_dataset_audit_and_endpoint_policy",
        "source_urls": [],
        "source_artifacts": [
            "experiments/regression/audits/nhanes_2017_2018_glycohemoglobin/audit.json",
            "experiments/regression/reports/duplicate_cluster_sensitivity_nhanes_2017_2018_glycohemoglobin_identity_ridreth3_row_signature/endpoint_audit.json",
            "experiments/regression/reports/duplicate_cluster_sensitivity_nhanes_2017_2018_glycohemoglobin_identity_ridreth3_model_visible/endpoint_audit.json",
        ],
        "provenance_notes": [
            "The local audit describes LBXGH as a glycohemoglobin percentage target.",
            "Endpoint audits use lower_floor=0.0 and upper_warning=100.0.",
        ],
        "target_transform_inverse_policy": "identity",
    },
    {
        "dataset_id": "nhanes_2017_2018_systolic_bp",
        "target": "SYSBP_MEAN_3",
        "target_domain_class": "nonnegative",
        "natural_lower": 0.0,
        "natural_upper": None,
        "natural_bound_status": "lower_bound_provenance_present",
        "source_type": "local_dataset_audit_and_endpoint_policy",
        "source_urls": [],
        "source_artifacts": [
            "experiments/regression/audits/nhanes_2017_2018_systolic_bp/audit.json",
            "experiments/regression/reports/duplicate_cluster_sensitivity_nhanes_2017_2018_systolic_bp_identity_ridreth3_row_signature/endpoint_audit.json",
            "experiments/regression/reports/duplicate_cluster_sensitivity_nhanes_2017_2018_systolic_bp_identity_ridreth3_model_visible/endpoint_audit.json",
        ],
        "provenance_notes": [
            "Systolic blood pressure is treated as a nonnegative identity-scale method-engineering target.",
            "Endpoint audits use lower_floor=0.0 for systolic BP bundles.",
        ],
        "target_transform_inverse_policy": "identity",
    },
    {
        "dataset_id": "stackoverflow_2025_compensation",
        "target": "ConvertedCompYearly",
        "target_domain_class": "nonnegative",
        "natural_lower": 0.0,
        "natural_upper": None,
        "natural_bound_status": "lower_bound_provenance_present",
        "source_type": "local_dataset_audit_and_endpoint_policy",
        "source_urls": [],
        "source_artifacts": [
            "experiments/regression/audits/stackoverflow_2025_compensation/audit.json",
            "experiments/regression/reports/duplicate_cluster_sensitivity_stackoverflow_2025_compensation_log1p_age_row_signature/endpoint_audit.json",
            "experiments/regression/reports/duplicate_cluster_sensitivity_stackoverflow_2025_compensation_log1p_age_model_visible/endpoint_audit.json",
        ],
        "provenance_notes": [
            "The local audit drops nonpositive ConvertedCompYearly values for profiling.",
            "Endpoint audits use lower_floor=0.0 after log1p inverse transformation.",
        ],
        "target_transform_inverse_policy": "log1p inverse uses expm1 on interval endpoints",
    },
    {
        "dataset_id": "uci_wine_quality",
        "target": "quality",
        "target_domain_class": "bounded_ordinal",
        "natural_lower": 0.0,
        "natural_upper": 10.0,
        "natural_bound_status": "bounded_ordinal_source_provenance_present",
        "source_type": "official_uci_dataset_metadata",
        "source_urls": [
            "https://archive.ics.uci.edu/dataset/186/wine%2Bquality",
            "https://doi.org/10.24432/C56S3T",
        ],
        "source_artifacts": [
            "experiments/regression/audits/uci_wine_quality/audit.json",
            "experiments/regression/audits/uci_wine_quality_dedup/audit.json",
        ],
        "provenance_notes": [
            "The official UCI Wine Quality metadata describes the output variable as quality score between 0 and 10.",
            "The local audit observes scores 3 through 9, so observed-range endpoint diagnostics are narrower than the source-backed natural ordinal scale.",
        ],
        "target_transform_inverse_policy": "identity on ordinal score scale",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def source_artifact_exists(root: Path, row: dict[str, Any]) -> bool:
    return all((root / artifact).exists() for artifact in row.get("source_artifacts", []))


def build_payload(root: Path) -> dict[str, Any]:
    rows = []
    for row in ROWS:
        current = dict(row)
        current["source_artifacts_present"] = source_artifact_exists(root, current)
        rows.append(current)
    failed_checks = []
    if not rows:
        failed_checks.append("rows_present")
    if len({(row["dataset_id"], row["target"]) for row in rows}) != len(rows):
        failed_checks.append("unique_dataset_target_rows")
    if not all(row["source_artifacts_present"] for row in rows):
        failed_checks.append("all_source_artifacts_present")
    if not any(row["dataset_id"] == "uci_wine_quality" for row in rows):
        failed_checks.append("uci_wine_quality_row_present")
    if not all(row.get("natural_bound_status") for row in rows):
        failed_checks.append("all_rows_have_bound_status")
    status = (
        "target_domain_provenance_ready"
        if not failed_checks
        else "target_domain_provenance_incomplete"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": status,
            "failed_check_count": len(failed_checks),
            "row_count": len(rows),
            "source_artifact_complete_count": sum(
                1 for row in rows if row["source_artifacts_present"]
            ),
            "external_source_row_count": sum(
                1 for row in rows if row.get("source_urls")
            ),
            "bounded_ordinal_row_count": sum(
                1 for row in rows if row.get("target_domain_class") == "bounded_ordinal"
            ),
        },
        "failed_checks": failed_checks,
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Target Domain Provenance",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Failed checks: {summary['failed_check_count']}",
        f"- Rows: {summary['row_count']}",
        f"- Rows with all local source artifacts present: {summary['source_artifact_complete_count']}",
        f"- Rows with external source URLs: {summary['external_source_row_count']}",
        f"- Bounded-ordinal rows: {summary['bounded_ordinal_row_count']}",
        "",
        "## Rows",
        "",
        "| Dataset | Target | Class | Bounds | Status | Source type |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        bounds = f"{row.get('natural_lower')} / {row.get('natural_upper')}"
        lines.append(
            "| "
            f"`{row['dataset_id']}` | "
            f"`{row['target']}` | "
            f"`{row['target_domain_class']}` | "
            f"{bounds} | "
            f"`{row['natural_bound_status']}` | "
            f"`{row['source_type']}` |"
        )
    lines.extend(
        [
            "",
            "## Source Notes",
            "",
        ]
    )
    for row in payload["rows"]:
        lines.append(f"### `{row['dataset_id']}::{row['target']}`")
        for note in row.get("provenance_notes", []):
            lines.append(f"- {note}")
        for url in row.get("source_urls", []):
            lines.append(f"- Source URL: {url}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = resolve(root, args.out)
    payload = build_payload(root)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok" if not payload["failed_checks"] else "fail",
                "out": rel(out_path, root),
                **payload["summary"],
            },
            sort_keys=True,
        )
    )
    return 1 if payload["failed_checks"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
