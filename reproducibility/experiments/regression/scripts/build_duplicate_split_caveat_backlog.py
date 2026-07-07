"""Build a backlog for duplicate-content split caveats.

The split-profile audit already distinguishes hard split leakage
(row-id/split-group overlap) from duplicate-content overlap. This script turns
the remaining duplicate-content warnings into a machine-readable follow-up
queue so affected datasets can be tracked without overstating the evidence.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_duplicate_split_caveat_backlog_v1"
DEFAULT_OUT = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "duplicate_split_caveat_backlog.json"
)
PAIR_KEYS = ("train_cal", "train_test", "cal_test")
CLAIM_BOUNDARIES = [
    "This is not row-id leakage evidence when row_id_overlap_violations is zero.",
    "This is not split-group leakage evidence when split_group_overlap_violations is zero.",
    "Do not claim strict split independence for affected datasets until a duplicate-aware sensitivity is run.",
    "Do not treat raw random-split results on affected datasets as final model-selection evidence.",
]
ALLOWED_INTERPRETATION = (
    "Hard split leakage checks are clean when row-id and split-group overlap "
    "violation counts are zero, but exact duplicate content remains a "
    "sensitivity caveat for raw split interpretation."
)
NEXT_ACTIONS = [
    "Run a duplicate-aware sensitivity with exact duplicate signatures assigned to the same split where feasible.",
    "Run or reuse an exact de-duplicated dataset variant when it preserves the scientific target definition.",
    "Compare coverage, width, and group-gap diagnostics between raw and duplicate-controlled variants before making strong conclusions.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output JSON path.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def positive_overlap_count(overlaps: Any) -> int:
    if not isinstance(overlaps, dict):
        return 0
    total = 0
    for value in overlaps.values():
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        if count > 0:
            total += count
    return total


def severity_for(total_pair_overlaps: int) -> str:
    if total_pair_overlaps >= 1000:
        return "high"
    if total_pair_overlaps >= 100:
        return "medium"
    return "low"


def report_id_from_split_path(path: Path) -> str:
    return f"report:{path.parent.name}"


def paired_dedup_variant(dataset_id: str, profile_dataset_ids: set[str]) -> str | None:
    candidates = [
        f"{dataset_id}_dedup",
        f"{dataset_id}_exact_dedup",
        dataset_id.replace("_raw", "_dedup"),
    ]
    for candidate in candidates:
        if candidate != dataset_id and candidate in profile_dataset_ids:
            return candidate
    return None


def build_row(
    *,
    root: Path,
    split_path: Path,
    payload: dict[str, Any],
    profile: dict[str, Any],
    profile_dataset_ids: set[str],
) -> dict[str, Any] | None:
    pair_totals: Counter[str] = Counter()
    seed_rows = []
    row_id_violation_count = 0
    split_group_violation_count = 0

    for seed_profile in profile.get("seeds", []) or []:
        row_signature_overlaps = seed_profile.get("row_signature_overlaps") or {}
        duplicate_total = positive_overlap_count(row_signature_overlaps)
        if duplicate_total <= 0:
            continue
        row_id_overlaps = seed_profile.get("row_id_overlaps") or {}
        split_group_overlaps = seed_profile.get("split_group_overlaps") or {}
        row_id_total = positive_overlap_count(row_id_overlaps)
        split_group_total = positive_overlap_count(split_group_overlaps)
        row_id_violation_count += int(row_id_total > 0)
        split_group_violation_count += int(
            bool(profile.get("split_group_col")) and split_group_total > 0
        )
        for pair in PAIR_KEYS:
            pair_totals[pair] += int(row_signature_overlaps.get(pair) or 0)
        seed_rows.append(
            {
                "seed": int(seed_profile.get("seed")),
                "duplicate_signature_pair_overlaps": duplicate_total,
                "row_signature_overlaps": {
                    pair: int(row_signature_overlaps.get(pair) or 0)
                    for pair in PAIR_KEYS
                },
                "row_id_overlaps": {
                    pair: int(row_id_overlaps.get(pair) or 0) for pair in PAIR_KEYS
                },
                "split_group_overlaps": {
                    pair: int(split_group_overlaps.get(pair) or 0)
                    for pair in PAIR_KEYS
                },
            }
        )

    if not seed_rows:
        return None

    total = sum(pair_totals.values())
    dataset_id = str(profile.get("dataset_id"))
    dedup_variant = paired_dedup_variant(dataset_id, profile_dataset_ids)
    return {
        "dataset_id": dataset_id,
        "report_id": report_id_from_split_path(split_path),
        "report_dir": rel(split_path.parent, root),
        "split_profile_path": rel(split_path, root),
        "config_path": str(payload.get("config_path")),
        "experiment_id": payload.get("experiment_id"),
        "target": profile.get("target"),
        "primary_group": profile.get("primary_group"),
        "split_strategy": profile.get("split_strategy"),
        "split_group_col": profile.get("split_group_col"),
        "rows_after_target_drop": profile.get("rows_after_target_drop"),
        "duplicate_seed_profiles": len(seed_rows),
        "total_duplicate_signature_pair_overlaps": int(total),
        "max_seed_duplicate_signature_pair_overlaps": max(
            row["duplicate_signature_pair_overlaps"] for row in seed_rows
        ),
        "pair_totals": {pair: int(pair_totals[pair]) for pair in PAIR_KEYS},
        "row_id_overlap_violation_seed_profiles": row_id_violation_count,
        "split_group_overlap_violation_seed_profiles": split_group_violation_count,
        "hard_split_leakage_status": (
            "no_row_id_or_split_group_overlap"
            if row_id_violation_count == 0 and split_group_violation_count == 0
            else "inspect_row_id_or_split_group_overlap"
        ),
        "paired_dedup_variant_available": dedup_variant is not None,
        "paired_dedup_variant_dataset_id": dedup_variant,
        "allowed_interpretation": ALLOWED_INTERPRETATION,
        "status": "needs_duplicate_aware_sensitivity",
        "severity": severity_for(int(total)),
        "recommended_next_actions": NEXT_ACTIONS,
        "claim_boundaries": CLAIM_BOUNDARIES,
        "seed_profiles": sorted(seed_rows, key=lambda row: row["seed"]),
    }


def build_payload(root: Path) -> dict[str, Any]:
    rows = []
    malformed_profiles = []
    for split_path in sorted((root / "experiments/regression/reports").glob("**/split_profile.json")):
        try:
            payload = read_json(split_path)
        except json.JSONDecodeError as exc:
            malformed_profiles.append(
                {"path": rel(split_path, root), "error": f"{type(exc).__name__}: {exc}"}
            )
            continue
        profiles = payload.get("profiles", []) or []
        profile_dataset_ids = {
            str(profile.get("dataset_id"))
            for profile in profiles
            if isinstance(profile, dict) and profile.get("dataset_id") is not None
        }
        for profile in profiles:
            if not isinstance(profile, dict):
                malformed_profiles.append(
                    {"path": rel(split_path, root), "error": "profile entry is not an object"}
                )
                continue
            row = build_row(
                root=root,
                split_path=split_path,
                payload=payload,
                profile=profile,
                profile_dataset_ids=profile_dataset_ids,
            )
            if row:
                rows.append(row)

    severity_rank = {"high": 3, "medium": 2, "low": 1}
    rows.sort(
        key=lambda row: (
            -severity_rank[row["severity"]],
            -row["total_duplicate_signature_pair_overlaps"],
            row["dataset_id"],
        )
    )
    total_pair_overlaps = sum(row["total_duplicate_signature_pair_overlaps"] for row in rows)
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "experiments/regression/reports/**/split_profile.json",
        "summary": {
            "affected_dataset_count": len(rows),
            "affected_seed_profile_count": sum(row["duplicate_seed_profiles"] for row in rows),
            "total_duplicate_signature_pair_overlaps": int(total_pair_overlaps),
            "row_id_overlap_violation_seed_profiles": sum(
                row["row_id_overlap_violation_seed_profiles"] for row in rows
            ),
            "split_group_overlap_violation_seed_profiles": sum(
                row["split_group_overlap_violation_seed_profiles"] for row in rows
            ),
            "malformed_split_profile_count": len(malformed_profiles),
        },
        "methodology_sanity_audit_path": (
            "experiments/regression/reports/methodology_sanity_audit_20260627/"
            "sanity_audit.json"
        ),
        "claim_boundaries": CLAIM_BOUNDARIES,
        "allowed_interpretation": ALLOWED_INTERPRETATION,
        "recommended_next_actions": NEXT_ACTIONS,
        "malformed_profiles": malformed_profiles,
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Duplicate Split Caveat Backlog",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Source: `{payload['source']}`",
        f"- Affected datasets: {summary['affected_dataset_count']}",
        f"- Affected seed profiles: {summary['affected_seed_profile_count']}",
        f"- Duplicate-signature pair overlaps: {summary['total_duplicate_signature_pair_overlaps']}",
        f"- Row-id overlap violation seed profiles: {summary['row_id_overlap_violation_seed_profiles']}",
        f"- Split-group overlap violation seed profiles: {summary['split_group_overlap_violation_seed_profiles']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    for item in payload["claim_boundaries"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Backlog Rows", ""])
    if not payload["rows"]:
        lines.append("No duplicate-content split caveats are currently open.")
    else:
        lines.extend(
            [
                "| Dataset | Severity | Seed profiles | Pair overlaps | Dedup variant | Pair totals | Status |",
                "| --- | --- | ---: | ---: | --- | --- | --- |",
            ]
        )
        for row in payload["rows"]:
            pair_totals = ", ".join(
                f"{pair}={row['pair_totals'][pair]}" for pair in PAIR_KEYS
            )
            dedup_variant = row["paired_dedup_variant_dataset_id"] or "none recorded"
            lines.append(
                "| "
                f"`{row['dataset_id']}` | "
                f"{row['severity']} | "
                f"{row['duplicate_seed_profiles']} | "
                f"{row['total_duplicate_signature_pair_overlaps']} | "
                f"`{dedup_variant}` | "
                f"`{pair_totals}` | "
                f"{row['status']} |"
            )
    lines.extend(["", "## Recommended Next Actions", ""])
    for item in payload["recommended_next_actions"]:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = root / out_path
    payload = build_payload(root)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "out": rel(out_path, root),
                **payload["summary"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
