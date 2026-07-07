"""Audit endpoint-domain closure status for bounded-support blockers.

This report separates three states that should not be conflated:

* clean endpoint hygiene,
* raw natural-domain endpoint excursions that are already measured and kept
  under a no-validity-claim policy, and
* genuine endpoint-count backfill gaps.

It is a gate-control artifact only. It does not promote bounded-support
validity, final method selection, or dataset-final claims.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_bounded_support_endpoint_closure_audit_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = REPORT_DIR / "bounded_support_endpoint_closure_audit.json"
ENDPOINT_AUDIT_ACTION_ID = (
    "endpoint_bounded_support_gate.audit_natural_domain_endpoint_excursions"
)
BOUNDED_SUPPORT_PROTOCOL = Path(
    "experiments/regression/manuscript/bounded_support_protocol.json"
)
TARGET_DOMAIN_PROVENANCE = Path(
    "experiments/regression/catalogs/target_domain_provenance.json"
)
BOUNDED_SUPPORT_POSTHANDLING_VALIDATION = Path(
    "experiments/regression/manuscript/bounded_support_posthandling_validation.json"
)
BOUNDED_SUPPORT_DATASET_AUDIT = Path(
    "experiments/regression/manuscript/bounded_support_dataset_audit.json"
)
PAPER_READINESS_MAP = Path("experiments/regression/manuscript/paper_readiness_map.json")

NO_VALIDITY_DECISION = "do_not_claim_bounded_support_validity"
RAW_EXCURSION_CLOSURE = "closed_raw_endpoint_excursion_no_validity_claim"
CLEAN_CLOSURE = "closed_endpoint_clean_or_not_applicable_global_no_claim"
BACKFILL_REQUIRED = "open_endpoint_excursion_count_backfill_required"


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


def is_posthandling_validated(row: dict[str, Any]) -> bool:
    if row.get("posthandling_support_status") == "validated_all_completed_rows":
        return True
    validation = row.get("bounded_support_posthandling_validation") or {}
    return validation.get("status") == "validated"


def closure_status(row: dict[str, Any]) -> str:
    endpoint_status = str(row.get("endpoint_support_status") or "")
    endpoint = row.get("endpoint_audit") or {}
    count_status = str(
        endpoint.get("natural_domain_endpoint_excursion_count_status") or ""
    )
    has_unknown_count = (
        endpoint_status == "blocked_natural_domain_endpoint_excursion_count_unknown"
        or (
            endpoint.get("natural_domain_endpoint_excursion_present") is True
            and endpoint.get("natural_domain_endpoint_excursion_count") is None
        )
        or count_status.startswith("not_computed")
    )
    if has_unknown_count:
        return BACKFILL_REQUIRED
    if endpoint_status.startswith("blocked_"):
        return RAW_EXCURSION_CLOSURE
    return CLEAN_CLOSURE


def evidence_strength(status: str, row: dict[str, Any]) -> str:
    endpoint_status = str(row.get("endpoint_support_status") or "")
    if status == BACKFILL_REQUIRED:
        return "endpoint_excursion_present_but_count_not_computed"
    if endpoint_status == "not_applicable_unbounded_target_endpoint_hygiene_recorded":
        return "unbounded_target_endpoint_hygiene_not_applicable"
    if endpoint_status == "clean_no_natural_domain_endpoint_excursions":
        return "exact_endpoint_clean_count"
    if is_posthandling_validated(row):
        return "exact_endpoint_excursion_count_with_posthandling_validation"
    return "raw_endpoint_excursion_count_without_posthandling_validation"


def next_action(status: str) -> str:
    if status == BACKFILL_REQUIRED:
        return "backfill_unknown_natural_endpoint_excursion_count"
    return "maintain_no_bounded_support_validity_claim"


def source_paths(root: Path) -> dict[str, Path]:
    return {
        "bounded_support_protocol": root / BOUNDED_SUPPORT_PROTOCOL,
        "target_domain_provenance": root / TARGET_DOMAIN_PROVENANCE,
        "bounded_support_posthandling_validation": root
        / BOUNDED_SUPPORT_POSTHANDLING_VALIDATION,
        "bounded_support_dataset_audit": root / BOUNDED_SUPPORT_DATASET_AUDIT,
        "paper_readiness_map": root / PAPER_READINESS_MAP,
    }


def build_payload(root: Path) -> dict[str, Any]:
    paths = source_paths(root)
    bounded_support_dataset = read_json(paths["bounded_support_dataset_audit"])
    bounded_support_protocol = read_json(paths["bounded_support_protocol"])
    posthandling = read_json(paths["bounded_support_posthandling_validation"])
    paper_readiness = read_json(paths["paper_readiness_map"])

    rows: list[dict[str, Any]] = []
    by_dataset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(bounded_support_dataset.get("rows") or []):
        if not isinstance(row, dict):
            continue
        status = closure_status(row)
        endpoint = row.get("endpoint_audit") or {}
        validation = row.get("bounded_support_posthandling_validation") or {}
        clip_policy = validation.get("clip_policy") or {}
        closure_row = {
            "row_index": index,
            "bundle_id": row.get("bundle_id"),
            "dataset_id": row.get("dataset_id"),
            "paired_dataset_id": row.get("paired_dataset_id"),
            "target": row.get("target"),
            "target_domain_class": row.get("target_domain_class"),
            "natural_lower": row.get("natural_lower"),
            "natural_upper": row.get("natural_upper"),
            "natural_bound_status": row.get("natural_bound_status"),
            "endpoint_support_status": row.get("endpoint_support_status"),
            "endpoint_closure_status": status,
            "closure_decision": NO_VALIDITY_DECISION,
            "evidence_strength": evidence_strength(status, row),
            "next_action_id": next_action(status),
            "claim_status": row.get("claim_status"),
            "can_support_bounded_support_validity": bool(
                row.get("can_support_bounded_support_validity")
            ),
            "interval_handling_policy": row.get("interval_handling_policy"),
            "posthandling_support_status": row.get("posthandling_support_status"),
            "posthandling_validation_status": validation.get("status"),
            "completed_ledger_rows": validation.get("completed_ledger_rows"),
            "clip_policy_coverage": clip_policy.get("coverage"),
            "clip_policy_abstention_rate": clip_policy.get("abstention_rate"),
            "natural_domain_endpoint_excursion_count": endpoint.get(
                "natural_domain_endpoint_excursion_count"
            ),
            "natural_domain_endpoint_excursion_rate": endpoint.get(
                "natural_domain_endpoint_excursion_rate"
            ),
            "natural_domain_endpoint_excursion_count_status": endpoint.get(
                "natural_domain_endpoint_excursion_count_status"
            ),
            "natural_lower_excursion_count": (
                (endpoint.get("natural_lower_audit") or {}).get("count")
            ),
            "natural_upper_excursion_count": (
                (endpoint.get("natural_upper_audit") or {}).get("count")
            ),
            "observed_range_endpoint_excursion_count": endpoint.get(
                "observed_range_endpoint_excursion_count"
            ),
            "endpoint_report_id": endpoint.get("report_id"),
            "source_artifacts": [
                artifact
                for artifact in (
                    row.get("paths", {}) or {}
                ).values()
                if artifact
            ],
        }
        rows.append(closure_row)
        dataset_id = str(row.get("dataset_id") or "").strip()
        if dataset_id:
            by_dataset[dataset_id].append(closure_row)

    status_counts = Counter(row["endpoint_closure_status"] for row in rows)
    action_counts = Counter(row["next_action_id"] for row in rows)
    endpoint_counts = Counter(row["endpoint_support_status"] for row in rows)
    evidence_counts = Counter(row["evidence_strength"] for row in rows)
    posthandling_validated = sum(
        1
        for row in rows
        if row.get("posthandling_support_status") == "validated_all_completed_rows"
        or row.get("posthandling_validation_status") == "validated"
    )
    global_no_claim = sum(
        1
        for row in bounded_support_dataset.get("rows") or []
        if "global_bounded_support_validity_claim_disabled"
        in (row.get("blockers") or [])
    )
    raw_endpoint_excursion = sum(
        1
        for row in rows
        if str(row.get("endpoint_support_status") or "").startswith("blocked_")
    )
    clean_or_na = sum(1 for row in rows if row["endpoint_closure_status"] == CLEAN_CLOSURE)
    claim_ready = sum(
        1 for row in rows if row.get("can_support_bounded_support_validity")
    )

    dataset_rows: list[dict[str, Any]] = []
    for dataset_id in sorted(by_dataset):
        dataset_closure_rows = by_dataset[dataset_id]
        dataset_status_counts = Counter(
            row["endpoint_closure_status"] for row in dataset_closure_rows
        )
        if dataset_status_counts.get(BACKFILL_REQUIRED):
            dataset_status = "open_endpoint_count_backfill_required"
        elif dataset_status_counts.get(RAW_EXCURSION_CLOSURE):
            dataset_status = "triaged_raw_endpoint_excursions_no_validity_claim"
        else:
            dataset_status = "triaged_endpoint_clean_or_not_applicable_global_no_claim"
        dataset_rows.append(
            {
                "dataset_id": dataset_id,
                "bundle_count": len(dataset_closure_rows),
                "endpoint_closure_status": dataset_status,
                "endpoint_closure_status_counts": dict(
                    sorted(dataset_status_counts.items())
                ),
                "next_action_ids": sorted(
                    {row["next_action_id"] for row in dataset_closure_rows}
                ),
                "bundle_ids": sorted(
                    str(row["bundle_id"])
                    for row in dataset_closure_rows
                    if row.get("bundle_id")
                ),
            }
        )

    open_count = int(status_counts.get(BACKFILL_REQUIRED) or 0)
    failed_checks = []
    checks = {
        "bounded_support_dataset_audit_present": bool(bounded_support_dataset),
        "posthandling_validation_source_present": bool(posthandling),
        "bounded_support_protocol_source_present": bool(bounded_support_protocol),
        "paper_readiness_source_present": bool(paper_readiness),
        "all_rows_have_closure_status": len(rows)
        == len(bounded_support_dataset.get("rows") or []),
        "all_rows_keep_no_validity_claim": claim_ready == 0,
        "posthandling_validated_for_all_rows": posthandling_validated == len(rows),
        "unknown_endpoint_counts_are_explicit_actions": open_count
        == int(action_counts.get("backfill_unknown_natural_endpoint_excursion_count") or 0),
    }
    failed_checks = [key for key, value in checks.items() if not value]
    gate_status = (
        "endpoint_policy_triage_open_count_backfill_required_no_validity_claim"
        if open_count
        else "endpoint_policy_triage_closed_no_bounded_support_validity_claim"
    )
    action_status = (
        "empirical_execution_complete"
        if (
            gate_status
            == "endpoint_policy_triage_closed_no_bounded_support_validity_claim"
            and not failed_checks
            and open_count == 0
            and claim_ready == 0
            and len(rows) > 0
        )
        else "endpoint_count_backfill_required"
    )
    action_status_reason = (
        "natural_domain_endpoint_policy_triage_complete_no_validity_claim"
        if action_status == "empirical_execution_complete"
        else "natural_domain_endpoint_count_backfill_required_no_validity_claim"
    )
    sources = {key: rel(path, root) for key, path in paths.items()}
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "summary": {
            "overall_status": gate_status,
            "action_id": ENDPOINT_AUDIT_ACTION_ID,
            "action_status": action_status,
            "action_status_reason": action_status_reason,
            "failed_check_count": len(failed_checks),
            "bundle_count": len(rows),
            "dataset_count": len(dataset_rows),
            "endpoint_closure_status_counts": dict(sorted(status_counts.items())),
            "endpoint_support_status_counts": dict(sorted(endpoint_counts.items())),
            "endpoint_closure_action_counts": dict(sorted(action_counts.items())),
            "endpoint_closure_evidence_strength_counts": dict(
                sorted(evidence_counts.items())
            ),
            "closed_policy_bundle_count": len(rows) - open_count,
            "open_endpoint_count_backfill_bundle_count": open_count,
            "dataset_open_endpoint_count_backfill_count": sum(
                1
                for row in dataset_rows
                if row["endpoint_closure_status"]
                == "open_endpoint_count_backfill_required"
            ),
            "raw_endpoint_excursion_bundle_count": raw_endpoint_excursion,
            "endpoint_clean_or_not_applicable_bundle_count": clean_or_na,
            "posthandling_validated_bundle_count": posthandling_validated,
            "global_no_claim_bundle_count": global_no_claim,
            "bounded_support_validity_claim_ready_bundle_count": claim_ready,
            "can_support_bounded_support_validity": claim_ready > 0,
            "current_manuscript_bounded_support_validity_claim_ready": False,
            "bounded_support_validity_claim_boundary": (
                "no_current_bounded_support_validity_claim_supported"
            ),
            "paper_readiness_endpoint_gate_status": next(
                (
                    row.get("status")
                    for row in paper_readiness.get("blocked_gates") or []
                    if row.get("gate_id") == "endpoint_bounded_support_gate"
                ),
                (paper_readiness.get("summary") or {}).get(
                    "endpoint_bounded_support_gate_status"
                )
                or "blocked",
            ),
        },
        "claim_boundaries": [
            "This audit closes endpoint-policy triage only; it does not validate bounded-support coverage.",
            "Rows with raw natural-domain endpoint excursions remain eligible only for transparent diagnostic reporting under the no-validity-claim boundary.",
            "Rows with unknown endpoint excursion counts require backfill before any endpoint-support language can be strengthened.",
            "The global bounded-support validity claim remains disabled for every current bundle.",
        ],
        "checks": checks,
        "failed_checks": failed_checks,
        "dataset_rows": dataset_rows,
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Bounded Support Endpoint Closure Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Action: `{summary['action_id']}` -> `{summary['action_status']}`",
        f"- Action status reason: `{summary['action_status_reason']}`",
        f"- Failed checks: {summary['failed_check_count']}",
        f"- Bundles audited: {summary['bundle_count']}",
        f"- Datasets audited: {summary['dataset_count']}",
        f"- Closure status counts: `{summary['endpoint_closure_status_counts']}`",
        f"- Action counts: `{summary['endpoint_closure_action_counts']}`",
        f"- Closed policy bundles: {summary['closed_policy_bundle_count']}",
        f"- Open endpoint-count backfill bundles: {summary['open_endpoint_count_backfill_bundle_count']}",
        f"- Raw endpoint-excursion bundles: {summary['raw_endpoint_excursion_bundle_count']}",
        f"- Endpoint clean/not-applicable bundles: {summary['endpoint_clean_or_not_applicable_bundle_count']}",
        f"- Posthandling validated bundles: {summary['posthandling_validated_bundle_count']}",
        f"- Global no-claim bundles: {summary['global_no_claim_bundle_count']}",
        f"- Bounded-support validity claim-ready bundles: {summary['bounded_support_validity_claim_ready_bundle_count']}",
        f"- Current manuscript bounded-support validity claim ready: `{summary['current_manuscript_bounded_support_validity_claim_ready']}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Dataset Closure",
            "",
            "| Dataset | Bundles | Closure status | Next actions |",
            "| --- | ---: | --- | --- |",
        ]
    )
    for row in payload["dataset_rows"]:
        actions = ", ".join(f"`{item}`" for item in row["next_action_ids"])
        lines.append(
            f"| `{row['dataset_id']}` | {row['bundle_count']} | "
            f"`{row['endpoint_closure_status']}` | {actions} |"
        )
    lines.extend(
        [
            "",
            "## Bundle Closure",
            "",
            "| Bundle | Dataset | Target | Domain | Endpoint status | Closure status | Excursions | Next action |",
            "| --- | --- | --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for row in payload["rows"]:
        excursion_count = row.get("natural_domain_endpoint_excursion_count")
        excursion_text = (
            str(excursion_count)
            if excursion_count is not None
            else str(row.get("natural_domain_endpoint_excursion_count_status"))
        )
        lines.append(
            "| "
            f"`{row['bundle_id']}` | "
            f"`{row['dataset_id']}` | "
            f"`{row['target']}` | "
            f"`{row['target_domain_class']}` | "
            f"`{row['endpoint_support_status']}` | "
            f"`{row['endpoint_closure_status']}` | "
            f"{excursion_text} | "
            f"`{row['next_action_id']}` |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status |", "| --- | --- |"])
    for key, value in payload["checks"].items():
        lines.append(f"| `{key}` | `{'pass' if value else 'fail'}` |")
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
    return 0 if not payload["failed_checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
