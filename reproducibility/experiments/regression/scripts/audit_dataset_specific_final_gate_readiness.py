"""Audit dataset-specific final-result readiness for manuscript gates.

This audit decomposes the `dataset_specific_final_gates` blocker. It does not
promote any dataset or conformal method to a main result; it records why the
current manifested bundles remain robustness/caveat evidence instead of
dataset-specific final-result evidence.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_dataset_specific_final_gate_audit_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = REPORT_DIR / "dataset_specific_final_gate_audit.json"
BUNDLE_INDEX = Path("experiments/regression/catalogs/manuscript_bundle_index.json")
BUNDLE_ELIGIBILITY = Path("experiments/regression/manuscript/bundle_eligibility_matrix.json")
MANIFEST_COMPLETENESS = REPORT_DIR / "manuscript_manifest_completeness_audit.json"
BOUNDED_SUPPORT_DATASET_AUDIT = Path(
    "experiments/regression/manuscript/bounded_support_dataset_audit.json"
)
FAIRNESS_POPULATION_READINESS = REPORT_DIR / "fairness_population_readiness_audit.json"
FINAL_SELECTION = REPORT_DIR / "final_selection_claim_boundary_audit.json"
PAPER_READINESS = Path("experiments/regression/manuscript/paper_readiness_map.json")


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


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {
        str(row[key]): row
        for row in rows
        if isinstance(row, dict) and row.get(key) is not None
    }


def rows_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if isinstance(row, dict) and row.get(key) is not None:
            grouped[str(row[key])].append(row)
    return dict(grouped)


def bundle_rows(bundle_index: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in bundle_index.get("bundles", []) or []
        if isinstance(row, dict) and row.get("bundle_id")
    ]


def eligibility_rows(bundle_eligibility: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in bundle_eligibility.get("rows", []) or []
        if isinstance(row, dict) and row.get("bundle_id")
    ]


def audit_bundle_rows(
    bundle_index: dict[str, Any],
    bundle_eligibility: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return the full manuscript eligibility bundle universe for final-gate audit."""

    indexed_rows = bundle_rows(bundle_index)
    indexed_by_bundle = by_key(indexed_rows, "bundle_id")
    eligible_rows = eligibility_rows(bundle_eligibility)
    if not eligible_rows:
        return [
            {**row, "bundle_index_present": True, "eligibility_matrix_present": False}
            for row in indexed_rows
        ]

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for eligibility in eligible_rows:
        bundle_id = str(eligibility["bundle_id"])
        index_row = indexed_by_bundle.get(bundle_id, {})
        merged = {
            **index_row,
            **eligibility,
            "bundle_index_present": bool(index_row),
            "eligibility_matrix_present": True,
        }
        rows.append(merged)
        seen.add(bundle_id)

    for index_row in indexed_rows:
        bundle_id = str(index_row["bundle_id"])
        if bundle_id not in seen:
            rows.append(
                {
                    **index_row,
                    "bundle_index_present": True,
                    "eligibility_matrix_present": False,
                }
            )
    return rows


def main_surface(row: dict[str, Any]) -> dict[str, Any]:
    return ((row.get("surface_eligibility") or {}).get("main_results_table") or {})


def is_main_result_candidate_diagnostic(row: dict[str, Any]) -> bool:
    role = str(row.get("evidence_role") or "")
    table = str(row.get("paper_table_candidate") or "")
    return (
        role == "main_result_candidate_diagnostic"
        or table == "main_results_table_blocked_diagnostic_only"
    )


def manifest_present(row: dict[str, Any]) -> bool:
    if "manifest_present" in row:
        return bool(row.get("manifest_present"))
    return bool(row.get("manifest_path"))


