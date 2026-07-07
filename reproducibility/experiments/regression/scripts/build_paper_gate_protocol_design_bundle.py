"""Build protocol-design artifacts for executable paper-gate actions.

This artifact completes the first protocol-design layer for the paper-gate
closure plan. It does not close positive claim gates. Instead it records the
claim contracts that must be satisfied before empirical audits, selection, or
Venn-Abers validation work can be promoted.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_paper_gate_protocol_design_bundle_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/paper_gate_protocol_design_bundle.json"
)
PAPER_GATE_CLOSURE = Path(
    "experiments/regression/manuscript/paper_gate_closure_map.json"
)
PAPER_READINESS = Path("experiments/regression/manuscript/paper_readiness_map.json")
SELECTION_MULTIPLICITY_PROTOCOL = Path(
    "experiments/regression/manuscript/selection_multiplicity_protocol.json"
)
BOUNDED_SUPPORT_PROTOCOL = Path(
    "experiments/regression/manuscript/bounded_support_protocol.json"
)
FAIRNESS_POPULATION_READINESS = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "fairness_population_readiness_audit.json"
)
VENN_ABERS_VALIDATION_READINESS = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "venn_abers_validation_readiness_audit.json"
)
VENN_ABERS_IVAPD_PROTOCOL = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "venn_abers_grid_ivapd_validation_protocol.json"
)
METHOD_PERFORMANCE_SYNTHESIS = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "method_performance_synthesis.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def protocol_row(
    *,
    action_id: str,
    gate_id: str,
    protocol_id: str,
    title: str,
    design_contract: list[str],
    required_fields: list[str],
    evidence_sources: list[str],
    acceptance_criteria: list[str],
    downstream_action_ids: list[str],
    claim_boundary: str,
) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "gate_id": gate_id,
        "protocol_id": protocol_id,
        "title": title,
        "status": "protocol_design_complete",
        "claim_effect": "protocol_only_no_positive_claim_promotion",
        "design_contract": design_contract,
        "required_fields": required_fields,
        "evidence_sources": evidence_sources,
        "acceptance_criteria": acceptance_criteria,
        "downstream_action_ids": downstream_action_ids,
        "claim_boundary": claim_boundary,
    }


def build_protocol_rows(root: Path) -> list[dict[str, Any]]:
    bounded_support = read_json(root / BOUNDED_SUPPORT_PROTOCOL)
    fairness = read_json(root / FAIRNESS_POPULATION_READINESS)
    multiplicity = read_json(root / SELECTION_MULTIPLICITY_PROTOCOL)
    venn_readiness = read_json(root / VENN_ABERS_VALIDATION_READINESS)
    venn_ivapd = read_json(root / VENN_ABERS_IVAPD_PROTOCOL)
    performance = read_json(root / METHOD_PERFORMANCE_SYNTHESIS)

    publication_rows = int(
        (performance.get("summary") or {}).get("completed_ledger_rows") or 0
    )
    method_count = int((performance.get("summary") or {}).get("method_count") or 0)
    dataset_count = int((performance.get("summary") or {}).get("dataset_count") or 0)
    target_domain_class_count = int(
        (bounded_support.get("summary") or {}).get("target_domain_class_count") or 0
    )
    fairness_bundle_count = int(
        (fairness.get("summary") or {}).get("bundle_count") or 0
    )
    ranking_scope_count = int(
        (multiplicity.get("summary") or {}).get("ranking_scope_count") or 0
    )
    venn_undercoverage_run_count = int(
        (venn_readiness.get("summary") or {}).get("undercoverage_run_count") or 0
    )
    ivapd_status = str(
        (venn_ivapd.get("summary") or {}).get("ivapd_interval_cp_status") or ""
    )

    return [
        protocol_row(
            action_id=(
                "endpoint_bounded_support_gate."
                "define_target_domain_validity_estimand"
            ),
            gate_id="endpoint_bounded_support_gate",
            protocol_id="target_domain_bounded_support_validity_estimand_v1",
            title="Target-domain bounded-support validity estimand",
            design_contract=[
                "Define coverage validity over the declared natural target domain, not over observed test endpoints only.",
                "Bind every lower and upper prediction endpoint to a dataset target-domain class before any bounded-support language is allowed.",
                "Treat clipping, monotone inverse transforms, and endpoint rejection as explicit target-domain policies rather than silent post-processing.",
                f"Carry forward the current bounded-support protocol taxonomy with {target_domain_class_count} target-domain classes.",
            ],
            required_fields=[
                "dataset_id",
                "target_name",
                "target_domain_class",
                "natural_lower_bound",
                "natural_upper_bound",
                "target_transform",
                "inverse_transform_policy",
                "endpoint_posthandling_policy",
                "allowed_endpoint_excursion_policy",
            ],
            evidence_sources=[
                rel(root / BOUNDED_SUPPORT_PROTOCOL, root),
                rel(root / PAPER_GATE_CLOSURE, root),
            ],
            acceptance_criteria=[
                "Every manuscript candidate bundle has a declared target-domain validity estimand.",
                "Endpoint validity language cites the target-domain policy and does not rely on empirical observed ranges alone.",
                "The downstream endpoint-excursion audit can classify every excursion as pass, allowed-by-policy, or blocker.",
            ],
            downstream_action_ids=[
                "endpoint_bounded_support_gate.audit_natural_domain_endpoint_excursions"
            ],
            claim_boundary=(
                "This protocol does not make a bounded-support validity claim; "
                "it only defines the estimand needed for the next endpoint audit."
            ),
        ),
        protocol_row(
            action_id=(
                "fairness_population_inference_gate."
                "define_population_and_protected_scope"
            ),
            gate_id="fairness_population_inference_gate",
            protocol_id="population_and_protected_attribute_scope_v1",
            title="Population universe and protected-attribute scope",
            design_contract=[
                "Separate diagnostic grouping variables from protected attributes that support fairness inference.",
                "Declare the population universe, inclusion rule, exclusion rule, and protected-attribute coding before group-gap estimation.",
                "Record missing protected-attribute handling before computing group counts or uncertainty.",
                f"Apply this contract to the current {fairness_bundle_count} fairness-readiness bundles before promotion.",
            ],
            required_fields=[
                "dataset_id",
                "population_universe",
                "sampling_frame",
                "protected_attribute_columns",
                "protected_category_mapping",
                "protected_attribute_missingness_policy",
                "diagnostic_group_columns",
                "claim_eligible_group_columns",
            ],
            evidence_sources=[
                rel(root / FAIRNESS_POPULATION_READINESS, root),
                rel(root / PAPER_GATE_CLOSURE, root),
            ],
            acceptance_criteria=[
                "Every candidate fairness claim has population_universe and protected_attribute_scope fields.",
                "Diagnostic-only group columns are explicitly excluded from fairness population claims.",
                "The downstream sampling-weight policy can be evaluated without reinterpreting group labels.",
            ],
            downstream_action_ids=[
                "fairness_population_inference_gate.define_sampling_weight_policy"
            ],
            claim_boundary=(
                "This protocol keeps all current group results diagnostic until "
                "sampling, group counts, missingness, gaps, uncertainty, and "
                "multiplicity are audited."
            ),
        ),
        protocol_row(
            action_id=(
                "multiplicity_selection_record."
                "freeze_searched_space_and_error_contract"
            ),
            gate_id="multiplicity_selection_record",
            protocol_id="searched_space_and_error_control_contract_v1",
            title="Searched-space and error-control contract",
            design_contract=[
                f"Freeze the searched publication evidence as {publication_rows} completed rows over {dataset_count} datasets and {method_count} conformal methods unless a later refresh explicitly supersedes it.",
                "Define searched dimensions as dataset, target, transform, alpha, model family, model hyperparameters, conformal method, split seed, group policy, endpoint policy, and eligibility filter.",
                "Keep the primary CQR finding diagnostic until final-selection, dataset, endpoint, fairness, and multiplicity gates are simultaneously compatible.",
                f"Use the existing selection multiplicity protocol with {ranking_scope_count} ranking scopes as the source contract.",
            ],
            required_fields=[
                "search_space_snapshot_id",
                "dataset_ids",
                "alpha_levels",
                "model_families",
                "model_hyperparameter_grid",
                "conformal_methods",
                "split_seed_policy",
                "primary_ranking_metric",
                "tie_break_rule",
                "post_selection_validation_policy",
                "winner_language_activation_rule",
            ],
            evidence_sources=[
                rel(root / SELECTION_MULTIPLICITY_PROTOCOL, root),
                rel(root / METHOD_PERFORMANCE_SYNTHESIS, root),
                rel(root / PAPER_GATE_CLOSURE, root),
            ],
            acceptance_criteria=[
                "The selection record covers every result consumed by a future final-winner claim.",
                "No searched dimension used in the final recommendation remains outside the multiplicity contract.",
                "If final-selection claims remain blocked, CQR is reported only as a diagnostic primary candidate.",
            ],
            downstream_action_ids=[
                "multiplicity_selection_record.link_record_to_final_selection_claim"
            ],
            claim_boundary=(
                "This protocol freezes the search contract; it does not activate "
                "winner, superiority, or final recommendation language."
            ),
        ),
        protocol_row(
            action_id=(
                "venn_abers_regression_validation_gate."
                "design_validated_regression_venn_abers_method"
            ),
            gate_id="venn_abers_regression_validation_gate",
            protocol_id="validated_regression_venn_abers_interval_contract_v1",
            title="Validated regression Venn-Abers interval method contract",
            design_contract=[
                "A regression Venn-Abers method can be promoted only if it outputs finite-sample-valid prediction intervals, not merely calibrated predictive distributions.",
                "The interval construction must state exchangeability assumptions, score definition, threshold/quantile mapping, lower-upper endpoint construction, and finite-sample coverage target.",
                "The current fast bridge remains negative diagnostic evidence until exact-grid or theory-backed validation passes.",
                f"Current Venn-Abers evidence remains blocked with {venn_undercoverage_run_count} undercoverage runs and IVAPD status `{ivapd_status}`.",
            ],
            required_fields=[
                "method_name",
                "regression_interval_algorithm",
                "exchangeability_assumption",
                "score_definition",
                "calibration_rule",
                "interval_endpoint_rule",
                "coverage_guarantee_statement",
                "grid_or_theory_validation_plan",
                "split_fallback_separation_rule",
            ],
            evidence_sources=[
                rel(root / VENN_ABERS_VALIDATION_READINESS, root),
                rel(root / VENN_ABERS_IVAPD_PROTOCOL, root),
                rel(root / PAPER_GATE_CLOSURE, root),
            ],
            acceptance_criteria=[
                "The method contract distinguishes validated Venn-Abers regression from split conformal fallback.",
                "Predictive-distribution-only outputs cannot satisfy the interval CP contract without a proven interval endpoint rule.",
                "Exact-grid or theory-backed validation can be run against a declared nominal coverage target.",
            ],
            downstream_action_ids=[
                "venn_abers_regression_validation_gate.run_exact_grid_or_theory_validation_benchmark",
                "venn_abers_regression_validation_gate.validate_ivapd_interval_cp_contract",
            ],
            claim_boundary=(
                "This protocol preserves the current negative Venn-Abers result; "
                "it is a method-design contract, not validation evidence."
            ),
        ),
    ]


def build_payload(root: Path) -> dict[str, Any]:
    closure_map = read_json(root / PAPER_GATE_CLOSURE)
    paper_readiness = read_json(root / PAPER_READINESS)
    rows = build_protocol_rows(root)
    status_counts = Counter(str(row.get("status")) for row in rows)
    gate_counts = Counter(str(row.get("gate_id")) for row in rows)
    downstream_action_ids = sorted(
        {
            str(action_id)
            for row in rows
            for action_id in row.get("downstream_action_ids", []) or []
        }
    )
    completed_action_ids = sorted(
        str(row["action_id"])
        for row in rows
        if row.get("status") == "protocol_design_complete"
    )

    required_action_ids = {
        "endpoint_bounded_support_gate.define_target_domain_validity_estimand",
        "fairness_population_inference_gate.define_population_and_protected_scope",
        "multiplicity_selection_record.freeze_searched_space_and_error_contract",
        "venn_abers_regression_validation_gate.design_validated_regression_venn_abers_method",
    }
    failed_checks: list[dict[str, Any]] = []
    missing_required = sorted(required_action_ids - set(completed_action_ids))
    if missing_required:
        failed_checks.append(
            {
                "check_id": "required_protocol_design_actions_complete",
                "status": "fail",
                "missing_action_ids": missing_required,
            }
        )
    if any("positive_claim" not in row.get("claim_effect", "") for row in rows):
        failed_checks.append(
            {
                "check_id": "protocol_rows_keep_claim_promotion_disabled",
                "status": "fail",
            }
        )

    overall_status = (
        "paper_gate_protocol_design_bundle_failed"
        if failed_checks
        else "paper_gate_protocol_design_bundle_ready_no_claim_promotions"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": overall_status,
            "paper_gate_closure_status": (closure_map.get("summary") or {}).get(
                "overall_status"
            ),
            "paper_readiness_status": (paper_readiness.get("summary") or {}).get(
                "overall_status"
            ),
            "protocol_design_count": len(rows),
            "completed_protocol_design_action_count": len(completed_action_ids),
            "claim_promoted_action_count": 0,
            "downstream_action_count": len(downstream_action_ids),
            "status_counts": dict(sorted(status_counts.items())),
            "gate_counts": dict(sorted(gate_counts.items())),
            "completed_action_ids": completed_action_ids,
            "downstream_action_ids": downstream_action_ids,
            "failed_check_count": len(failed_checks),
        },
        "claim_boundaries": [
            "This bundle completes protocol-design actions only; it does not close positive paper gates.",
            "Downstream empirical audits must pass before bounded-support, fairness, final-selection, or Venn-Abers validation claims can be promoted.",
            "The existing CQR result remains a diagnostic primary candidate until final-selection and multiplicity gates close.",
            "The existing Venn-Abers regression result remains negative diagnostic evidence until a validated interval method passes the declared benchmark.",
        ],
        "failed_checks": failed_checks,
        "protocol_design_rows": rows,
        "sources": {
            "paper_gate_closure_map": rel(root / PAPER_GATE_CLOSURE, root),
            "paper_readiness_map": rel(root / PAPER_READINESS, root),
            "selection_multiplicity_protocol": rel(
                root / SELECTION_MULTIPLICITY_PROTOCOL, root
            ),
            "bounded_support_protocol": rel(root / BOUNDED_SUPPORT_PROTOCOL, root),
            "fairness_population_readiness": rel(
                root / FAIRNESS_POPULATION_READINESS, root
            ),
            "venn_abers_validation_readiness": rel(
                root / VENN_ABERS_VALIDATION_READINESS, root
            ),
            "venn_abers_ivapd_protocol": rel(root / VENN_ABERS_IVAPD_PROTOCOL, root),
            "method_performance_synthesis": rel(
                root / METHOD_PERFORMANCE_SYNTHESIS, root
            ),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Paper Gate Protocol Design Bundle",
        "",
        "This artifact completes the first protocol-design layer for blocked positive paper gates. It does not promote any claim.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Protocol designs: {summary['protocol_design_count']}",
        f"- Completed protocol-design actions: {summary['completed_protocol_design_action_count']}",
        f"- Claim-promoted actions: {summary['claim_promoted_action_count']}",
        f"- Downstream actions exposed: {summary['downstream_action_count']}",
        f"- Status counts: `{summary['status_counts']}`",
        "",
        "## Completed Protocol Designs",
        "",
        "| Action | Gate | Protocol | Downstream Actions |",
        "|---|---|---|---:|",
    ]
    for row in payload["protocol_design_rows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['action_id']}`",
                    f"`{row['gate_id']}`",
                    f"`{row['protocol_id']}`",
                    str(len(row.get("downstream_action_ids", []) or [])),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Claim Boundaries", ""])
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = root / args.out
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))


if __name__ == "__main__":
    main()
