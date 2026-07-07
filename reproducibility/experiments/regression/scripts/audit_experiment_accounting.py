"""Audit regression experiment row accounting across ledger and manuscript scopes."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts.audit_cross_run_integrity import (
    canonical_ledger_rows,
    load_jsonl_rows,
)


SCHEMA = "cpfi_regression_experiment_accounting_audit_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = REPORT_DIR / "experiment_accounting_audit.json"
CLAIM_BOUNDARIES = [
    "This audit is experiment-row accounting and scope reconciliation, not a new model-performance result.",
    "Raw ledger rows include resume skips, superseded rows, invalidated runs, aborted runs, smoke runs, and diagnostics unless a narrower scope says otherwise.",
    "Canonical rows deduplicate by run_id and semantic model/method keys; they are not automatically manuscript-eligible rows.",
    "Cross-run represented completed rows are the methodology-audited publication workbench surface, not the full raw ledger universe.",
    "Manuscript selected rows and Venn-Abers grid-reference rows are narrower evidence surfaces with separate claim boundaries.",
]


SOURCE_PATHS = {
    "cross_run_integrity": REPORT_DIR / "cross_run_integrity_audit.json",
    "publication_methodology": REPORT_DIR / "publication_methodology_audit.json",
    "selection_multiplicity": Path(
        "experiments/regression/manuscript/selection_multiplicity_protocol.json"
    ),
    "bounded_support_posthandling": Path(
        "experiments/regression/manuscript/bounded_support_posthandling_validation.json"
    ),
    "venn_abers_grid_expansion": REPORT_DIR / "venn_abers_grid_expansion_plan.json",
    "venn_abers_grid_ivapd": REPORT_DIR
    / "venn_abers_grid_ivapd_validation_protocol.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def read_json_if_present(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def ledger_surface(path: Path, root: Path) -> str:
    rel_path = rel(path, root)
    if "/invalidated/" in rel_path:
        return "invalidated"
    if "_aborted_" in rel_path or "/aborted_" in rel_path:
        return "aborted"
    if "venn_abers_grid_expansion" in rel_path:
        return "venn_abers_grid_worker"
    if rel_path.startswith("experiments/regression/results/_"):
        return "derived_state"
    return "regular_results"


def counter_to_sorted_dict(counter: Counter[str]) -> dict[str, int]:
    return {str(key): int(value) for key, value in sorted(counter.items())}


def add_status_counts(
    target: dict[str, Any],
    rows: list[dict[str, Any]],
    prefix: str,
) -> None:
    status_counts = Counter(str(row.get("status", "missing")) for row in rows)
    target[f"{prefix}_status_counts"] = counter_to_sorted_dict(status_counts)
    for status, count in status_counts.items():
        target[f"{prefix}_{status}_rows"] = int(count)


def scan_ledgers(root: Path) -> dict[str, Any]:
    ledger_paths = sorted(
        (root / "experiments/regression/results").glob("**/ledger.jsonl")
    )
    totals: dict[str, Any] = {
        "ledger_file_count": 0,
        "raw_row_count": 0,
        "canonical_row_count": 0,
        "raw_completed_row_count": 0,
        "canonical_completed_row_count": 0,
        "canonical_failed_row_count": 0,
        "canonicalization_removed_row_count": 0,
        "raw_status_counts": {},
        "canonical_status_counts": {},
    }
    surface_counters: dict[str, Counter[str]] = defaultdict(Counter)
    raw_status_total: Counter[str] = Counter()
    canonical_status_total: Counter[str] = Counter()
    dataset_completed_counts: Counter[str] = Counter()
    ledger_rows: list[dict[str, Any]] = []

    for ledger_path in ledger_paths:
        rows = load_jsonl_rows(ledger_path)
        canonical = canonical_ledger_rows(rows)
        raw_status = Counter(str(row.get("status", "missing")) for row in rows)
        canonical_status = Counter(
            str(row.get("status", "missing")) for row in canonical
        )
        surface = ledger_surface(ledger_path, root)
        surface_counter = surface_counters[surface]
        surface_counter["ledger_file_count"] += 1
        surface_counter["raw_row_count"] += len(rows)
        surface_counter["canonical_row_count"] += len(canonical)
        surface_counter["raw_completed_row_count"] += raw_status.get("completed", 0)
        surface_counter["canonical_completed_row_count"] += canonical_status.get(
            "completed", 0
        )
        surface_counter["canonical_failed_row_count"] += canonical_status.get(
            "failed", 0
        )
        for status, count in raw_status.items():
            surface_counter[f"raw_status:{status}"] += count
        for status, count in canonical_status.items():
            surface_counter[f"canonical_status:{status}"] += count
        raw_status_total.update(raw_status)
        canonical_status_total.update(canonical_status)
        for row in canonical:
            if str(row.get("status")) == "completed" and row.get("dataset_id"):
                dataset_completed_counts[str(row["dataset_id"])] += 1
        ledger_rows.append(
            {
                "path": rel(ledger_path, root),
                "surface": surface,
                "raw_row_count": len(rows),
                "canonical_row_count": len(canonical),
                "raw_status_counts": counter_to_sorted_dict(raw_status),
                "canonical_status_counts": counter_to_sorted_dict(canonical_status),
                "canonicalization_removed_row_count": len(rows) - len(canonical),
            }
        )

    totals["ledger_file_count"] = len(ledger_paths)
    totals["raw_row_count"] = sum(row["raw_row_count"] for row in ledger_rows)
    totals["canonical_row_count"] = sum(
        row["canonical_row_count"] for row in ledger_rows
    )
    totals["raw_completed_row_count"] = raw_status_total.get("completed", 0)
    totals["canonical_completed_row_count"] = canonical_status_total.get("completed", 0)
    totals["canonical_failed_row_count"] = canonical_status_total.get("failed", 0)
    totals["canonicalization_removed_row_count"] = (
        totals["raw_row_count"] - totals["canonical_row_count"]
    )
    totals["raw_status_counts"] = counter_to_sorted_dict(raw_status_total)
    totals["canonical_status_counts"] = counter_to_sorted_dict(canonical_status_total)

    surface_rows = []
    for surface, counter in sorted(surface_counters.items()):
        raw_status = {
            key.split(":", 1)[1]: value
            for key, value in counter.items()
            if key.startswith("raw_status:")
        }
        canonical_status = {
            key.split(":", 1)[1]: value
            for key, value in counter.items()
            if key.startswith("canonical_status:")
        }
        surface_rows.append(
            {
                "surface": surface,
                "ledger_file_count": int(counter["ledger_file_count"]),
                "raw_row_count": int(counter["raw_row_count"]),
                "canonical_row_count": int(counter["canonical_row_count"]),
                "raw_completed_row_count": int(counter["raw_completed_row_count"]),
                "canonical_completed_row_count": int(
                    counter["canonical_completed_row_count"]
                ),
                "canonical_failed_row_count": int(
                    counter["canonical_failed_row_count"]
                ),
                "canonicalization_removed_row_count": int(
                    counter["raw_row_count"] - counter["canonical_row_count"]
                ),
                "raw_status_counts": counter_to_sorted_dict(Counter(raw_status)),
                "canonical_status_counts": counter_to_sorted_dict(
                    Counter(canonical_status)
                ),
            }
        )

    return {
        "summary": totals,
        "surface_rows": surface_rows,
        "ledger_rows": ledger_rows,
        "top_datasets_by_canonical_completed_rows": [
            {"dataset_id": dataset_id, "canonical_completed_row_count": int(count)}
            for dataset_id, count in dataset_completed_counts.most_common(20)
        ],
    }


def source_counts(root: Path) -> dict[str, Any]:
    sources = {
        name: read_json_if_present(root / path) for name, path in SOURCE_PATHS.items()
    }
    cross_summary = sources["cross_run_integrity"].get("summary") or {}
    cross_rows = sources["cross_run_integrity"].get("rows") or []
    publication_summary = sources["publication_methodology"].get("summary") or {}
    selection_summary = sources["selection_multiplicity"].get("summary") or {}
    bounded_summary = sources["bounded_support_posthandling"].get("summary") or {}
    venn_plan_summary = sources["venn_abers_grid_expansion"].get("summary") or {}
    venn_ivapd_summary = sources["venn_abers_grid_ivapd"].get("summary") or {}
    return {
        "cross_run_completed_rows": safe_int(cross_summary.get("total_completed_rows")),
        "cross_run_reports_scanned": safe_int(cross_summary.get("reports_scanned")),
        "candidate_duplicate_sensitivity_completed_rows": sum(
            safe_int(row.get("ledger_rows"))
            for row in cross_rows
            if isinstance(row, dict)
            and str(row.get("report_name") or "").startswith(
                "main_result_candidate_duplicate_sensitivity_"
            )
        ),
        "publication_completed_rows": safe_int(
            publication_summary.get("total_completed_rows")
        ),
        "selection_completed_rows_scanned": safe_int(
            selection_summary.get("completed_ledger_rows_scanned")
        ),
        "bounded_support_selected_completed_rows": safe_int(
            bounded_summary.get("completed_ledger_rows")
        ),
        "bounded_support_state_resumed_records": safe_int(
            bounded_summary.get("state_resumed_records")
        ),
        "bounded_support_state_written_records": safe_int(
            bounded_summary.get("state_written_records")
        ),
        "bounded_support_reconstruction_failures": safe_int(
            bounded_summary.get("reconstruction_failures")
        ),
        "venn_grid_total_rows_available": safe_int(
            venn_plan_summary.get("total_test_rows_available")
        ),
        "venn_grid_rows_completed": safe_int(
            venn_plan_summary.get("total_grid_rows_completed")
        ),
        "venn_grid_rows_pending": safe_int(
            venn_plan_summary.get("total_grid_rows_pending")
        ),
        "venn_grid_worker_rows_completed": safe_int(
            venn_plan_summary.get("worker_grid_rows_completed")
        ),
        "venn_grid_worker_rows_failed": safe_int(
            venn_plan_summary.get("worker_grid_rows_failed")
        ),
        "venn_grid_completion_fraction": float(
            venn_plan_summary.get("grid_completion_fraction") or 0.0
        ),
        "venn_ivapd_grid_reference_rows_scored": safe_int(
            venn_ivapd_summary.get("total_grid_reference_rows_scored")
        ),
        "venn_ivapd_rows_scored": safe_int(
            venn_ivapd_summary.get("total_ivapd_rows_scored")
        ),
        "source_paths": {name: str(path) for name, path in SOURCE_PATHS.items()},
    }


def build_checks(
    ledger_summary: dict[str, Any],
    surfaces: list[dict[str, Any]],
    sources: dict[str, Any],
) -> list[dict[str, Any]]:
    surface_by_name = {row["surface"]: row for row in surfaces}
    regular_completed = safe_int(
        surface_by_name.get("regular_results", {}).get("canonical_completed_row_count")
    )
    cross_completed = safe_int(sources.get("cross_run_completed_rows"))
    publication_completed = safe_int(sources.get("publication_completed_rows"))
    selection_completed = safe_int(sources.get("selection_completed_rows_scanned"))
    candidate_duplicate_sensitivity_completed = safe_int(
        sources.get("candidate_duplicate_sensitivity_completed_rows")
    )
    cross_publication_selection_aligned = publication_completed == selection_completed and (
        cross_completed == publication_completed
        or cross_completed
        == publication_completed + candidate_duplicate_sensitivity_completed
    )
    checks = [
        {
            "check_id": "raw_rows_cover_canonical_rows",
            "status": (
                "pass"
                if safe_int(ledger_summary.get("raw_row_count"))
                >= safe_int(ledger_summary.get("canonical_row_count"))
                else "fail"
            ),
            "observed": {
                "raw_row_count": ledger_summary.get("raw_row_count"),
                "canonical_row_count": ledger_summary.get("canonical_row_count"),
            },
        },
        {
            "check_id": "canonical_rows_cover_completed_rows",
            "status": (
                "pass"
                if safe_int(ledger_summary.get("canonical_row_count"))
                >= safe_int(ledger_summary.get("canonical_completed_row_count"))
                else "fail"
            ),
            "observed": {
                "canonical_row_count": ledger_summary.get("canonical_row_count"),
                "canonical_completed_row_count": ledger_summary.get(
                    "canonical_completed_row_count"
                ),
            },
        },
        {
            "check_id": "cross_publication_selection_completed_rows_align",
            "status": "pass" if cross_publication_selection_aligned else "fail",
            "observed": {
                "cross_run_completed_rows": cross_completed,
                "publication_completed_rows": publication_completed,
                "selection_completed_rows_scanned": selection_completed,
                "candidate_duplicate_sensitivity_completed_rows": (
                    candidate_duplicate_sensitivity_completed
                ),
                "cross_minus_publication_completed_rows": (
                    cross_completed - publication_completed
                ),
                "candidate_duplicate_sensitivity_scope": (
                    "included_in_publication_selection_scope"
                    if cross_completed == publication_completed
                    else "diagnostic_only_outside_publication_selection_scope"
                ),
            },
        },
        {
            "check_id": "regular_ledgers_cover_cross_run_scope",
            "status": "pass" if regular_completed >= cross_completed else "fail",
            "observed": {
                "regular_canonical_completed_rows": regular_completed,
                "cross_run_completed_rows": cross_completed,
            },
        },
        {
            "check_id": "bounded_support_scope_is_subset_of_cross_run",
            "status": (
                "pass"
                if safe_int(sources.get("bounded_support_selected_completed_rows"))
                <= cross_completed
                else "fail"
            ),
            "observed": {
                "bounded_support_selected_completed_rows": sources.get(
                    "bounded_support_selected_completed_rows"
                ),
                "cross_run_completed_rows": cross_completed,
            },
        },
        {
            "check_id": "bounded_support_state_matches_selected_rows",
            "status": (
                "pass"
                if safe_int(sources.get("bounded_support_selected_completed_rows"))
                == (
                    safe_int(sources.get("bounded_support_state_resumed_records"))
                    + safe_int(sources.get("bounded_support_state_written_records"))
                )
                and safe_int(sources.get("bounded_support_reconstruction_failures"))
                == 0
                else "fail"
            ),
            "observed": {
                "bounded_support_selected_completed_rows": sources.get(
                    "bounded_support_selected_completed_rows"
                ),
                "bounded_support_state_resumed_records": sources.get(
                    "bounded_support_state_resumed_records"
                ),
                "bounded_support_state_written_records": sources.get(
                    "bounded_support_state_written_records"
                ),
                "bounded_support_state_total_records": (
                    safe_int(sources.get("bounded_support_state_resumed_records"))
                    + safe_int(sources.get("bounded_support_state_written_records"))
                ),
                "bounded_support_reconstruction_failures": sources.get(
                    "bounded_support_reconstruction_failures"
                ),
            },
        },
        {
            "check_id": "venn_grid_reference_rows_complete",
            "status": (
                "pass"
                if safe_int(sources.get("venn_grid_rows_completed"))
                == safe_int(sources.get("venn_grid_total_rows_available"))
                and safe_int(sources.get("venn_grid_rows_pending")) == 0
                else "fail"
            ),
            "observed": {
                "venn_grid_rows_completed": sources.get("venn_grid_rows_completed"),
                "venn_grid_total_rows_available": sources.get(
                    "venn_grid_total_rows_available"
                ),
                "venn_grid_rows_pending": sources.get("venn_grid_rows_pending"),
            },
        },
        {
            "check_id": "venn_ivapd_grid_reference_matches_expansion",
            "status": (
                "pass"
                if safe_int(sources.get("venn_ivapd_grid_reference_rows_scored"))
                == safe_int(sources.get("venn_grid_rows_completed"))
                else "fail"
            ),
            "observed": {
                "venn_ivapd_grid_reference_rows_scored": sources.get(
                    "venn_ivapd_grid_reference_rows_scored"
                ),
                "venn_grid_rows_completed": sources.get("venn_grid_rows_completed"),
            },
        },
    ]
    return checks


def build_audit(root: Path) -> dict[str, Any]:
    ledger = scan_ledgers(root)
    sources = source_counts(root)
    checks = build_checks(ledger["summary"], ledger["surface_rows"], sources)
    failed_checks = [check for check in checks if check["status"] != "pass"]
    surface_by_name = {row["surface"]: row for row in ledger["surface_rows"]}
    regular_completed = safe_int(
        surface_by_name.get("regular_results", {}).get("canonical_completed_row_count")
    )
    cross_completed = safe_int(sources.get("cross_run_completed_rows"))
    summary = {
        "overall_status": (
            "experiment_accounting_pass"
            if not failed_checks
            else "experiment_accounting_fail"
        ),
        "failed_check_count": len(failed_checks),
        "ledger_file_count": ledger["summary"]["ledger_file_count"],
        "raw_ledger_row_count": ledger["summary"]["raw_row_count"],
        "canonical_ledger_row_count": ledger["summary"]["canonical_row_count"],
        "raw_completed_row_count": ledger["summary"]["raw_completed_row_count"],
        "canonical_completed_row_count": ledger["summary"][
            "canonical_completed_row_count"
        ],
        "canonical_failed_row_count": ledger["summary"]["canonical_failed_row_count"],
        "canonicalization_removed_row_count": ledger["summary"][
            "canonicalization_removed_row_count"
        ],
        "regular_canonical_completed_row_count": regular_completed,
        "cross_run_completed_rows": cross_completed,
        "regular_completed_minus_cross_run_completed_rows": (
            regular_completed - cross_completed
        ),
        "invalidated_canonical_completed_row_count": safe_int(
            surface_by_name.get("invalidated", {}).get("canonical_completed_row_count")
        ),
        "aborted_canonical_completed_row_count": safe_int(
            surface_by_name.get("aborted", {}).get("canonical_completed_row_count")
        ),
        "publication_completed_rows": sources["publication_completed_rows"],
        "selection_completed_rows_scanned": sources["selection_completed_rows_scanned"],
        "candidate_duplicate_sensitivity_completed_rows": sources[
            "candidate_duplicate_sensitivity_completed_rows"
        ],
        "bounded_support_selected_completed_rows": sources[
            "bounded_support_selected_completed_rows"
        ],
        "bounded_support_state_resumed_records": sources[
            "bounded_support_state_resumed_records"
        ],
        "bounded_support_state_written_records": sources[
            "bounded_support_state_written_records"
        ],
        "venn_grid_rows_completed": sources["venn_grid_rows_completed"],
        "venn_grid_rows_pending": sources["venn_grid_rows_pending"],
        "venn_grid_completion_fraction": sources["venn_grid_completion_fraction"],
        "venn_grid_worker_rows_completed": sources["venn_grid_worker_rows_completed"],
        "venn_grid_worker_rows_failed": sources["venn_grid_worker_rows_failed"],
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": summary,
        "checks": checks,
        "failed_checks": failed_checks,
        "ledger_accounting": ledger["summary"],
        "ledger_surfaces": ledger["surface_rows"],
        "source_accounting": sources,
        "top_datasets_by_canonical_completed_rows": ledger[
            "top_datasets_by_canonical_completed_rows"
        ],
        "ledger_files": ledger["ledger_rows"],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Experiment Accounting Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Failed checks: {summary['failed_check_count']}",
        f"- Ledger files: {summary['ledger_file_count']}",
        f"- Raw ledger rows: {summary['raw_ledger_row_count']}",
        f"- Canonical ledger rows: {summary['canonical_ledger_row_count']}",
        f"- Raw completed rows: {summary['raw_completed_row_count']}",
        f"- Canonical completed rows: {summary['canonical_completed_row_count']}",
        f"- Cross-run represented completed rows: {summary['cross_run_completed_rows']}",
        f"- Publication completed rows: {summary['publication_completed_rows']}",
        f"- Selection protocol completed rows scanned: {summary['selection_completed_rows_scanned']}",
        f"- Manuscript bounded-support selected completed rows: {summary['bounded_support_selected_completed_rows']}",
        f"- Venn-Abers grid rows completed/pending: {summary['venn_grid_rows_completed']} / {summary['venn_grid_rows_pending']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    for boundary in payload["claim_boundaries"]:
        lines.append(f"- {boundary}")
    lines.extend(["", "## Ledger Surfaces", ""])
    for row in payload["ledger_surfaces"]:
        lines.append(
            "- "
            f"`{row['surface']}`: {row['ledger_file_count']} ledger files, "
            f"{row['raw_row_count']} raw rows, "
            f"{row['canonical_row_count']} canonical rows, "
            f"{row['canonical_completed_row_count']} canonical completed rows"
        )
    lines.extend(["", "## Checks", ""])
    for check in payload["checks"]:
        lines.append(
            f"- `{check['check_id']}`: `{check['status']}` "
            f"observed `{check['observed']}`"
        )
    lines.extend(["", "## Top Datasets By Canonical Completed Rows", ""])
    for row in payload["top_datasets_by_canonical_completed_rows"][:10]:
        lines.append(f"- `{row['dataset_id']}`: {row['canonical_completed_row_count']}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = root / args.out
    payload = build_audit(root)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(json.dumps(payload["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
