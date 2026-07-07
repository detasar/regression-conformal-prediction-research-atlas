"""Audit post-run closure artifacts for main-result candidate bundles."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts.build_method_selection_alpha_expansion_batch import (
    read_json,
    rel,
)
from experiments.regression.scripts.build_main_result_candidate_bundle_results import (
    canonical_rows,
)


SCHEMA = "cpfi_regression_main_result_candidate_post_run_closure_audit_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_PLAN = REPORT_DIR / "main_result_candidate_bundle_plan.json"
DEFAULT_RESULTS = REPORT_DIR / "main_result_candidate_bundle_results.json"
DEFAULT_OUT = REPORT_DIR / "main_result_candidate_post_run_closure_audit.json"
KG_CATALOG = Path("experiments/regression/catalogs/knowledge_graph.json")
CLAIM_REGISTER = Path("experiments/regression/catalogs/manuscript_claim_register.json")
BUNDLE_INDEX = Path("experiments/regression/catalogs/manuscript_bundle_index.json")
BUNDLE_ELIGIBILITY = Path("experiments/regression/manuscript/bundle_eligibility_matrix.json")
PAPER_READINESS = Path("experiments/regression/manuscript/paper_readiness_map.json")

CLAIM_BOUNDARIES = [
    "This audit checks post-run closure artifacts for executed candidate bundles; it does not promote a main result.",
    "Ledger, pilot-summary, and split-profile readiness are necessary but not sufficient for manuscript promotion.",
    "Feature-leakage, endpoint, manifest, claim-register, and bundle-index evidence must pass before any main-results table row is promoted.",
    "Duplicate-signature and sparse-group caveats are retained as claim-boundary evidence rather than hidden by the audit.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN), help="Candidate plan JSON.")
    parser.add_argument(
        "--results", default=str(DEFAULT_RESULTS), help="Candidate results JSON."
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def status_row(
    artifact_id: str,
    status: str,
    *,
    path: str | None = None,
    observed: dict[str, Any] | None = None,
    blocker: bool = False,
    caveat: bool = False,
    next_action: str,
) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "status": status,
        "path": path,
        "blocker": blocker,
        "caveat": caveat,
        "observed": observed or {},
        "next_action": next_action,
    }


def ledger_status(root: Path, row: dict[str, Any]) -> dict[str, Any]:
    path = resolve(root, str(row.get("ledger") or ""))
    expected = int(row.get("expected_atomic_run_count") or 0)
    raw_rows = []
    if path.exists():
        raw_rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    canonical = canonical_rows(raw_rows)
    completed = [item for item in canonical if item.get("status") == "completed"]
    status_counts = Counter(str(item.get("status") or "missing") for item in canonical)
    passed = path.exists() and expected > 0 and len(completed) == expected
    return status_row(
        "completed_ledger",
        "pass" if passed else "missing_or_incomplete",
        path=rel(path, root),
        observed={
            "expected_atomic_run_count": expected,
            "raw_ledger_row_count": len(raw_rows),
            "unique_run_row_count": len(canonical),
            "completed_atomic_run_count": len(completed),
            "status_counts": dict(sorted(status_counts.items())),
        },
        blocker=not passed,
        next_action=(
            "No action; candidate ledger is complete."
            if passed
            else "Resume the candidate config until expected completed rows are present."
        ),
    )


def report_dir_for_row(root: Path, row: dict[str, Any]) -> Path:
    ledger = Path(str(row.get("ledger") or ""))
    result_slug = ledger.parent.name
    return root / "experiments/regression/reports" / result_slug


def pilot_summary_status(root: Path, row: dict[str, Any]) -> dict[str, Any]:
    path = report_dir_for_row(root, row) / "pilot_summary.json"
    expected = int(row.get("expected_atomic_run_count") or 0)
    payload = load_optional_json(path)
    metadata = payload.get("metadata") or {}
    passed = (
        path.exists()
        and int(metadata.get("unique_run_rows") or 0) == expected
        and int((metadata.get("status_counts") or {}).get("completed") or 0) == expected
    )
    return status_row(
        "pilot_summary",
        "pass" if passed else "missing_or_incomplete",
        path=rel(path, root),
        observed={
            "unique_run_rows": metadata.get("unique_run_rows"),
            "status_counts": metadata.get("status_counts"),
            "summary_row_count": len(payload.get("rows") or []),
        },
        blocker=not passed,
        next_action=(
            "No action; pilot summary is synchronized with the ledger."
            if passed
            else "Run summarize_regression_results.py for this candidate ledger."
        ),
    )


def split_profile_status(root: Path, row: dict[str, Any]) -> dict[str, Any]:
    path = report_dir_for_row(root, row) / "split_profile.json"
    payload = load_optional_json(path)
    seed_rows = [
        seed
        for profile in payload.get("profiles", []) or []
        for seed in profile.get("seeds", []) or []
    ]
    row_id_failures = [
        seed.get("seed")
        for seed in seed_rows
        if seed.get("all_row_id_overlaps_zero") is not True
    ]
    split_group_failures = [
        seed.get("seed")
        for seed in seed_rows
        if seed.get("all_split_group_overlaps_zero") is False
    ]
    sparse_cells = sum(int(seed.get("sparse_primary_group_cell_count") or 0) for seed in seed_rows)
    duplicate_signature_caveat_count = sum(
        1
        for seed in seed_rows
        if seed.get("all_model_visible_feature_signature_overlaps_zero") is False
        or seed.get("all_model_visible_feature_plus_target_signature_overlaps_zero")
        is False
    )
    hard_pass = path.exists() and not row_id_failures and not split_group_failures
    caveat = sparse_cells > 0 or duplicate_signature_caveat_count > 0
    return status_row(
        "split_profile",
        "pass_with_caveats" if hard_pass and caveat else ("pass" if hard_pass else "fail"),
        path=rel(path, root),
        observed={
            "schema": payload.get("schema"),
            "seed_count": len(seed_rows),
            "row_id_overlap_failure_seeds": row_id_failures,
            "split_group_overlap_failure_seeds": split_group_failures,
            "sparse_primary_group_cell_count": sparse_cells,
            "duplicate_signature_caveat_seed_count": duplicate_signature_caveat_count,
        },
        blocker=not hard_pass,
        caveat=caveat,
        next_action=(
            "Use split profile as hard split evidence, but keep sparse/duplicate caveats in claim text."
            if hard_pass
            else "Regenerate split profile and inspect row-id or split-group overlaps."
        ),
    )


def simple_file_status(
    root: Path,
    row: dict[str, Any],
    artifact_id: str,
    filename: str,
    *,
    blocker: bool = True,
    next_action: str,
) -> dict[str, Any]:
    path = report_dir_for_row(root, row) / filename
    return status_row(
        artifact_id,
        "present" if path.exists() else "missing",
        path=rel(path, root),
        observed={"exists": path.exists()},
        blocker=blocker and not path.exists(),
        next_action="No action; artifact is present." if path.exists() else next_action,
    )


def global_register_status(root: Path, dataset_id: str, *, kind: str) -> dict[str, Any]:
    if kind == "claim_register_refresh":
        path = root / CLAIM_REGISTER
        payload = load_optional_json(path)
        text = json.dumps(payload, sort_keys=True)
        present = dataset_id in text and "main_result_candidate" in text
        next_action = "Add a candidate-specific claim-register entry after post-run sidecars pass."
    elif kind == "bundle_eligibility_refresh":
        path = root / BUNDLE_INDEX
        payload = load_optional_json(path)
        text = json.dumps(payload, sort_keys=True)
        present = dataset_id in text and "main_result_candidate" in text
        next_action = "Add candidate bundle-index and eligibility rows after manifest generation."
    elif kind == "paper_readiness_refresh":
        path = root / PAPER_READINESS
        payload = load_optional_json(path)
        present = (payload.get("summary") or {}).get(
            "main_result_candidate_results_status"
        ) is not None
        next_action = "No action; paper-readiness map sees candidate results."
    elif kind == "kg_refresh":
        path = root / KG_CATALOG
        payload = load_optional_json(path)
        node_ids = {str(node.get("id")) for node in payload.get("nodes", []) or []}
        present = "report:main_result_candidate_bundle_results" in node_ids
        next_action = "No action; KG links candidate result summary."
    else:
        raise ValueError(kind)
    return status_row(
        kind,
        "present" if present else "missing",
        path=rel(path, root),
        observed={"candidate_dataset_id": dataset_id, "present": present},
        blocker=not present and kind in {"claim_register_refresh", "bundle_eligibility_refresh"},
        next_action=next_action if not present else "No action; global artifact is refreshed.",
    )


def dataset_row(root: Path, plan_row: dict[str, Any]) -> dict[str, Any]:
    dataset_id = str(plan_row.get("dataset_id"))
    checks = [
        ledger_status(root, plan_row),
        pilot_summary_status(root, plan_row),
        split_profile_status(root, plan_row),
        simple_file_status(
            root,
            plan_row,
            "feature_leakage_audit",
            "feature_leakage_audit.json",
            next_action="Run prediction feature-leakage audit against the candidate prediction cache.",
        ),
        simple_file_status(
            root,
            plan_row,
            "endpoint_audit",
            "endpoint_audit.json",
            next_action="Run full-method endpoint audit for this candidate bundle.",
        ),
        simple_file_status(
            root,
            plan_row,
            "publication_readiness_manifest",
            "publication_readiness_manifest.md",
            next_action="Generate candidate publication-readiness manifest after sidecars pass.",
        ),
        global_register_status(root, dataset_id, kind="claim_register_refresh"),
        global_register_status(root, dataset_id, kind="bundle_eligibility_refresh"),
        global_register_status(root, dataset_id, kind="paper_readiness_refresh"),
        global_register_status(root, dataset_id, kind="kg_refresh"),
    ]
    blocker_count = sum(1 for item in checks if item["blocker"])
    caveat_count = sum(1 for item in checks if item["caveat"])
    return {
        "dataset_id": dataset_id,
        "config_path": plan_row.get("config_path"),
        "report_dir": rel(report_dir_for_row(root, plan_row), root),
        "required_post_run_artifacts": plan_row.get("required_post_run_artifacts"),
        "closure_status": (
            "post_run_closure_blocked"
            if blocker_count
            else (
                "post_run_closure_ready_with_caveats"
                if caveat_count
                else "post_run_closure_ready"
            )
        ),
        "blocker_count": blocker_count,
        "caveat_count": caveat_count,
        "checks": checks,
    }


def build_payload(root: Path, *, plan_path: Path, results_path: Path) -> dict[str, Any]:
    plan = read_json(plan_path)
    results = read_json(results_path)
    rows = [
        dataset_row(root, row)
        for row in plan.get("candidate_rows") or []
        if isinstance(row, dict) and row.get("dataset_id")
    ]
    artifact_counts: dict[str, Counter[str]] = {}
    for row in rows:
        for check in row["checks"]:
            artifact_counts.setdefault(check["artifact_id"], Counter())[check["status"]] += 1
    blocker_counts = Counter(
        check["artifact_id"]
        for row in rows
        for check in row["checks"]
        if check["blocker"]
    )
    total_blockers = sum(row["blocker_count"] for row in rows)
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "main_result_candidate_bundle_plan": rel(plan_path, root),
            "main_result_candidate_bundle_results": rel(results_path, root),
            "paper_readiness_map": rel(root / PAPER_READINESS, root),
            "knowledge_graph": rel(root / KG_CATALOG, root),
            "manuscript_claim_register": rel(root / CLAIM_REGISTER, root),
            "manuscript_bundle_index": rel(root / BUNDLE_INDEX, root),
            "bundle_eligibility_matrix": rel(root / BUNDLE_ELIGIBILITY, root),
        },
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": {
            "overall_status": (
                "main_result_candidate_post_run_closure_blocked"
                if total_blockers
                else "main_result_candidate_post_run_closure_ready_no_promotions"
            ),
            "can_support_main_result_promotion": False,
            "candidate_dataset_count": len(rows),
            "completed_atomic_run_count": (results.get("summary") or {}).get(
                "completed_atomic_run_count"
            ),
            "expected_atomic_run_count": (results.get("summary") or {}).get(
                "expected_atomic_run_count"
            ),
            "dataset_blocked_count": sum(1 for row in rows if row["blocker_count"]),
            "total_blocker_count": total_blockers,
            "blocker_counts_by_artifact": dict(sorted(blocker_counts.items())),
            "artifact_status_counts": {
                key: dict(sorted(counter.items()))
                for key, counter in sorted(artifact_counts.items())
            },
        },
        "dataset_rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Main-Result Candidate Post-Run Closure Audit",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Main-result promotion supported: `{summary['can_support_main_result_promotion']}`",
        f"- Candidate datasets: {summary['candidate_dataset_count']}",
        f"- Completed rows: {summary['completed_atomic_run_count']} / {summary['expected_atomic_run_count']}",
        f"- Blocked datasets: {summary['dataset_blocked_count']}",
        f"- Total blockers: {summary['total_blocker_count']}",
        f"- Blocker counts by artifact: `{summary['blocker_counts_by_artifact']}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Dataset Closure Rows",
            "",
            "| Dataset | Status | Blockers | Caveats | Missing/blocking artifacts |",
            "| --- | --- | ---: | ---: | --- |",
        ]
    )
    for row in payload["dataset_rows"]:
        blockers = [
            check["artifact_id"] for check in row["checks"] if check["blocker"]
        ]
        lines.append(
            "| "
            f"`{row['dataset_id']}` | "
            f"`{row['closure_status']}` | "
            f"{row['blocker_count']} | "
            f"{row['caveat_count']} | "
            f"`{blockers}` |"
        )
    lines.extend(["", "## Artifact Status Counts", ""])
    for artifact_id, counts in summary["artifact_status_counts"].items():
        lines.append(f"- `{artifact_id}`: `{counts}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = resolve(root, args.out)
    payload = build_payload(
        root,
        plan_path=resolve(root, args.plan),
        results_path=resolve(root, args.results),
    )
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(json.dumps({"out": rel(out_path, root), **payload["summary"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
