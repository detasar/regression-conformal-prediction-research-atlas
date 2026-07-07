"""Audit Fairlearn Diabetes 130-Hospitals as a bounded regression source."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cpfi.regression.datasets import audit_regression_frame, render_audit_markdown
from cpfi.regression.experiment import atomic_write_json, atomic_write_text

try:
    from profile_openml_regression_dataset import (
        group_profile,
        json_safe,
        target_summary,
        top_abs_correlations,
    )
except ModuleNotFoundError:
    from experiments.regression.scripts.profile_openml_regression_dataset import (
        group_profile,
        json_safe,
        target_summary,
        top_abs_correlations,
    )


DATASET_ID = "fairlearn_diabetes_hospital_los"
TARGET = "time_in_hospital"
GROUP_COLUMNS = ["race", "gender", "age"]
LEAKAGE_DROP_COLUMNS = ["readmitted", "readmit_binary", "readmit_30_days"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-dir",
        default="experiments/regression/audits",
        help="Root directory for generated audit/profile files.",
    )
    return parser.parse_args()


def load_frame():
    from fairlearn.datasets import fetch_diabetes_hospital

    bunch = fetch_diabetes_hospital(as_frame=True)
    frame = bunch.frame.drop(columns=LEAKAGE_DROP_COLUMNS)
    return frame, bunch


def build_profile(frame, bunch) -> dict[str, Any]:
    audit = audit_regression_frame(frame, target=TARGET, dataset_id=DATASET_ID).to_dict()
    return {
        "dataset_id": DATASET_ID,
        "target": TARGET,
        "source": {
            "name": "Fairlearn Diabetes 130-Hospitals",
            "fairlearn_loader": "fairlearn.datasets.fetch_diabetes_hospital",
            "fairlearn_doc": "https://fairlearn.org/main/api_reference/generated/fairlearn.datasets.fetch_diabetes_hospital.html",
            "uci_page": "https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008",
            "openml_id": 43874,
            "description_excerpt": (getattr(bunch, "DESCR", "") or "")[:900],
            "dropped_leakage_columns": LEAKAGE_DROP_COLUMNS,
        },
        "shape": {"rows": int(frame.shape[0]), "columns": int(frame.shape[1])},
        "audit": audit,
        "target_summary": target_summary(frame[TARGET]),
        "group_profiles": [
            group_profile(frame, TARGET, column) for column in GROUP_COLUMNS
        ],
        "top_abs_correlations": top_abs_correlations(frame, TARGET),
    }


def render_profile_markdown(profile: dict[str, Any]) -> str:
    audit = profile["audit"]
    source = profile["source"]
    lines = [
        f"# Dataset Profile: {profile['dataset_id']}",
        "",
        "## Source",
        "",
        f"- Name: {source['name']}",
        f"- Fairlearn loader: `{source['fairlearn_loader']}`",
        f"- Fairlearn docs: {source['fairlearn_doc']}",
        f"- UCI page: {source['uci_page']}",
        f"- OpenML id: {source['openml_id']}",
        f"- Target: `{profile['target']}`",
        f"- Rows/columns: {profile['shape']['rows']} / {profile['shape']['columns']}",
        f"- Dropped leakage columns: {', '.join(source['dropped_leakage_columns'])}",
        "",
        "## Audit Summary",
        "",
        f"- Target missing rate: {audit['target_missing_rate']:.4f}",
        f"- Target mean/std: {audit['target_mean']:.4f} / {audit['target_std']:.4f}",
        f"- Target skew: {audit['target_skew']:.4f}",
        f"- Target range: {audit['target_min']:.4f} to {audit['target_max']:.4f}",
        f"- Duplicate row rate: {audit['duplicate_row_rate']:.4f}",
        f"- Sensitive/proxy candidates: {', '.join(audit['sensitive_candidates']) or 'none_detected'}",
        f"- Recommended actions: {', '.join(audit['recommended_actions']) or 'none'}",
        "",
        "## Group Target Profiles",
        "",
    ]
    for group in profile["group_profiles"]:
        lines.extend(
            [
                f"### `{group['column']}`",
                "",
                f"- Mode: {group['mode']}",
                f"- Missing rate: {group['missing_rate']:.4f}",
                f"- Unique values: {group['unique_values']}",
                "",
                "| Level | n | share | target mean | target median |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for row in group["levels"]:
            mean = "" if row["target_mean"] is None else f"{row['target_mean']:.4f}"
            median = "" if row["target_median"] is None else f"{row['target_median']:.4f}"
            lines.append(
                f"| {row['level']} | {row['n']} | {row['share']:.4f} | {mean} | {median} |"
            )
        lines.append("")

    lines.extend(["## Top Numeric Correlations With Target", ""])
    if profile["top_abs_correlations"]:
        lines.extend(["| Column | Pearson r | n |", "|---|---:|---:|"])
        for row in profile["top_abs_correlations"]:
            lines.append(f"| `{row['column']}` | {row['pearson_corr']:.4f} | {row['n']} |")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir) / DATASET_ID
    frame, bunch = load_frame()
    profile = json_safe(build_profile(frame, bunch))
    audit = profile["audit"]
    audit["source_loader"] = "fairlearn.datasets.fetch_diabetes_hospital"
    audit["dropped_leakage_columns"] = LEAKAGE_DROP_COLUMNS

    atomic_write_json(out_dir / "audit.json", audit)
    atomic_write_text(out_dir / "audit.md", render_audit_markdown(audit))
    atomic_write_json(out_dir / "profile.json", profile)
    atomic_write_text(out_dir / "profile.md", render_profile_markdown(profile))
    print(json.dumps({"status": "ok", "audit_path": str(out_dir / "audit.json")}))


if __name__ == "__main__":
    main()
