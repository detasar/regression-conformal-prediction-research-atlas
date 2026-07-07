"""Run the bounded-support positive-validity protocol without promoting claims.

The current manuscript surface has target-domain, endpoint, and post-handling
evidence. This script evaluates whether that evidence can support a positive
bounded-support validity claim. A clean run can still produce a no-claim result:
the protocol is executed, but the acceptance criteria are not met.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_bounded_support_positive_validation_protocol_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/"
    "bounded_support_positive_validation_protocol.json"
)
BOUNDED_SUPPORT_PROTOCOL = Path(
    "experiments/regression/manuscript/bounded_support_protocol.json"
)
BOUNDED_SUPPORT_DATASET_AUDIT = Path(
    "experiments/regression/manuscript/bounded_support_dataset_audit.json"
)
BOUNDED_SUPPORT_POSTHANDLING = Path(
    "experiments/regression/manuscript/bounded_support_posthandling_validation.json"
)
BOUNDED_SUPPORT_ENDPOINT_CLOSURE = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "bounded_support_endpoint_closure_audit.json"
)
PAPER_READINESS = Path("experiments/regression/manuscript/paper_readiness_map.json")
ACTION_ID = "endpoint_bounded_support_gate.run_positive_bounded_support_validity_protocol"
NEUTRAL_REPORTING_POLICY = (
    "This is a neutral scientific test. Positive, negative, blocked, and "
    "no-claim outcomes are reported as observed; no conformal method or "
    "validity claim is promoted beyond its audited evidence."
)


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
    return json.loads(path.read_text(encoding="utf-8"))


def metric_available(policy: dict[str, Any]) -> bool:
    return all(
        policy.get(key) is not None
        for key in ("coverage", "mean_width", "interval_count")
    )


def interval_score_available(policy: dict[str, Any]) -> bool:
    return policy.get("interval_score") is not None


def posthandling_by_bundle(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("bundle_id")): row
        for row in payload.get("rows", []) or []
        if isinstance(row, dict) and row.get("bundle_id")
    }


def endpoint_is_blocked(status: str) -> bool:
    return status.startswith("blocked_") or status.startswith("incomplete_")


def build_row(
    row: dict[str, Any],
    posthandling: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    bundle_id = str(row.get("bundle_id") or "")
    post_row = posthandling.get(bundle_id, {})
    policies = post_row.get("policies") or {}
    raw_policy = policies.get("raw_unclipped") or {}
    clip_policy = policies.get("clip_to_natural_bounds") or {}
    abstain_policy = policies.get("abstain_if_raw_out_of_domain") or {}
    endpoint_status = str(row.get("endpoint_support_status") or "")
    post_status = str(row.get("posthandling_support_status") or "")
    target_domain_class = str(row.get("target_domain_class") or "")
    endpoint_blocked = endpoint_is_blocked(endpoint_status)
    unbounded_no_claim = target_domain_class == "unbounded_real"
    metrics_available = all(
        metric_available(policy)
        for policy in (raw_policy, clip_policy, abstain_policy)
    )
    interval_scores_available = all(
        interval_score_available(policy)
        for policy in (raw_policy, clip_policy, abstain_policy)
    )
    validated_all_rows = post_status == "validated_all_completed_rows"

    if not validated_all_rows:
        inclusion_status = "excluded_posthandling_validation_incomplete"
    elif endpoint_blocked:
        inclusion_status = "excluded_endpoint_domain_blocker"
    elif unbounded_no_claim:
        inclusion_status = "excluded_unbounded_target_no_bounded_claim_needed"
    elif not metrics_available:
        inclusion_status = "excluded_policy_metric_gap"
    else:
        inclusion_status = "eligible_but_global_validity_claim_disabled"

    endpoint_audit = row.get("endpoint_audit") or {}
    return {
        "bundle_id": row.get("bundle_id"),
        "dataset_id": row.get("dataset_id"),
        "target": row.get("target"),
        "target_transform": row.get("target_transform"),
        "target_domain_class": row.get("target_domain_class"),
        "endpoint_support_status": endpoint_status,
        "posthandling_support_status": post_status,
        "claim_status": row.get("claim_status"),
        "blockers": row.get("blockers", []) or [],
        "positive_protocol_inclusion_status": inclusion_status,
        "positive_claim_ready": False,
        "can_support_bounded_support_validity": False,
        "posthandling_validated_all_completed_rows": validated_all_rows,
        "raw_policy_metrics_available": metric_available(raw_policy),
        "clip_policy_metrics_available": metric_available(clip_policy),
        "abstain_policy_metrics_available": metric_available(abstain_policy),
        "policy_metrics_available": metrics_available,
        "interval_score_metrics_available": interval_scores_available,
        "endpoint_blocked_or_incomplete": endpoint_blocked,
        "unbounded_target_no_bounded_claim_needed": unbounded_no_claim,
        "natural_domain_endpoint_excursion_present": endpoint_audit.get(
            "natural_domain_endpoint_excursion_present"
        ),
        "natural_domain_endpoint_excursion_count": endpoint_audit.get(
            "natural_domain_endpoint_excursion_count"
        ),
        "natural_domain_endpoint_excursion_rate": endpoint_audit.get(
            "natural_domain_endpoint_excursion_rate"
        ),
        "raw_policy": {
            "coverage": raw_policy.get("coverage"),
            "mean_width": raw_policy.get("mean_width"),
            "interval_score": raw_policy.get("interval_score"),
            "interval_count": raw_policy.get("interval_count"),
            "lower_below_natural_count": raw_policy.get(
                "lower_below_natural_count"
            ),
            "upper_above_natural_count": raw_policy.get(
                "upper_above_natural_count"
            ),
            "invalid_interval_count": raw_policy.get("invalid_interval_count"),
            "interval_score_nonfinite_count": raw_policy.get(
                "interval_score_nonfinite_count"
            ),
        },
        "clip_policy": {
            "coverage": clip_policy.get("coverage"),
            "mean_width": clip_policy.get("mean_width"),
            "interval_score": clip_policy.get("interval_score"),
            "interval_count": clip_policy.get("interval_count"),
            "lower_below_natural_count": clip_policy.get(
                "lower_below_natural_count"
            ),
            "upper_above_natural_count": clip_policy.get(
                "upper_above_natural_count"
            ),
            "invalid_interval_count": clip_policy.get("invalid_interval_count"),
            "interval_score_nonfinite_count": clip_policy.get(
                "interval_score_nonfinite_count"
            ),
        },
        "abstain_policy": {
            "coverage": abstain_policy.get("coverage"),
            "mean_width": abstain_policy.get("mean_width"),
            "interval_score": abstain_policy.get("interval_score"),
            "interval_count": abstain_policy.get("interval_count"),
            "abstention_rate": abstain_policy.get("abstention_rate"),
            "abstained_interval_count": abstain_policy.get(
                "abstained_interval_count"
            ),
        },
        "source_artifacts": [
            row.get("paths", {}).get("endpoint_audit_json"),
            row.get("paths", {}).get("manifest_path"),
            "experiments/regression/manuscript/bounded_support_dataset_audit.json",
            "experiments/regression/manuscript/bounded_support_posthandling_validation.json",
        ],
    }


def build_payload(root: Path) -> dict[str, Any]:
    sources = {
        "bounded_support_protocol": root / BOUNDED_SUPPORT_PROTOCOL,
        "bounded_support_dataset_audit": root / BOUNDED_SUPPORT_DATASET_AUDIT,
        "bounded_support_posthandling_validation": root / BOUNDED_SUPPORT_POSTHANDLING,
        "bounded_support_endpoint_closure": root / BOUNDED_SUPPORT_ENDPOINT_CLOSURE,
        "paper_readiness_map": root / PAPER_READINESS,
    }
    protocol = read_json(sources["bounded_support_protocol"])
    dataset_audit = read_json(sources["bounded_support_dataset_audit"])
    posthandling = read_json(sources["bounded_support_posthandling_validation"])
    endpoint_closure = read_json(sources["bounded_support_endpoint_closure"])
    paper_readiness = read_json(sources["paper_readiness_map"])

    post_by_bundle = posthandling_by_bundle(posthandling)
    rows = [
        build_row(row, post_by_bundle)
        for row in dataset_audit.get("rows", []) or []
        if isinstance(row, dict)
    ]
    endpoint_blocked_rows = [
        row for row in rows if row["endpoint_blocked_or_incomplete"]
    ]
    policy_metric_rows = [row for row in rows if row["policy_metrics_available"]]
    interval_score_rows = [
        row for row in rows if row["interval_score_metrics_available"]
    ]
    validated_rows = [
        row for row in rows if row["posthandling_validated_all_completed_rows"]
    ]
    inclusion_counts = Counter(
        str(row["positive_protocol_inclusion_status"]) for row in rows
    )
    target_class_counts = Counter(str(row.get("target_domain_class")) for row in rows)
    dataset_summary = dataset_audit.get("summary") or {}
    post_summary = posthandling.get("summary") or {}
    endpoint_summary = endpoint_closure.get("summary") or {}
    protocol_summary = protocol.get("summary") or {}
    readiness_summary = paper_readiness.get("summary") or {}

    acceptance_criteria = {
        "can_support_bounded_support_validity_true": False,
        "no_selected_bundle_blocked_by_endpoint_hygiene_posthandling_or_policy": (
            len(endpoint_blocked_rows) == 0
            and len(validated_rows) == len(rows)
            and len(policy_metric_rows) == len(rows)
        ),
        "coverage_and_interval_validity_metrics_available_after_handling": (
            len(policy_metric_rows) == len(rows)
            and len(interval_score_rows) == len(rows)
            and bool(rows)
        ),
        "sensitivity_against_raw_clipped_and_abstention_policies_available": (
            len(policy_metric_rows) == len(rows) and bool(rows)
        ),
        "current_paper_endpoint_gate_unblocked": (
            readiness_summary.get("blocked_gate_count") == 0
            or endpoint_summary.get("paper_readiness_endpoint_gate_status") != "blocked"
        ),
    }

    quality_checks = {
        "source_artifacts_present": all(path.exists() for path in sources.values()),
        "bounded_support_protocol_available": (
            protocol_summary.get("overall_status")
            == "bounded_support_protocol_defined_no_validity_claim"
        ),
        "dataset_audit_complete": (
            dataset_summary.get("overall_status")
            == "dataset_bounded_support_audit_completed_no_validity_claim"
            and int(dataset_summary.get("failed_check_count") or 0) == 0
        ),
        "posthandling_validation_complete_for_selected_scope": (
            post_summary.get("overall_status")
            == "bounded_support_posthandling_validation_completed"
            and post_summary.get("scope_complete") is True
            and int(post_summary.get("unvalidated_bundle_count") or 0) == 0
            and int(post_summary.get("validated_bundle_count") or 0) == len(rows)
        ),
        "endpoint_closure_complete_no_open_backfill": (
            endpoint_summary.get("overall_status")
            == "endpoint_policy_triage_closed_no_bounded_support_validity_claim"
            and int(endpoint_summary.get("failed_check_count") or 0) == 0
            and int(endpoint_summary.get("open_endpoint_count_backfill_bundle_count") or 0)
            == 0
        ),
        "all_selected_rows_have_policy_metrics": len(policy_metric_rows) == len(rows)
        and bool(rows),
        "positive_claim_not_promoted": (
            protocol_summary.get("can_support_bounded_support_validity") is False
            and dataset_summary.get("can_support_bounded_support_validity") is False
            and endpoint_summary.get("current_manuscript_bounded_support_validity_claim_ready")
            is False
        ),
    }
    failed_checks = [key for key, value in quality_checks.items() if not value]
    acceptance_failed = [
        key for key, value in acceptance_criteria.items() if not value
    ]
    overall_status = (
        "bounded_support_positive_validation_protocol_failed"
        if failed_checks
        else "bounded_support_positive_validation_protocol_completed_no_validity_claim"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "action_id": ACTION_ID,
        "action_status": "empirical_validation_complete_no_bounded_support_claim",
        "neutral_reporting_policy": NEUTRAL_REPORTING_POLICY,
        "sources": {key: rel(path, root) for key, path in sources.items()},
        "summary": {
            "overall_status": overall_status,
            "action_id": ACTION_ID,
            "action_status": "empirical_validation_complete_no_bounded_support_claim",
            "failed_check_count": len(failed_checks),
            "positive_acceptance_failed_count": len(acceptance_failed),
            "selected_bundle_scope": "all_current_manuscript_bundles",
            "selected_bundle_count": len(rows),
            "bundle_count": len(rows),
            "dataset_count": len({row.get("dataset_id") for row in rows}),
            "target_domain_class_counts": dict(sorted(target_class_counts.items())),
            "posthandling_validated_bundle_count": len(validated_rows),
            "policy_metrics_available_bundle_count": len(policy_metric_rows),
            "interval_score_metrics_available_bundle_count": len(
                interval_score_rows
            ),
            "interval_score_metrics_missing_bundle_count": len(rows)
            - len(interval_score_rows),
            "endpoint_blocked_or_incomplete_bundle_count": len(endpoint_blocked_rows),
            "endpoint_clean_or_not_applicable_bundle_count": len(rows)
            - len(endpoint_blocked_rows),
            "natural_domain_excursion_bundle_count": sum(
                1 for row in rows if row.get("natural_domain_endpoint_excursion_present")
            ),
            "positive_claim_ready_bundle_count": 0,
            "can_support_bounded_support_validity": False,
            "current_manuscript_bounded_support_validity_claim_ready": False,
            "protocol_can_support_bounded_support_validity": protocol_summary.get(
                "can_support_bounded_support_validity"
            ),
            "dataset_audit_can_support_bounded_support_validity": dataset_summary.get(
                "can_support_bounded_support_validity"
            ),
            "endpoint_closure_status": endpoint_summary.get("overall_status"),
            "endpoint_closure_claim_ready_bundle_count": endpoint_summary.get(
                "bounded_support_validity_claim_ready_bundle_count"
            ),
            "paper_readiness_status": readiness_summary.get("overall_status"),
            "paper_readiness_endpoint_gate_status": endpoint_summary.get(
                "paper_readiness_endpoint_gate_status"
            ),
            "inclusion_status_counts": dict(sorted(inclusion_counts.items())),
        },
        "acceptance_criteria_results": acceptance_criteria,
        "failed_acceptance_criteria": acceptance_failed,
        "quality_checks": quality_checks,
        "failed_checks": failed_checks,
        "claim_boundaries": [
            "This protocol evaluates the current manuscript bundles as the selected positive-claim scope.",
            "It does not carve out a cleaner subset after seeing endpoint blockers.",
            "Because the selected scope fails positive bounded-support acceptance criteria, no bounded-support validity claim is promoted.",
            "Raw, clipped, and abstention metrics remain diagnostic sensitivity evidence only.",
            NEUTRAL_REPORTING_POLICY,
        ],
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Bounded Support Positive Validation Protocol",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Action id: `{summary['action_id']}`",
        f"- Action status: `{summary['action_status']}`",
        f"- Neutral reporting policy: {payload['neutral_reporting_policy']}",
        f"- Selected bundle scope: `{summary['selected_bundle_scope']}`",
        f"- Selected bundles: {summary['selected_bundle_count']}",
        f"- Post-handling validated bundles: {summary['posthandling_validated_bundle_count']}",
        f"- Policy metrics available bundles: {summary['policy_metrics_available_bundle_count']}",
        f"- Endpoint blocked/incomplete bundles: {summary['endpoint_blocked_or_incomplete_bundle_count']}",
        f"- Positive claim-ready bundles: {summary['positive_claim_ready_bundle_count']}",
        f"- Can support bounded-support validity: `{summary['can_support_bounded_support_validity']}`",
        f"- Current manuscript bounded-support validity claim ready: `{summary['current_manuscript_bounded_support_validity_claim_ready']}`",
        f"- Positive acceptance failed criteria: {summary['positive_acceptance_failed_count']}",
        f"- Inclusion status counts: `{summary['inclusion_status_counts']}`",
        "",
        "## Acceptance Criteria",
        "",
    ]
    for key, value in payload["acceptance_criteria_results"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Claim Boundaries",
            "",
            *[f"- {item}" for item in payload["claim_boundaries"]],
            "",
            "## Bundle Rows",
            "",
            "| bundle_id | endpoint_status | posthandling_status | inclusion_status | claim_ready |",
            "|---|---|---|---|---|",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            "| {bundle_id} | `{endpoint}` | `{post}` | `{inclusion}` | `{ready}` |".format(
                bundle_id=row.get("bundle_id"),
                endpoint=row.get("endpoint_support_status"),
                post=row.get("posthandling_support_status"),
                inclusion=row.get("positive_protocol_inclusion_status"),
                ready=row.get("positive_claim_ready"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root)
    out = resolve(root, args.out)
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
