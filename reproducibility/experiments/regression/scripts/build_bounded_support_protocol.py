"""Build the manuscript bounded-support and endpoint-domain protocol.

This artifact defines the evidence required before a regression conformal
prediction result can use bounded-support or target-domain validity language.
It deliberately does not validate bounded support for the current study.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_bounded_support_protocol_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/bounded_support_protocol.json")
MANIFEST_SCHEMA = Path("experiments/regression/catalogs/manuscript_evidence_manifest_schema.json")
PUBLICATION_PROTOCOL = Path("experiments/regression/PUBLICATION_READINESS_PROTOCOL.md")
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
PUBLICATION_METHODOLOGY = REPORT_DIR / "publication_methodology_audit.json"
FINAL_SELECTION = REPORT_DIR / "final_selection_claim_boundary_audit.json"
RETROSPECTIVE_CONTROLS_MD = REPORT_DIR / "retrospective_methodology_controls.md"
RETROSPECTIVE_GATE = REPORT_DIR / "retrospective_quality_gate.json"
EVIDENCE_VIEW = Path("experiments/regression/manuscript/evidence_view.json")


TARGET_DOMAIN_CLASSES: dict[str, dict[str, Any]] = {
    "unbounded_real": {
        "bounds": "(-inf, +inf)",
        "claim_policy": "No bounded-support claim is available or needed.",
        "required_audit": [
            "target transform and inverse-transform declaration",
            "raw interval endpoint audit",
        ],
    },
    "nonnegative": {
        "bounds": "[0, +inf)",
        "claim_policy": "Lower-support validity requires lower-tail excursion accounting.",
        "required_audit": [
            "count and rate of lower endpoints below zero",
            "coverage and width before any endpoint handling",
            "declared clipping, truncation, or abstention policy",
        ],
    },
    "bounded_continuous": {
        "bounds": "[lower, upper]",
        "claim_policy": "Two-sided support validity requires both lower and upper endpoint accounting.",
        "required_audit": [
            "natural lower and upper bounds with source provenance",
            "count and rate of intervals crossing each bound",
            "coverage and interval-score sensitivity after the declared handling rule",
        ],
    },
    "bounded_ordinal": {
        "bounds": "finite ordered set",
        "claim_policy": "Ordinal support claims require ordered-label and rounding/clipping policy.",
        "required_audit": [
            "allowed ordered target values",
            "rounding or discretization rule",
            "coverage audit on original ordered labels",
        ],
    },
    "count_or_rate": {
        "bounds": "nonnegative integer or bounded rate",
        "claim_policy": "Count/rate support claims require transform-back and domain excursion accounting.",
        "required_audit": [
            "integer/rate domain declaration",
            "transform-back monotonicity check",
            "out-of-domain endpoint counts after inverse transform",
        ],
    },
}

INTERVAL_HANDLING_POLICIES: dict[str, dict[str, Any]] = {
    "report_raw_unclipped_with_excursion_audit": {
        "claim_effect": "Permits transparent diagnostic reporting, not bounded-support validity.",
        "coverage_rule": "Coverage is evaluated on raw intervals; out-of-support endpoints are counted.",
    },
    "clip_for_display_only_not_coverage": {
        "claim_effect": "May be used for plots or tables if raw coverage metrics remain primary.",
        "coverage_rule": "Coverage, width, and interval score must still be reported before clipping.",
    },
    "truncate_with_recalibration_required": {
        "claim_effect": "Can support bounded-domain language only after a separate recalibration/sensitivity gate passes.",
        "coverage_rule": "Report pre-truncation and post-truncation metrics and explain the coverage target.",
    },
    "abstain_or_flag_out_of_domain_intervals": {
        "claim_effect": "Can support a scoped abstention policy, not automatic method superiority.",
        "coverage_rule": "Report abstention rate, coverage on retained rows, and coverage on the full row set.",
    },
}

REQUIRED_EVIDENCE = [
    "target_domain_classification",
    "natural_bound_values_and_provenance",
    "target_transform_and_inverse_transform_policy",
    "endpoint_reconstruction_audit_v2",
    "out_of_support_count_by_dataset_method_model_group_seed",
    "out_of_support_rate_by_dataset_method_model_group_seed",
    "interval_handling_policy",
    "raw_coverage_width_and_interval_score_before_handling",
    "post_handling_coverage_width_and_interval_score_when_handling_changes_intervals",
    "claim_register_update_for_bounded_support_language",
    "sensitivity_or_holdout_validation_for_any_positive_bounded_support_claim",
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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def endpoint_counts(
    evidence_view: dict[str, Any], retrospective_gate: dict[str, Any]
) -> dict[str, Any]:
    evidence_summary = evidence_view.get("summary") or {}
    gate_summary = retrospective_gate.get("summary") or {}
    kg_summary = gate_summary.get("knowledge_graph") or {}
    return {
        "manuscript_endpoint_result_count": int(
            evidence_summary.get("endpoint_result_count") or 0
        ),
        "manuscript_endpoint_caveat_count": int(
            evidence_summary.get("endpoint_caveat_count") or 0
        ),
        "manuscript_clean_endpoint_state_count": int(
            evidence_summary.get("clean_endpoint_state_count") or 0
        ),
        "kg_endpoint_result_count": int(kg_summary.get("endpoint_result_count") or 0),
        "kg_endpoint_caveat_count": int(kg_summary.get("endpoint_caveat_count") or 0),
        "kg_endpoint_relation_coverage": kg_summary.get(
            "endpoint_result_relation_coverage", {}
        ),
    }


def build_checks(
    manifest_schema: dict[str, Any],
    publication_protocol_text: str,
    publication_methodology: dict[str, Any],
    final_selection: dict[str, Any],
    retrospective_controls_text: str,
    counts: dict[str, Any],
) -> dict[str, bool]:
    data_fields = set(str(field) for field in manifest_schema.get("data_evidence_fields", []))
    publication_summary = publication_methodology.get("summary") or {}
    publication_requirements = publication_methodology.get("requirement_statuses") or {}
    final_summary = final_selection.get("summary") or {}
    final_requirements = final_selection.get("requirement_statuses") or {}
    lower_protocol = publication_protocol_text.lower()
    lower_controls = retrospective_controls_text.lower()
    endpoint_total = int(counts.get("manuscript_endpoint_result_count") or 0) + int(
        counts.get("kg_endpoint_result_count") or 0
    )
    return {
        "manifest_schema_has_bounded_support_policy": "bounded_support_policy"
        in data_fields,
        "publication_protocol_requires_bounded_or_endpoint_domain_policy": (
            "bounded-support or endpoint-domain policy" in lower_protocol
            and "natural bounds" in lower_protocol
        ),
        "publication_methodology_keeps_bounded_support_blocked": publication_summary.get(
            "can_support_bounded_support_validity"
        )
        is False,
        "endpoint_bounded_support_gate_still_blocked": (
            publication_requirements.get("endpoint_bounded_support_gate") == "blocked"
            and final_requirements.get("endpoint_bounded_support_gate") == "blocked"
        ),
        "final_selection_claim_remains_blocked": final_summary.get("claim_status")
        == "blocked",
        "endpoint_reconstruction_not_promoted_to_validity": (
            "not bounded-support validity" in lower_controls
            and publication_summary.get("can_support_bounded_support_validity")
            is False
        ),
        "endpoint_evidence_is_linked_but_caveated": (
            endpoint_total > 0
            and int(counts.get("manuscript_endpoint_caveat_count") or 0) > 0
            and int(counts.get("kg_endpoint_caveat_count") or 0) > 0
        ),
        "target_domain_classes_declared": len(TARGET_DOMAIN_CLASSES) >= 5,
        "interval_handling_policies_declared": len(INTERVAL_HANDLING_POLICIES) >= 4,
        "required_evidence_contract_declared": len(REQUIRED_EVIDENCE) >= 10,
    }


def build_payload(root: Path) -> dict[str, Any]:
    out_sources = {
        "manifest_schema": root / MANIFEST_SCHEMA,
        "publication_protocol": root / PUBLICATION_PROTOCOL,
        "publication_methodology": root / PUBLICATION_METHODOLOGY,
        "final_selection_claim_boundary": root / FINAL_SELECTION,
        "retrospective_methodology_controls_md": root / RETROSPECTIVE_CONTROLS_MD,
        "retrospective_quality_gate": root / RETROSPECTIVE_GATE,
        "manuscript_evidence_view": root / EVIDENCE_VIEW,
    }
    manifest_schema = read_json(out_sources["manifest_schema"])
    publication_protocol_text = read_text(out_sources["publication_protocol"])
    publication_methodology = read_json(out_sources["publication_methodology"])
    final_selection = read_json(out_sources["final_selection_claim_boundary"])
    retrospective_controls_text = read_text(out_sources["retrospective_methodology_controls_md"])
    retrospective_gate = read_json(out_sources["retrospective_quality_gate"])
    evidence_view = read_json(out_sources["manuscript_evidence_view"])
    counts = endpoint_counts(evidence_view, retrospective_gate)
    checks = build_checks(
        manifest_schema,
        publication_protocol_text,
        publication_methodology,
        final_selection,
        retrospective_controls_text,
        counts,
    )
    failed_checks = [key for key, value in checks.items() if not value]
    overall_status = (
        "bounded_support_protocol_defined_no_validity_claim"
        if not failed_checks
        else "bounded_support_protocol_incomplete"
    )
    final_requirements = final_selection.get("requirement_statuses") or {}
    publication_summary = publication_methodology.get("summary") or {}
    final_summary = final_selection.get("summary") or {}
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {key: rel(path, root) for key, path in out_sources.items()},
        "summary": {
            "overall_status": overall_status,
            "failed_check_count": len(failed_checks),
            "target_domain_class_count": len(TARGET_DOMAIN_CLASSES),
            "interval_handling_policy_count": len(INTERVAL_HANDLING_POLICIES),
            "required_evidence_count": len(REQUIRED_EVIDENCE),
            "bounded_support_policy_field_present": checks[
                "manifest_schema_has_bounded_support_policy"
            ],
            "can_support_bounded_support_validity": False,
            "publication_can_support_bounded_support_validity": publication_summary.get(
                "can_support_bounded_support_validity"
            ),
            "endpoint_bounded_support_gate_status": final_requirements.get(
                "endpoint_bounded_support_gate"
            ),
            "final_selection_claim_status": final_summary.get("claim_status"),
            **counts,
        },
        "claim_boundaries": [
            "This protocol defines required bounded-support evidence; it does not validate bounded support for any current result.",
            "Endpoint reconstruction hygiene is necessary traceability evidence, not proof that intervals respect a target domain.",
            "Bounded-support, clipping, truncation, and abstention language remains blocked until target-domain audits and post-handling metrics pass.",
        ],
        "checks": checks,
        "failed_checks": failed_checks,
        "target_domain_classes": TARGET_DOMAIN_CLASSES,
        "interval_handling_policies": INTERVAL_HANDLING_POLICIES,
        "required_evidence": REQUIRED_EVIDENCE,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Bounded Support Protocol",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Failed checks: {summary['failed_check_count']}",
        f"- Target-domain classes: {summary['target_domain_class_count']}",
        f"- Interval handling policies: {summary['interval_handling_policy_count']}",
        f"- Required evidence items: {summary['required_evidence_count']}",
        f"- Manifest `bounded_support_policy` field present: `{summary['bounded_support_policy_field_present']}`",
        f"- Can support bounded-support validity now: `{summary['can_support_bounded_support_validity']}`",
        f"- Endpoint bounded-support gate status: `{summary['endpoint_bounded_support_gate_status']}`",
        f"- Final-selection claim status: `{summary['final_selection_claim_status']}`",
        f"- Manuscript endpoint result/caveat/clean counts: {summary['manuscript_endpoint_result_count']} / {summary['manuscript_endpoint_caveat_count']} / {summary['manuscript_clean_endpoint_state_count']}",
        f"- KG endpoint result/caveat counts: {summary['kg_endpoint_result_count']} / {summary['kg_endpoint_caveat_count']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Target-Domain Classes",
            "",
            "| Class | Bounds | Claim policy | Required audit |",
            "| --- | --- | --- | --- |",
        ]
    )
    for class_id, spec in payload["target_domain_classes"].items():
        lines.append(
            "| "
            f"`{class_id}` | "
            f"{spec['bounds']} | "
            f"{spec['claim_policy']} | "
            f"{', '.join(spec['required_audit'])} |"
        )
    lines.extend(
        [
            "",
            "## Interval Handling Policies",
            "",
            "| Policy | Claim effect | Coverage rule |",
            "| --- | --- | --- |",
        ]
    )
    for policy_id, spec in payload["interval_handling_policies"].items():
        lines.append(
            "| "
            f"`{policy_id}` | "
            f"{spec['claim_effect']} | "
            f"{spec['coverage_rule']} |"
        )
    lines.extend(
        [
            "",
            "## Required Evidence",
            "",
        ]
    )
    lines.extend(f"- `{item}`" for item in payload["required_evidence"])
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status |",
            "| --- | --- |",
        ]
    )
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
    return 1 if payload["failed_checks"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