def bundle_blockers(
    bundle: dict[str, Any],
    *,
    eligibility: dict[str, Any],
    manifest: dict[str, Any] | None,
    bounded: dict[str, Any] | None,
    fairness: dict[str, Any] | None,
    final_selection_status: str | None,
) -> list[str]:
    blockers: list[str] = []
    if bundle.get("evidence_role") == "main_result":
        pass
    elif is_main_result_candidate_diagnostic(bundle):
        blockers.append("main_result_candidate_diagnostic_only")
    else:
        blockers.append("not_indexed_as_main_result_bundle")
    if "caveat" in str(bundle.get("status", "")).lower():
        blockers.append("bundle_status_contains_caveats")
    if bundle.get("promotion_blockers"):
        blockers.append("bundle_promotion_blockers_present")
    if not manifest_present(eligibility):
        blockers.append("manifest_missing")
    if manifest and manifest.get("status") != "pass":
        blockers.append("manifest_completeness_not_pass")
    selection = (manifest or {}).get("selection_multiplicity_evidence") or {}
    if selection and selection.get("status") != "pass":
        blockers.append("manifest_selection_multiplicity_not_pass")
    if main_surface(eligibility).get("eligible") is not True:
        blockers.append("main_results_surface_blocked")
    if bounded and bounded.get("can_support_bounded_support_validity") is not True:
        blockers.append("bounded_support_validity_not_supported")
    if fairness and fairness.get("fairness_population_claim_status") != "ready":
        blockers.append("fairness_population_claim_not_ready")
    if final_selection_status == "blocked":
        blockers.append("final_selection_claim_blocked")
    return list(dict.fromkeys(blockers))


