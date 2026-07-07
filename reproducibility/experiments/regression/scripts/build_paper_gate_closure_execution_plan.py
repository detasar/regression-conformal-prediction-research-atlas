"""Build an execution plan for closing blocked regression paper gates.

This artifact does not promote any paper claim. It turns the remaining blocked
paper gates into concrete protocol, empirical, refresh, and claim-control
actions with dependencies and acceptance criteria.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_paper_gate_closure_execution_plan_v1"
DEFAULT_OUT = Path(
    "experiments/regression/manuscript/paper_gate_closure_execution_plan.json"
)
PAPER_GATE_CLOSURE = Path(
    "experiments/regression/manuscript/paper_gate_closure_map.json"
)
PAPER_READINESS = Path("experiments/regression/manuscript/paper_readiness_map.json")
PAPER_GATE_PROTOCOL_DESIGN_BUNDLE = Path(
    "experiments/regression/manuscript/paper_gate_protocol_design_bundle.json"
)
FAIRNESS_SAMPLING_WEIGHT_POLICY = Path(
    "experiments/regression/manuscript/fairness_sampling_weight_policy.json"
)
FAIRNESS_GROUP_DIAGNOSTIC_AUDIT = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "fairness_group_diagnostic_audit.json"
)
FAIRNESS_GROUP_MULTIPLICITY_SCOPE = Path(
    "experiments/regression/manuscript/fairness_group_multiplicity_scope.json"
)
FAIRNESS_POPULATION_READINESS = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "fairness_population_readiness_audit.json"
)
BOUNDED_SUPPORT_ENDPOINT_CLOSURE = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "bounded_support_endpoint_closure_audit.json"
)
BOUNDED_SUPPORT_POSITIVE_VALIDATION = Path(
    "experiments/regression/manuscript/"
    "bounded_support_positive_validation_protocol.json"
)
VENN_ABERS_NEGATIVE_DISPOSITION = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "venn_abers_negative_evidence_disposition_audit.json"
)
BOUNDED_SUPPORT_POSITIVE_VALIDATION_ACTION_ID = (
    "endpoint_bounded_support_gate.run_positive_bounded_support_validity_protocol"
)
BOUNDED_SUPPORT_REFRESH_ACTION_ID = (
    "endpoint_bounded_support_gate.refresh_bounded_support_claim_gate"
)
ENDPOINT_AUDIT_ACTION_ID = (
    "endpoint_bounded_support_gate.audit_natural_domain_endpoint_excursions"
)
FAIRNESS_POPULATION_REFRESH_ACTION_ID = (
    "fairness_population_inference_gate.refresh_fairness_population_gate"
)
VENN_ABERS_NEGATIVE_DISPOSITION_ACTION_ID = (
    "venn_abers_regression_validation_gate."
    "accept_negative_result_disposition_for_manuscript"
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


def status_is_blocked(value: Any) -> bool:
    return "blocked" in str(value or "").lower()


def slug(value: str) -> str:
    return (
        value.replace(":", "_")
        .replace("/", "_")
        .replace(" ", "_")
        .replace("-", "_")
        .lower()
    )


def closure_rows_by_gate(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("gate_id")): row
        for row in payload.get("gate_rows", []) or []
        if isinstance(row, dict) and row.get("gate_id")
    }


def readiness_status_by_gate(payload: dict[str, Any]) -> dict[str, str]:
    return {
        str(row.get("gate_id")): str(row.get("status") or "")
        for row in payload.get("blocked_gates", []) or []
        if isinstance(row, dict) and row.get("gate_id")
    }


def completed_protocol_design_action_ids(payload: dict[str, Any]) -> set[str]:
    return {
        str(row.get("action_id"))
        for row in payload.get("protocol_design_rows", []) or []
        if isinstance(row, dict)
        and row.get("action_id")
        and row.get("status") == "protocol_design_complete"
    }


def completed_sampling_weight_policy_action_ids(payload: dict[str, Any]) -> set[str]:
    summary = payload.get("summary") or {}
    if (
        summary.get("overall_status")
        == "fairness_sampling_weight_policy_defined_no_fairness_claim"
        and summary.get("action_status") == "protocol_design_complete"
        and summary.get("action_id")
    ):
        return {str(summary["action_id"])}
    return set()


def completed_fairness_group_diagnostic_action_statuses(
    payload: dict[str, Any],
) -> dict[str, str]:
    summary = payload.get("summary") or {}
    if (
        summary.get("overall_status")
        == "fairness_group_diagnostic_audit_completed_no_fairness_claim"
        and summary.get("action_status") == "empirical_execution_complete"
        and summary.get("action_id")
    ):
        return {str(summary["action_id"]): "empirical_execution_complete"}
    return {}


def completed_fairness_group_multiplicity_scope_action_statuses(
    payload: dict[str, Any],
) -> dict[str, str]:
    summary = payload.get("summary") or {}
    if (
        summary.get("overall_status")
        == "fairness_group_multiplicity_scope_declared_no_fairness_claim"
        and summary.get("action_status") == "multiplicity_control_complete"
        and summary.get("action_id")
        and summary.get("claim_register_cites_multiplicity_record") is True
        and summary.get("current_manuscript_fairness_population_claim_ready") is False
    ):
        return {str(summary["action_id"]): "multiplicity_control_complete"}
    return {}


def completed_fairness_population_refresh_action_statuses(
    payload: dict[str, Any],
) -> dict[str, str]:
    summary = payload.get("summary") or {}
    bundle_count = int(summary.get("bundle_count") or 0)
    diagnostic_count = int(summary.get("diagnostic_group_bundle_count") or 0)
    if (
        summary.get("overall_status")
        == "fairness_population_readiness_audit_completed_no_fairness_claim"
        and summary.get("fairness_population_claim_status")
        == "blocked_diagnostic_only"
        and summary.get("fairness_requirement_status") == "blocked"
        and summary.get("can_support_publication_ready_fairness") is False
        and int(summary.get("failed_check_count") or 0) == 0
        and bundle_count > 0
        and diagnostic_count == bundle_count
        and int(summary.get("population_fairness_ready_bundle_count") or 0) == 0
        and int(summary.get("population_estimand_declared_bundle_count") or 0) == 0
        and int(summary.get("protected_attribute_scope_declared_bundle_count") or 0)
        == 0
        and int(summary.get("group_counts_recorded_bundle_count") or 0) == bundle_count
        and int(summary.get("group_gap_uncertainty_recorded_bundle_count") or 0)
        == bundle_count
        and int(summary.get("multiplicity_scope_declared_bundle_count") or 0)
        == bundle_count
        and summary.get("claim_register_cites_multiplicity_record") is True
    ):
        return {
            FAIRNESS_POPULATION_REFRESH_ACTION_ID: (
                "gate_refresh_complete_no_fairness_claim"
            )
        }
    return {}


def completed_endpoint_natural_domain_audit_action_statuses(
    payload: dict[str, Any],
) -> dict[str, str]:
    summary = payload.get("summary") or {}
    bundle_count = int(summary.get("bundle_count") or 0)
    closed_count = int(summary.get("closed_policy_bundle_count") or 0)
    if (
        summary.get("overall_status")
        == "endpoint_policy_triage_closed_no_bounded_support_validity_claim"
        and summary.get("action_id") == ENDPOINT_AUDIT_ACTION_ID
        and summary.get("action_status") == "empirical_execution_complete"
        and int(summary.get("failed_check_count") or 0) == 0
        and bundle_count > 0
        and closed_count == bundle_count
        and int(summary.get("open_endpoint_count_backfill_bundle_count") or 0) == 0
        and int(summary.get("global_no_claim_bundle_count") or 0) == bundle_count
        and int(summary.get("bounded_support_validity_claim_ready_bundle_count") or 0)
        == 0
        and summary.get("can_support_bounded_support_validity") is False
        and summary.get("current_manuscript_bounded_support_validity_claim_ready")
        is False
    ):
        return {ENDPOINT_AUDIT_ACTION_ID: "empirical_execution_complete"}
    return {}


def completed_bounded_support_positive_validation_action_statuses(
    payload: dict[str, Any],
) -> dict[str, str]:
    summary = payload.get("summary") or {}
    bundle_count = int(summary.get("bundle_count") or 0)
    if (
        summary.get("overall_status")
        == "bounded_support_positive_validation_protocol_completed_no_validity_claim"
        and summary.get("action_id") == BOUNDED_SUPPORT_POSITIVE_VALIDATION_ACTION_ID
        and summary.get("action_status")
        == "empirical_validation_complete_no_bounded_support_claim"
        and int(summary.get("failed_check_count") or 0) == 0
        and bundle_count > 0
        and int(summary.get("posthandling_validated_bundle_count") or 0)
        == bundle_count
        and int(summary.get("policy_metrics_available_bundle_count") or 0)
        == bundle_count
        and int(summary.get("endpoint_blocked_or_incomplete_bundle_count") or 0) > 0
        and int(summary.get("positive_claim_ready_bundle_count") or 0) == 0
        and summary.get("can_support_bounded_support_validity") is False
        and summary.get("current_manuscript_bounded_support_validity_claim_ready")
        is False
    ):
        return {
            BOUNDED_SUPPORT_POSITIVE_VALIDATION_ACTION_ID: (
                "empirical_validation_complete_no_bounded_support_claim"
            )
        }
    return {}


def completed_bounded_support_refresh_action_statuses(
    *,
    positive_validation: dict[str, Any],
    endpoint_closure: dict[str, Any],
) -> dict[str, str]:
    validation_summary = positive_validation.get("summary") or {}
    endpoint_summary = endpoint_closure.get("summary") or {}
    if (
        validation_summary.get("overall_status")
        == "bounded_support_positive_validation_protocol_completed_no_validity_claim"
        and validation_summary.get("action_status")
        == "empirical_validation_complete_no_bounded_support_claim"
        and int(validation_summary.get("failed_check_count") or 0) == 0
        and validation_summary.get("can_support_bounded_support_validity") is False
        and int(validation_summary.get("positive_claim_ready_bundle_count") or 0) == 0
        and endpoint_summary.get("overall_status")
        == "endpoint_policy_triage_closed_no_bounded_support_validity_claim"
        and endpoint_summary.get("current_manuscript_bounded_support_validity_claim_ready")
        is False
    ):
        return {
            BOUNDED_SUPPORT_REFRESH_ACTION_ID: (
                "gate_refresh_complete_no_bounded_support_claim"
            )
        }
    return {}


def completed_venn_abers_negative_disposition_action_statuses(
    payload: dict[str, Any],
) -> dict[str, str]:
    summary = payload.get("summary") or {}
    if (
        summary.get("overall_status") == "venn_abers_negative_evidence_disposition_pass"
        and summary.get("negative_result_reporting_ready") is True
        and summary.get("current_manuscript_positive_validation_required") is False
    ):
        return {VENN_ABERS_NEGATIVE_DISPOSITION_ACTION_ID: "negative_disposition_complete"}
    return {}


def action(
    gate_id: str,
    action_key: str,
    action_class: str,
    stage: str,
    title: str,
    evidence_needed: list[str],
    acceptance_criteria: list[str],
    *,
    depends_on_gate_ids: list[str] | None = None,
    depends_on_action_keys: list[str] | None = None,
    claim_effect: str = "enables_positive_gate_evidence",
    priority: int = 50,
) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "action_key": action_key,
        "action_id": f"{gate_id}.{action_key}",
        "action_class": action_class,
        "stage": stage,
        "title": title,
        "evidence_needed": evidence_needed,
        "acceptance_criteria": acceptance_criteria,
        "depends_on_gate_ids": depends_on_gate_ids or [],
        "depends_on_action_ids": [
            f"{gate_id}.{key}" if "." not in key else key
            for key in depends_on_action_keys or []
        ],
        "claim_effect": claim_effect,
        "priority": priority,
    }


def action_templates() -> list[dict[str, Any]]:
    return [
        action(
            "endpoint_bounded_support_gate",
            "define_target_domain_validity_estimand",
            "protocol_design",
            "claim_contract_design",
            "Define target-domain bounded-support validity estimand.",
            [
                "Dataset-level natural target domain class.",
                "Transform/inverse-transform endpoint policy.",
                "Allowed clipping or monotone transform policy per target.",
            ],
            [
                "Every manuscript candidate bundle has an explicit target-domain validity estimand.",
                "Validity language is tied to the declared target domain rather than observed test endpoints.",
            ],
            priority=10,
        ),
        action(
            "endpoint_bounded_support_gate",
            "audit_natural_domain_endpoint_excursions",
            "endpoint_audit",
            "empirical_audit",
            "Audit lower/upper endpoint excursions against natural target domain.",
            [
                "Per-run reconstructed lower/upper endpoints.",
                "Natural-domain lower/upper policy per dataset.",
                "Counts of endpoint excursions after all post-handling.",
            ],
            [
                "All candidate bundles have zero unexplained natural-domain endpoint excursions, or every excursion is formally allowed by the target-domain policy.",
                "The audit records bundle, dataset, method, alpha, and endpoint counts.",
            ],
            depends_on_action_keys=["define_target_domain_validity_estimand"],
            priority=20,
        ),
        action(
            "endpoint_bounded_support_gate",
            "run_positive_bounded_support_validity_protocol",
            "validation_protocol",
            "empirical_validation",
            "Run a positive bounded-support validity protocol.",
            [
                "Pre-registered inclusion criteria for bounded-support claim bundles.",
                "Coverage and interval validity metrics after target-domain handling.",
                "Sensitivity against raw endpoint hygiene and clipped/monotone policies.",
            ],
            [
                "Protocol output explicitly sets can_support_bounded_support_validity=true.",
                "No selected bundle is blocked by endpoint hygiene, post-handling, or target-domain policy gaps.",
            ],
            depends_on_action_keys=[
                "define_target_domain_validity_estimand",
                "audit_natural_domain_endpoint_excursions",
            ],
            priority=30,
        ),
        action(
            "endpoint_bounded_support_gate",
            "refresh_bounded_support_claim_gate",
            "gate_refresh",
            "artifact_refresh",
            "Refresh bounded-support protocol, dataset audit, closure map, and paper readiness.",
            [
                "Positive bounded-support validity protocol output.",
                "Updated bounded-support dataset audit.",
                "Updated publication methodology audit.",
            ],
            [
                "endpoint_bounded_support_gate is no longer blocked in paper_readiness_map.",
                "Disallowed bounded-support language is removed only after the gate passes.",
            ],
            depends_on_action_keys=["run_positive_bounded_support_validity_protocol"],
            priority=40,
        ),
        action(
            "fairness_population_inference_gate",
            "define_population_and_protected_scope",
            "protocol_design",
            "claim_contract_design",
            "Define population universe and protected-attribute scope.",
            [
                "Dataset-specific population universe.",
                "Protected attribute columns and category mapping.",
                "Exclusion and missingness policy for protected attributes.",
            ],
            [
                "Each candidate fairness claim has population_universe and protected_attribute_scope.",
                "Diagnostic-only group columns remain explicitly separated from protected-attribute claims.",
            ],
            priority=10,
        ),
        action(
            "fairness_population_inference_gate",
            "define_sampling_weight_policy",
            "protocol_design",
            "claim_contract_design",
            "Define sampling, survey design, or unweighted estimand policy.",
            [
                "Sampling frame per dataset.",
                "Weight columns or explicit unweighted target estimand.",
                "Variance/uncertainty policy for weighted group gaps.",
            ],
            [
                "Every candidate fairness bundle has sampling_weight_policy_declared=true.",
                "Weighted and unweighted estimands are not mixed in the same claim.",
            ],
            depends_on_action_keys=["define_population_and_protected_scope"],
            priority=20,
        ),
        action(
            "fairness_population_inference_gate",
            "compute_group_counts_missingness_and_gaps",
            "fairness_audit",
            "empirical_audit",
            "Compute group counts, missingness, coverage gaps, width gaps, and uncertainty.",
            [
                "Per-group sample counts and missing rates.",
                "Coverage and width by group.",
                "Confidence intervals or bootstrap intervals for group gaps.",
            ],
            [
                "group_counts_recorded=true for all promoted bundles.",
                "missingness_by_group_audited=true.",
                "group_gap_uncertainty_recorded=true.",
            ],
            depends_on_action_keys=[
                "define_population_and_protected_scope",
                "define_sampling_weight_policy",
            ],
            priority=30,
        ),
        action(
            "fairness_population_inference_gate",
            "declare_group_comparison_multiplicity_scope",
            "multiplicity_control",
            "claim_contract_design",
            "Declare multiplicity scope for protected-group comparisons.",
            [
                "Family of group comparisons.",
                "Correction or selective-inference policy.",
                "Link to final selection and manuscript claim register.",
            ],
            [
                "multiplicity_scope_declared_for_group_comparisons=true.",
                "The fairness claim register cites the multiplicity record.",
            ],
            depends_on_action_keys=["compute_group_counts_missingness_and_gaps"],
            priority=40,
        ),
        action(
            "fairness_population_inference_gate",
            "refresh_fairness_population_gate",
            "gate_refresh",
            "artifact_refresh",
            "Refresh fairness population readiness and paper readiness.",
            [
                "Completed population/protected-attribute protocol.",
                "Completed group-gap uncertainty artifact.",
                "Completed multiplicity scope record.",
            ],
            [
                "population_fairness_ready_bundle_count is positive for promoted bundles.",
                "fairness_population_inference_gate is no longer blocked for the scoped claim.",
            ],
            depends_on_action_keys=[
                "declare_group_comparison_multiplicity_scope",
            ],
            priority=50,
        ),
        action(
            "multiplicity_selection_record",
            "freeze_searched_space_and_error_contract",
            "multiplicity_control",
            "claim_contract_design",
            "Freeze searched model/method/dataset/alpha space and error-control contract.",
            [
                "All models, conformal methods, alpha levels, seeds, datasets, and filters searched.",
                "Primary ranking metric and tie-break policy.",
                "Familywise/FDR/post-selection inference policy.",
            ],
            [
                "The selection record covers every result consumed by the final winner claim.",
                "No unrecorded search dimension remains outside the multiplicity contract.",
            ],
            priority=10,
        ),
        action(
            "multiplicity_selection_record",
            "link_record_to_final_selection_claim",
            "multiplicity_control",
            "claim_traceability",
            "Link multiplicity record to the exact final-selection claim.",
            [
                "Claim id and final selection rule.",
                "Candidate shortlist and excluded method rationale.",
                "Post-selection validation evidence.",
            ],
            [
                "The final selection claim has a direct supported-by edge to the multiplicity record.",
                "Winner language cannot appear without the multiplicity citation.",
            ],
            depends_on_action_keys=["freeze_searched_space_and_error_contract"],
            depends_on_gate_ids=["final_method_model_selection_gate"],
            priority=20,
        ),
        action(
            "multiplicity_selection_record",
            "refresh_selection_multiplicity_gate",
            "gate_refresh",
            "artifact_refresh",
            "Refresh selection multiplicity evidence and paper readiness.",
            [
                "Frozen searched-space contract.",
                "Final selected method/model/dataset claim.",
            ],
            [
                "multiplicity_selection_record is no longer blocked.",
                "The paper readiness map links the final winner claim to the multiplicity artifact.",
            ],
            depends_on_action_keys=["link_record_to_final_selection_claim"],
            priority=30,
        ),
        action(
            "final_method_model_selection_gate",
            "freeze_final_selection_eligibility_contract",
            "selection_protocol",
            "claim_contract_design",
            "Freeze final selection eligibility, metric, and tie-break contract.",
            [
                "Eligible datasets and bundles after endpoint/fairness/bounded-support gates.",
                "Primary metric, secondary metric, and tie-break rule.",
                "Handling policy for width pathologies and diagnostic caveats.",
            ],
            [
                "The final selection rule is deterministic and does not inspect post-hoc paper wording.",
                "All excluded rows have a recorded exclusion reason.",
            ],
            depends_on_gate_ids=[
                "endpoint_bounded_support_gate",
                "fairness_population_inference_gate",
            ],
            priority=10,
        ),
        action(
            "final_method_model_selection_gate",
            "apply_final_selection_rule",
            "selection_execution",
            "empirical_selection",
            "Apply the frozen final selection rule to eligible evidence.",
            [
                "Eligible result table.",
                "Multiplicity record.",
                "Post-selection validation results.",
            ],
            [
                "The selected method/model is reproducible from the frozen rule.",
                "Sensitivity results do not contradict the selected claim scope.",
            ],
            depends_on_action_keys=["freeze_final_selection_eligibility_contract"],
            depends_on_gate_ids=["multiplicity_selection_record"],
            priority=20,
        ),
        action(
            "final_method_model_selection_gate",
            "refresh_final_selection_claim_boundary",
            "gate_refresh",
            "artifact_refresh",
            "Refresh final selection claim-boundary audit and paper readiness.",
            [
                "Frozen rule execution artifact.",
                "Multiplicity support artifact.",
                "Updated dataset/bounded/fairness gate statuses.",
            ],
            [
                "final_method_model_selection_gate is no longer blocked.",
                "Final winner language is allowed only within the selected claim scope.",
            ],
            depends_on_action_keys=["apply_final_selection_rule"],
            priority=30,
        ),
        action(
            "dataset_specific_final_gates",
            "refresh_after_global_gate_closure",
            "gate_refresh",
            "artifact_refresh",
            "Refresh dataset-specific final gate after global gates close.",
            [
                "Passed bounded-support gate.",
                "Passed fairness/population gate.",
                "Passed final method/model selection gate.",
                "Passed multiplicity gate.",
            ],
            [
                "Every promoted dataset has no remaining local execution gap.",
                "Dataset-specific final promotion is recomputed after global claim gates pass.",
            ],
            depends_on_gate_ids=[
                "endpoint_bounded_support_gate",
                "fairness_population_inference_gate",
                "final_method_model_selection_gate",
                "multiplicity_selection_record",
            ],
            priority=10,
        ),
        action(
            "dataset_specific_final_gates",
            "promote_dataset_final_results",
            "claim_promotion",
            "claim_traceability",
            "Promote eligible dataset-specific final results.",
            [
                "Refreshed dataset-specific final gate audit.",
                "Claim register update.",
                "Bundle eligibility matrix update.",
            ],
            [
                "At least one dataset-specific final result has all required source artifacts.",
                "Every promoted dataset result has direct KG traceability to the gate evidence.",
            ],
            depends_on_action_keys=["refresh_after_global_gate_closure"],
            priority=20,
        ),
        action(
            "venn_abers_regression_validation_gate",
            "accept_negative_result_disposition_for_manuscript",
            "negative_result_disposition",
            "claim_boundary_resolution",
            "Accept observed Venn-Abers negative evidence for current manuscript reporting.",
            [
                "Venn-Abers validation readiness audit with undercoverage evidence.",
                "Claim-gate matrix showing blocked positive validation requirements.",
                "Negative-evidence disposition audit quarantining Venn-Abers from final selection.",
            ],
            [
                "negative_result_reporting_ready=true.",
                "current_manuscript_positive_validation_required=false.",
                "Positive Venn-Abers interval-validation wording remains explicitly disallowed.",
            ],
            claim_effect=(
                "closes_current_manuscript_negative_result_scope_not_positive_validation"
            ),
            priority=5,
        ),
        action(
            "venn_abers_regression_validation_gate",
            "design_validated_regression_venn_abers_method",
            "method_design",
            "claim_contract_design",
            "Design or cite a validated regression Venn-Abers interval method.",
            [
                "Formal method statement for regression intervals.",
                "Assumptions linking Venn-Abers style calibration to interval validity.",
                "Implementation contract distinct from split conformal fallback.",
            ],
            [
                "The method is not merely a predictive distribution bridge unless interval validity is proven.",
                "The claim gate can distinguish validated Venn-Abers from split fallback.",
            ],
            priority=10,
        ),
        action(
            "venn_abers_regression_validation_gate",
            "run_exact_grid_or_theory_validation_benchmark",
            "validation_protocol",
            "empirical_validation",
            "Run exact-grid or theory-backed Venn-Abers validation benchmark.",
            [
                "Pre-registered datasets, alphas, seeds, and coverage targets.",
                "Panel and run-level coverage against nominal.",
                "Comparison to split fallback and CQR baselines.",
            ],
            [
                "Panel coverage is at or above nominal within the predeclared tolerance.",
                "Run-level failures are explained by allowed finite-sample policy or excluded before claim.",
            ],
            depends_on_action_keys=["design_validated_regression_venn_abers_method"],
            priority=20,
        ),
        action(
            "venn_abers_regression_validation_gate",
            "resolve_upper_boundary_hits",
            "validation_protocol",
            "empirical_validation",
            "Eliminate or formally justify score-grid upper-boundary hits.",
            [
                "Per-row candidate grid hit diagnostics.",
                "Bounded score-grid policy.",
                "Sensitivity to grid resolution and interpolation.",
            ],
            [
                "No promoted Venn-Abers validation run hits the grid upper boundary, or a formal extrapolation policy is validated.",
                "The claim gate records zero unexplained upper-boundary blockers.",
            ],
            depends_on_action_keys=["run_exact_grid_or_theory_validation_benchmark"],
            priority=30,
        ),
        action(
            "venn_abers_regression_validation_gate",
            "validate_ivapd_interval_cp_contract",
            "validation_protocol",
            "method_validation",
            "Validate that IVAPD output is an interval conformal predictor, not only a predictive distribution.",
            [
                "IVAPD interval construction rule.",
                "Coverage proof or empirical calibration evidence.",
                "Contract mapping distribution output to lower/upper interval endpoints.",
            ],
            [
                "ivapd_interval_cp_status is no longer blocked_predictive_distribution_only.",
                "The Venn-Abers claim gate records the IVAPD interval requirement as passed.",
            ],
            depends_on_action_keys=["design_validated_regression_venn_abers_method"],
            priority=40,
        ),
        action(
            "venn_abers_regression_validation_gate",
            "refresh_venn_abers_positive_claim_gate",
            "gate_refresh",
            "artifact_refresh",
            "Refresh Venn-Abers validation readiness, claim gate, and negative disposition.",
            [
                "Validated regression Venn-Abers method evidence.",
                "Exact-grid or theory validation benchmark.",
                "Resolved upper-boundary and IVAPD interval blockers.",
            ],
            [
                "can_support_validated_venn_abers_regression=true.",
                "venn_abers_regression_validation_gate is no longer blocked for the scoped Venn-Abers claim.",
            ],
            depends_on_action_keys=[
                "resolve_upper_boundary_hits",
                "validate_ivapd_interval_cp_contract",
            ],
            priority=50,
        ),
    ]


def enrich_action_status(
    row: dict[str, Any],
    closure_by_gate: dict[str, dict[str, Any]],
    completed_action_statuses: dict[str, str],
) -> dict[str, Any]:
    gate_id = row["gate_id"]
    gate = closure_by_gate.get(gate_id, {})
    positive_ready = bool(gate.get("positive_claim_ready"))
    blocked_dependency_gates = [
        dep
        for dep in row["depends_on_gate_ids"]
        if not bool(closure_by_gate.get(dep, {}).get("positive_claim_ready"))
    ]
    incomplete_action_dependencies = [
        dep
        for dep in row["depends_on_action_ids"]
        if dep not in completed_action_statuses
    ]
    completed_artifact_status = completed_action_statuses.get(row["action_id"])
    protocol_design_artifact_complete = (
        completed_artifact_status == "protocol_design_complete"
    )
    va_negative_disposition_complete = (
        completed_action_statuses.get(VENN_ABERS_NEGATIVE_DISPOSITION_ACTION_ID)
        == "negative_disposition_complete"
    )
    optional_va_positive_validation = (
        gate_id == "venn_abers_regression_validation_gate"
        and row["action_id"] != VENN_ABERS_NEGATIVE_DISPOSITION_ACTION_ID
        and va_negative_disposition_complete
    )

    if positive_ready:
        status = "complete"
        can_execute_now = False
    elif completed_artifact_status:
        status = completed_artifact_status
        can_execute_now = False
    elif optional_va_positive_validation:
        status = "optional_deferred_after_negative_disposition"
        can_execute_now = False
    elif blocked_dependency_gates:
        status = "blocked_by_gate_dependencies"
        can_execute_now = False
    elif incomplete_action_dependencies:
        status = "blocked_by_prior_plan_actions"
        can_execute_now = False
    elif row["action_class"] in {
        "protocol_design",
        "method_design",
        "multiplicity_control",
        "selection_protocol",
    }:
        status = "ready_for_protocol_design"
        can_execute_now = True
    else:
        status = "ready_for_empirical_execution"
        can_execute_now = True
    enriched = dict(row)
    enriched.update(
        {
            "gate_current_status": gate.get("current_status"),
            "gate_positive_claim_ready": positive_ready,
            "gate_scoped_or_negative_path_ready": bool(
                gate.get("scoped_or_negative_path_ready")
            ),
            "blocked_dependency_gate_ids": blocked_dependency_gates,
            "incomplete_action_dependency_ids": incomplete_action_dependencies,
            "protocol_design_artifact_complete": protocol_design_artifact_complete,
            "status": status,
            "can_execute_now": can_execute_now,
            "source_artifacts": gate.get("source_artifacts") or [],
        }
    )
    return enriched


def build_payload(root: Path) -> dict[str, Any]:
    closure_map = read_json(root / PAPER_GATE_CLOSURE)
    paper_readiness = read_json(root / PAPER_READINESS)
    protocol_bundle = read_json(root / PAPER_GATE_PROTOCOL_DESIGN_BUNDLE)
    sampling_policy = read_json(root / FAIRNESS_SAMPLING_WEIGHT_POLICY)
    fairness_group_diagnostic = read_json(root / FAIRNESS_GROUP_DIAGNOSTIC_AUDIT)
    fairness_group_multiplicity_scope = read_json(
        root / FAIRNESS_GROUP_MULTIPLICITY_SCOPE
    )
    fairness_population_readiness = read_json(root / FAIRNESS_POPULATION_READINESS)
    bounded_support_endpoint_closure = read_json(root / BOUNDED_SUPPORT_ENDPOINT_CLOSURE)
    bounded_support_positive_validation = read_json(
        root / BOUNDED_SUPPORT_POSITIVE_VALIDATION
    )
    venn_abers_negative_disposition = read_json(root / VENN_ABERS_NEGATIVE_DISPOSITION)
    closure_by_gate = closure_rows_by_gate(closure_map)
    readiness_by_gate = readiness_status_by_gate(paper_readiness)
    completed_sampling_policy_action_ids = completed_sampling_weight_policy_action_ids(
        sampling_policy
    )
    completed_action_statuses = {
        action_id: "protocol_design_complete"
        for action_id in (
            completed_protocol_design_action_ids(protocol_bundle)
            | completed_sampling_policy_action_ids
        )
    }
    completed_action_statuses.update(
        completed_fairness_group_diagnostic_action_statuses(
            fairness_group_diagnostic
        )
    )
    completed_action_statuses.update(
        completed_fairness_group_multiplicity_scope_action_statuses(
            fairness_group_multiplicity_scope
        )
    )
    fairness_population_refresh_action_statuses = (
        completed_fairness_population_refresh_action_statuses(
            fairness_population_readiness
        )
    )
    completed_action_statuses.update(fairness_population_refresh_action_statuses)
    endpoint_natural_domain_action_statuses = (
        completed_endpoint_natural_domain_audit_action_statuses(
            bounded_support_endpoint_closure
        )
    )
    completed_action_statuses.update(endpoint_natural_domain_action_statuses)
    bounded_support_positive_validation_action_statuses = (
        completed_bounded_support_positive_validation_action_statuses(
            bounded_support_positive_validation
        )
    )
    completed_action_statuses.update(
        bounded_support_positive_validation_action_statuses
    )
    bounded_support_refresh_action_statuses = (
        completed_bounded_support_refresh_action_statuses(
            positive_validation=bounded_support_positive_validation,
            endpoint_closure=bounded_support_endpoint_closure,
        )
    )
    completed_action_statuses.update(bounded_support_refresh_action_statuses)
    completed_action_statuses.update(
        completed_venn_abers_negative_disposition_action_statuses(
            venn_abers_negative_disposition
        )
    )

    rows = [
        enrich_action_status(row, closure_by_gate, completed_action_statuses)
        for row in action_templates()
    ]
    rows.sort(key=lambda row: (row["priority"], row["gate_id"], row["action_id"]))

    gate_ids = sorted({row["gate_id"] for row in rows})
    blocked_gate_ids = sorted(
        gate_id
        for gate_id in gate_ids
        if status_is_blocked(
            closure_by_gate.get(gate_id, {}).get("current_status")
            or readiness_by_gate.get(gate_id)
        )
    )
    status_counts = Counter(row["status"] for row in rows)
    class_counts = Counter(row["action_class"] for row in rows)
    stage_counts = Counter(row["stage"] for row in rows)
    ready_actions = [row for row in rows if row["can_execute_now"]]
    blocked_actions = [
        row
        for row in rows
        if row["status"]
        in {"blocked_by_gate_dependencies", "blocked_by_prior_plan_actions"}
    ]

    failed_checks: list[dict[str, Any]] = []
    if not gate_ids:
        failed_checks.append(
            {"check_id": "paper_gate_execution_plan_has_gate_rows", "status": "fail"}
        )
    if len(blocked_gate_ids) != int(
        (closure_map.get("summary") or {}).get("blocked_gate_count") or len(blocked_gate_ids)
    ):
        failed_checks.append(
            {
                "check_id": "blocked_gate_count_matches_closure_map",
                "status": "fail",
            }
        )
    for gate_id in blocked_gate_ids:
        if not any(row["gate_id"] == gate_id for row in rows):
            failed_checks.append(
                {
                    "check_id": "each_blocked_gate_has_plan_action",
                    "status": "fail",
                    "gate_id": gate_id,
                }
            )

    overall_status = (
        "paper_gate_closure_execution_plan_failed"
        if failed_checks
        else "paper_gate_closure_execution_plan_ready"
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
            "gate_count": len(gate_ids),
            "blocked_gate_count": len(blocked_gate_ids),
            "action_count": len(rows),
            "ready_action_count": len(ready_actions),
            "blocked_action_count": len(blocked_actions),
            "ready_for_protocol_design_action_count": status_counts.get(
                "ready_for_protocol_design", 0
            ),
            "ready_for_empirical_execution_action_count": status_counts.get(
                "ready_for_empirical_execution", 0
            ),
            "protocol_design_complete_action_count": status_counts.get(
                "protocol_design_complete", 0
            ),
            "empirical_execution_complete_action_count": status_counts.get(
                "empirical_execution_complete", 0
            ),
            "multiplicity_control_complete_action_count": status_counts.get(
                "multiplicity_control_complete", 0
            ),
            "gate_refresh_complete_no_fairness_claim_action_count": status_counts.get(
                "gate_refresh_complete_no_fairness_claim", 0
            ),
            "empirical_validation_complete_no_bounded_support_claim_action_count": (
                status_counts.get(
                    "empirical_validation_complete_no_bounded_support_claim", 0
                )
            ),
            "gate_refresh_complete_no_bounded_support_claim_action_count": (
                status_counts.get("gate_refresh_complete_no_bounded_support_claim", 0)
            ),
            "blocked_by_gate_dependencies_action_count": status_counts.get(
                "blocked_by_gate_dependencies", 0
            ),
            "blocked_by_prior_plan_actions_action_count": status_counts.get(
                "blocked_by_prior_plan_actions", 0
            ),
            "complete_action_count": status_counts.get("complete", 0),
            "can_close_any_positive_gate_now": any(
                bool(closure_by_gate.get(gate_id, {}).get("positive_claim_ready"))
                for gate_id in gate_ids
            ),
            "action_status_counts": dict(sorted(status_counts.items())),
            "action_class_counts": dict(sorted(class_counts.items())),
            "action_stage_counts": dict(sorted(stage_counts.items())),
            "protocol_design_bundle_status": (protocol_bundle.get("summary") or {}).get(
                "overall_status"
            ),
            "protocol_design_bundle_completed_action_count": (
                (protocol_bundle.get("summary") or {}).get(
                    "completed_protocol_design_action_count"
                )
            ),
            "fairness_sampling_weight_policy_status": (
                (sampling_policy.get("summary") or {}).get("overall_status")
            ),
            "fairness_sampling_weight_policy_complete_action_count": len(
                completed_sampling_policy_action_ids
            ),
            "fairness_group_diagnostic_audit_status": (
                (fairness_group_diagnostic.get("summary") or {}).get("overall_status")
            ),
            "fairness_group_diagnostic_complete_action_count": (
                1
                if completed_fairness_group_diagnostic_action_statuses(
                    fairness_group_diagnostic
                )
                else 0
            ),
            "fairness_group_multiplicity_scope_status": (
                (fairness_group_multiplicity_scope.get("summary") or {}).get(
                    "overall_status"
                )
            ),
            "fairness_group_multiplicity_scope_complete_action_count": (
                1
                if completed_fairness_group_multiplicity_scope_action_statuses(
                    fairness_group_multiplicity_scope
                )
                else 0
            ),
            "current_manuscript_fairness_population_claim_ready": (
                (fairness_group_multiplicity_scope.get("summary") or {}).get(
                    "current_manuscript_fairness_population_claim_ready"
                )
            ),
            "fairness_population_refresh_status": (
                (fairness_population_readiness.get("summary") or {}).get(
                    "overall_status"
                )
            ),
            "fairness_population_refresh_complete_action_count": len(
                fairness_population_refresh_action_statuses
            ),
            "fairness_population_ready_bundle_count": (
                (fairness_population_readiness.get("summary") or {}).get(
                    "population_fairness_ready_bundle_count"
                )
            ),
            "endpoint_natural_domain_audit_status": (
                (bounded_support_endpoint_closure.get("summary") or {}).get(
                    "overall_status"
                )
            ),
            "endpoint_natural_domain_audit_complete_action_count": len(
                endpoint_natural_domain_action_statuses
            ),
            "endpoint_natural_domain_open_backfill_bundle_count": (
                (bounded_support_endpoint_closure.get("summary") or {}).get(
                    "open_endpoint_count_backfill_bundle_count"
                )
            ),
            "current_manuscript_bounded_support_validity_claim_ready": (
                (bounded_support_endpoint_closure.get("summary") or {}).get(
                    "current_manuscript_bounded_support_validity_claim_ready"
                )
            ),
            "bounded_support_positive_validation_status": (
                (bounded_support_positive_validation.get("summary") or {}).get(
                    "overall_status"
                )
            ),
            "bounded_support_positive_validation_complete_action_count": len(
                bounded_support_positive_validation_action_statuses
            ),
            "bounded_support_positive_validation_acceptance_failed_count": (
                (bounded_support_positive_validation.get("summary") or {}).get(
                    "positive_acceptance_failed_count"
                )
            ),
            "bounded_support_positive_validation_interval_score_missing_bundle_count": (
                (bounded_support_positive_validation.get("summary") or {}).get(
                    "interval_score_metrics_missing_bundle_count"
                )
            ),
            "bounded_support_claim_refresh_complete_action_count": len(
                bounded_support_refresh_action_statuses
            ),
            "venn_abers_negative_disposition_status": (
                (venn_abers_negative_disposition.get("summary") or {}).get(
                    "overall_status"
                )
            ),
            "venn_abers_negative_disposition_complete_action_count": (
                1
                if completed_venn_abers_negative_disposition_action_statuses(
                    venn_abers_negative_disposition
                )
                else 0
            ),
            "current_manuscript_positive_venn_abers_validation_required": (
                (venn_abers_negative_disposition.get("summary") or {}).get(
                    "current_manuscript_positive_validation_required"
                )
            ),
            "next_executable_action_ids": [
                row["action_id"] for row in sorted(ready_actions, key=lambda item: item["priority"])[:8]
            ],
            "failed_check_count": len(failed_checks),
        },
        "claim_boundaries": [
            "This execution plan does not close paper gates or promote final claims.",
            "Ready actions are protocol or empirical work items; their outputs must be generated and audited before any positive claim changes.",
            "Scoped diagnostic and negative-result routes remain separate from full positive-claim closure.",
        ],
        "failed_checks": failed_checks,
        "action_rows": rows,
        "sources": {
            "paper_gate_closure_map": rel(root / PAPER_GATE_CLOSURE, root),
            "paper_readiness_map": rel(root / PAPER_READINESS, root),
            "paper_gate_protocol_design_bundle": rel(
                root / PAPER_GATE_PROTOCOL_DESIGN_BUNDLE, root
            ),
            "fairness_sampling_weight_policy": rel(
                root / FAIRNESS_SAMPLING_WEIGHT_POLICY, root
            ),
            "fairness_group_diagnostic_audit": rel(
                root / FAIRNESS_GROUP_DIAGNOSTIC_AUDIT, root
            ),
            "fairness_group_multiplicity_scope": rel(
                root / FAIRNESS_GROUP_MULTIPLICITY_SCOPE, root
            ),
            "bounded_support_endpoint_closure_audit": rel(
                root / BOUNDED_SUPPORT_ENDPOINT_CLOSURE, root
            ),
            "venn_abers_negative_evidence_disposition": rel(
                root / VENN_ABERS_NEGATIVE_DISPOSITION, root
            ),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Paper Gate Closure Execution Plan",
        "",
        "This is a planning artifact for blocked positive paper gates. It does not promote any claim.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Blocked gates: {summary['blocked_gate_count']} / {summary['gate_count']}",
        f"- Actions: {summary['action_count']}",
        f"- Ready actions: {summary['ready_action_count']}",
        f"- Blocked actions: {summary['blocked_action_count']}",
        f"- Protocol-design complete actions: {summary['protocol_design_complete_action_count']}",
        f"- Empirical-execution complete actions: {summary['empirical_execution_complete_action_count']}",
        f"- Multiplicity-control complete actions: {summary['multiplicity_control_complete_action_count']}",
        f"- Fairness group multiplicity-scope complete actions: {summary['fairness_group_multiplicity_scope_complete_action_count']}",
        f"- Current manuscript fairness population claim ready: `{summary['current_manuscript_fairness_population_claim_ready']}`",
        f"- Endpoint natural-domain audit complete actions: {summary['endpoint_natural_domain_audit_complete_action_count']}",
        f"- Current manuscript bounded-support validity claim ready: `{summary['current_manuscript_bounded_support_validity_claim_ready']}`",
        f"- Venn-Abers negative-disposition complete actions: {summary['venn_abers_negative_disposition_complete_action_count']}",
        f"- Current manuscript requires positive Venn-Abers validation: `{summary['current_manuscript_positive_venn_abers_validation_required']}`",
        f"- Can close any positive gate now: `{summary['can_close_any_positive_gate_now']}`",
        f"- Action status counts: `{summary['action_status_counts']}`",
        "",
        "## Next Executable Actions",
        "",
    ]
    if summary["next_executable_action_ids"]:
        for action_id in summary["next_executable_action_ids"]:
            lines.append(f"- `{action_id}`")
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Action Rows",
            "",
            "| Action | Gate | Class | Status | Can Execute Now |",
            "|---|---|---|---:|---:|",
        ]
    )
    for row in payload["action_rows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['action_id']}`",
                    f"`{row['gate_id']}`",
                    f"`{row['action_class']}`",
                    f"`{row['status']}`",
                    f"`{row['can_execute_now']}`",
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