def dataset_rows(
    bundles: list[dict[str, Any]],
    bundle_readiness_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped = rows_by_key(bundle_readiness_rows, "dataset_id")
    rows = []
    for dataset_id in sorted(grouped):
        dataset_bundles = grouped[dataset_id]
        blocker_counts = Counter(
            blocker for row in dataset_bundles for blocker in row["blocking_reasons"]
        )
        main_ready = [
            row for row in dataset_bundles if row["main_result_promotion_ready"]
        ]
        rows.append(
            {
                "dataset_id": dataset_id,
                "bundle_count": len(dataset_bundles),
                "bundle_ids": [row["bundle_id"] for row in dataset_bundles],
                "target_ids": sorted(
                    {
                        str(bundle.get("target"))
                        for bundle in bundles
                        if bundle.get("dataset_id") == dataset_id and bundle.get("target")
                    }
                ),
                "main_result_promotion_ready_bundle_count": len(main_ready),
                "has_main_result_ready_bundle": bool(main_ready),
                "robustness_bundle_count": sum(
                    row["evidence_role"] == "robustness" for row in dataset_bundles
                ),
                "blocking_reason_counts": dict(sorted(blocker_counts.items())),
                "recommended_next_action": (
                    "promote_ready_main_result_bundle"
                    if main_ready
                    else "create_or_refresh_caveat_free_main_result_bundle"
                ),
                "claim_boundary": (
                    "Dataset can support descriptive or robustness extraction only "
                    "until a caveat-free main-result bundle and final-selection "
                    "claim boundary pass."
                ),
            }
        )
    return rows


def build_payload(root: Path) -> dict[str, Any]:
    paths = {
        "manuscript_bundle_index": root / BUNDLE_INDEX,
        "bundle_eligibility_matrix": root / BUNDLE_ELIGIBILITY,
        "manuscript_manifest_completeness_audit": root / MANIFEST_COMPLETENESS,
        "bounded_support_dataset_audit": root / BOUNDED_SUPPORT_DATASET_AUDIT,
        "fairness_population_readiness_audit": root / FAIRNESS_POPULATION_READINESS,
        "final_selection_claim_boundary_audit": root / FINAL_SELECTION,
        "paper_readiness_map": root / PAPER_READINESS,
    }
    bundle_index = read_json(paths["manuscript_bundle_index"])
    bundle_eligibility = read_json(paths["bundle_eligibility_matrix"])
    manifest_completeness = read_json(paths["manuscript_manifest_completeness_audit"])
    bounded_support = read_json(paths["bounded_support_dataset_audit"])
    fairness = read_json(paths["fairness_population_readiness_audit"])
    final_selection = read_json(paths["final_selection_claim_boundary_audit"])
    paper_readiness = read_json(paths["paper_readiness_map"])

    bundles = audit_bundle_rows(bundle_index, bundle_eligibility)
    eligibility_by_bundle = by_key(bundle_eligibility.get("rows", []) or [], "bundle_id")
    manifest_by_path = by_key(manifest_completeness.get("rows", []) or [], "path")
    bounded_by_bundle = by_key(bounded_support.get("rows", []) or [], "bundle_id")
    fairness_by_bundle = by_key(fairness.get("rows", []) or [], "bundle_id")
    final_summary = final_selection.get("summary") or {}
    final_selection_status = final_summary.get("claim_status")

    bundle_readiness_rows = []
    for bundle in bundles:
        bundle_id = str(bundle["bundle_id"])
        eligibility = eligibility_by_bundle.get(bundle_id, bundle)
        manifest = manifest_by_path.get(str(bundle.get("manifest_path") or ""))
        bounded = bounded_by_bundle.get(bundle_id)
        fairness_row = fairness_by_bundle.get(bundle_id)
        blockers = bundle_blockers(
            bundle,
            eligibility=eligibility,
            manifest=manifest,
            bounded=bounded,
            fairness=fairness_row,
            final_selection_status=str(final_selection_status or ""),
        )
        bundle_readiness_rows.append(
            {
                "bundle_id": bundle_id,
                "dataset_id": str(bundle.get("dataset_id") or ""),
                "target": bundle.get("target"),
                "target_transform": bundle.get("target_transform"),
                "diagnostic_group": bundle.get("diagnostic_group"),
                "evidence_role": bundle.get("evidence_role"),
                "status": bundle.get("status"),
                "paper_table_candidate": bundle.get("paper_table_candidate"),
                "manifest_path": bundle.get("manifest_path"),
                "bundle_index_present": bool(bundle.get("bundle_index_present")),
                "eligibility_matrix_present": bool(
                    bundle.get("eligibility_matrix_present")
                ),
                "linked_claim_ids": list(bundle.get("linked_claim_ids") or []),
                "requires_caveat_label": bool(bundle.get("requires_caveat_label")),
                "manifest_present": manifest_present(eligibility),
                "manifest_completeness_status": (manifest or {}).get("status"),
                "selection_multiplicity_status": (
                    (manifest or {}).get("selection_multiplicity_evidence") or {}
                ).get("status"),
                "main_surface_status": main_surface(eligibility).get("status"),
                "main_surface_eligible": main_surface(eligibility).get("eligible"),
                "bounded_support_claim_status": (bounded or {}).get("claim_status"),
                "can_support_bounded_support_validity": (bounded or {}).get(
                    "can_support_bounded_support_validity"
                ),
                "fairness_population_claim_status": (fairness_row or {}).get(
                    "fairness_population_claim_status"
                ),
                "final_selection_claim_status": final_selection_status,
                "promotion_blockers": list(bundle.get("promotion_blockers") or []),
                "blocking_reasons": blockers,
                "main_result_promotion_ready": not blockers,
                "claim_boundary": (
                    "This row audits dataset-specific final-result readiness; "
                    "it does not promote a final dataset, model, or method."
                ),
            }
        )

    datasets = dataset_rows(bundles, bundle_readiness_rows)
    blocker_counts = Counter(
        blocker for row in bundle_readiness_rows for blocker in row["blocking_reasons"]
    )
    readiness_summary = paper_readiness.get("summary") or {}
    ready_rows = [row for row in bundle_readiness_rows if row["main_result_promotion_ready"]]
    status = (
        "dataset_specific_final_gate_ready"
        if ready_rows
        else "dataset_specific_final_gate_audit_completed_no_final_dataset_promotions"
    )
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {key: rel(path, root) for key, path in paths.items()},
        "summary": {
            "overall_status": status,
            "bundle_count": len(bundle_readiness_rows),
            "dataset_count": len(datasets),
            "main_result_ready_bundle_count": len(ready_rows),
            "main_result_ready_dataset_count": sum(
                row["has_main_result_ready_bundle"] for row in datasets
            ),
            "robustness_bundle_count": sum(
                row["evidence_role"] == "robustness" for row in bundle_readiness_rows
            ),
            "main_result_candidate_diagnostic_bundle_count": sum(
                is_main_result_candidate_diagnostic(row)
                for row in bundle_readiness_rows
            ),
            "eligibility_matrix_bundle_count": sum(
                row["eligibility_matrix_present"] for row in bundle_readiness_rows
            ),
            "bundle_index_present_count": sum(
                row["bundle_index_present"] for row in bundle_readiness_rows
            ),
            "missing_bundle_index_count": sum(
                not row["bundle_index_present"] for row in bundle_readiness_rows
            ),
            "evidence_role_counts": dict(
                sorted(
                    Counter(
                        str(row.get("evidence_role") or "unknown")
                        for row in bundle_readiness_rows
                    ).items()
                )
            ),
            "paper_table_candidate_counts": dict(
                sorted(
                    Counter(
                        str(row.get("paper_table_candidate") or "unknown")
                        for row in bundle_readiness_rows
                    ).items()
                )
            ),
            "manifest_present_bundle_count": sum(
                row["manifest_present"] for row in bundle_readiness_rows
            ),
            "manifest_pass_bundle_count": sum(
                row["manifest_completeness_status"] == "pass"
                for row in bundle_readiness_rows
            ),
            "bounded_support_ready_bundle_count": sum(
                row["can_support_bounded_support_validity"] is True
                for row in bundle_readiness_rows
            ),
            "fairness_population_ready_bundle_count": sum(
                row["fairness_population_claim_status"] == "ready"
                for row in bundle_readiness_rows
            ),
            "final_selection_claim_status": final_selection_status,
            "paper_readiness_status": readiness_summary.get("overall_status"),
            "paper_blocked_gate_count": readiness_summary.get("blocked_gate_count"),
            "blocking_reason_counts": dict(sorted(blocker_counts.items())),
        },
        "claim_boundaries": [
            "No current bundle is promoted to a final main-result dataset bundle.",
            "Robustness-table eligibility is not dataset-specific final-result eligibility.",
            "Main-result candidate diagnostic bundles are audited for final-gate blockers but remain non-promotional while paper gates are blocked.",
            "CQR remains a diagnostic primary candidate, not a final paper winner.",
            "Bounded-support, fairness/population, production, and Venn-Abers validation claims remain outside this audit's promotion scope.",
        ],
        "dataset_rows": datasets,
        "bundle_rows": bundle_readiness_rows,
    }
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Dataset-Specific Final Gate Audit",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Datasets: {summary['dataset_count']}",
        f"- Bundles: {summary['bundle_count']}",
        f"- Main-result ready bundles: {summary['main_result_ready_bundle_count']}",
        f"- Main-result ready datasets: {summary['main_result_ready_dataset_count']}",
        f"- Robustness bundles: {summary['robustness_bundle_count']}",
        f"- Main-result candidate diagnostic bundles: {summary['main_result_candidate_diagnostic_bundle_count']}",
        f"- Manifest pass bundles: {summary['manifest_pass_bundle_count']}",
        f"- Final-selection claim status: `{summary['final_selection_claim_status']}`",
        f"- Paper blocked gates: {summary['paper_blocked_gate_count']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Dataset Rows",
            "",
            "| Dataset | Bundles | Ready bundles | Main blocker counts | Next action |",
            "| --- | ---: | ---: | --- | --- |",
        ]
    )
    for row in payload["dataset_rows"]:
        lines.append(
            "| "
            f"`{row['dataset_id']}` | "
            f"{row['bundle_count']} | "
            f"{row['main_result_promotion_ready_bundle_count']} | "
            f"`{row['blocking_reason_counts']}` | "
            f"`{row['recommended_next_action']}` |"
        )
    lines.extend(
        [
            "",
            "## Bundle Rows",
            "",
            "| Bundle | Dataset | Main ready | Blocking reasons |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for row in payload["bundle_rows"]:
        lines.append(
            "| "
            f"`{row['bundle_id']}` | "
            f"`{row['dataset_id']}` | "
            f"`{row['main_result_promotion_ready']}` | "
            f"`{row['blocking_reasons']}` |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = resolve(root, args.out)
    payload = build_payload(root)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(json.dumps({"out": rel(out_path, root), **payload["summary"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
