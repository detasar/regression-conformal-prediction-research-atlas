"""Run the retrospective scientific-quality gate for regression CP artifacts.

This orchestrator is intentionally about methodology hygiene, not model
training. It refreshes the existing retrospective audits in a deterministic
order and writes a durable manifest after every step so interrupted runs leave a
usable progress record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_retrospective_quality_gate_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = REPORT_DIR / "retrospective_quality_gate.json"
KG_QUALITY_OUT = Path(
    "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"
)
DIRTY_SNAPSHOT_SCHEMA = "cpfi_retrospective_dirty_snapshot_v2"
DIRTY_PATH_SAMPLE_LIMIT = 50
DIRTY_RELEVANT_PATH_PREFIXES = (
    "cpfi/",
    "experiments/regression/catalogs/",
    "experiments/regression/configs/",
    "experiments/regression/method_specs/",
    "experiments/regression/policies/",
    "experiments/regression/scripts/",
    "tests/",
    "pyproject.toml",
    "requirements",
    "environment",
    "setup.cfg",
    "setup.py",
)

CLAIM_BOUNDARIES = [
    "This quality gate refreshes retrospective methodology artifacts; it is not a new model-performance result.",
    "A passing hard-leakage gate means no row-id, split-group, or recorded feature-leakage violation was detected in scanned artifacts.",
    "Feature-leakage conclusions remain bounded by available prediction metadata and documented loader/drop policies.",
    "Endpoint v2 closure is raw endpoint-reconstruction hygiene for completed ledger rows, not bounded-support validity or production readiness.",
    "Venn-Abers regression rows remain diagnostic or fallback evidence only; this gate must not promote them to validated regression Venn-Abers.",
    "The Venn-Abers grid expansion plan is a resumable work queue, not empirical validation evidence.",
    "The Venn-Abers grid failure-mode decomposition explains blockers; it is not validation evidence.",
    "The Venn-Abers claim-gate matrix joins existing diagnostics into claim-control evidence; it is not a new positive Venn-Abers result.",
    "CQR rows remain fixed-backend evidence unless a backend sweep artifact explicitly says otherwise.",
]


@dataclass(frozen=True)
class GateStep:
    step_id: str
    family: str
    description: str
    args: tuple[str, ...]
    outputs: tuple[str, ...]
    required: bool = True


STEPS: tuple[GateStep, ...] = (
    GateStep(
        "cross_run_integrity",
        "methodology",
        "Refresh report-level split, endpoint, leakage, and claim matrix.",
        (
            "experiments/regression/scripts/audit_cross_run_integrity.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "cross_run_integrity_audit.json"),
            str(REPORT_DIR / "cross_run_integrity_audit.md"),
        ),
    ),
    GateStep(
        "duplicate_split_backlog",
        "split",
        "Refresh duplicate-signature caveat backlog.",
        (
            "experiments/regression/scripts/build_duplicate_split_caveat_backlog.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "duplicate_split_caveat_backlog.json"),
            str(REPORT_DIR / "duplicate_split_caveat_backlog.md"),
        ),
    ),
    GateStep(
        "paired_duplicate_sensitivity",
        "split",
        "Refresh paired raw-vs-dedup sensitivity evidence where available.",
        (
            "experiments/regression/scripts/build_paired_duplicate_sensitivity_audit.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "paired_duplicate_sensitivity_audit.json"),
            str(REPORT_DIR / "paired_duplicate_sensitivity_audit.md"),
        ),
    ),
    GateStep(
        "feature_leakage_metadata_triage",
        "feature_leakage",
        "Refresh metadata-completeness limits for feature-leakage sidecars.",
        (
            "experiments/regression/scripts/audit_feature_leakage_metadata_completeness.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "feature_leakage_metadata_completeness_triage.json"),
            str(REPORT_DIR / "feature_leakage_metadata_completeness_triage.md"),
        ),
    ),
    GateStep(
        "integrity_remediation_backlog",
        "methodology",
        "Refresh the deterministic methodology-debt queue.",
        (
            "experiments/regression/scripts/build_integrity_remediation_backlog.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "integrity_remediation_backlog.json"),
            str(REPORT_DIR / "integrity_remediation_backlog.md"),
        ),
    ),
    GateStep(
        "endpoint_backfill_feasibility",
        "endpoint",
        "Refresh which legacy endpoint audits are ready for v2 reconstruction.",
        (
            "experiments/regression/scripts/audit_endpoint_schema_backfill_feasibility.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "endpoint_schema_backfill_feasibility.json"),
            str(REPORT_DIR / "endpoint_schema_backfill_feasibility.md"),
        ),
    ),
    GateStep(
        "retrospective_methodology_controls",
        "methodology",
        "Refresh the compact pass/caveat/fail scientific-control matrix.",
        (
            "experiments/regression/scripts/audit_retrospective_methodology_controls.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "retrospective_methodology_controls.json"),
            str(REPORT_DIR / "retrospective_methodology_controls.md"),
        ),
    ),
    GateStep(
        "methodology_sanity",
        "methodology",
        "Refresh high-level methodology and claim-boundary findings.",
        (
            "experiments/regression/scripts/audit_methodology_sanity.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "sanity_audit.json"),
            str(REPORT_DIR / "sanity_audit.md"),
        ),
    ),
    GateStep(
        "manuscript_manifest_completeness",
        "manuscript",
        "Refresh manuscript evidence-manifest completeness checks.",
        (
            "experiments/regression/scripts/audit_manuscript_manifest_completeness.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "manuscript_manifest_completeness_audit.json"),
            str(REPORT_DIR / "manuscript_manifest_completeness_audit.md"),
        ),
    ),
    GateStep(
        "manuscript_claim_register_consistency",
        "manuscript",
        "Refresh manuscript claim-register JSON/Markdown consistency checks.",
        (
            "experiments/regression/scripts/audit_manuscript_claim_register_consistency.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "manuscript_claim_register_consistency_audit.json"),
            str(REPORT_DIR / "manuscript_claim_register_consistency_audit.md"),
        ),
    ),
    GateStep(
        "final_selection_claim_boundary",
        "manuscript",
        "Refresh final-selection and broad-claim blocked-boundary checks.",
        (
            "experiments/regression/scripts/audit_final_selection_claim_boundary.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "final_selection_claim_boundary_audit.json"),
            str(REPORT_DIR / "final_selection_claim_boundary_audit.md"),
        ),
    ),
    GateStep(
        "venn_abers_validation_readiness",
        "manuscript",
        "Refresh Venn-Abers regression validation blocked-boundary checks.",
        (
            "experiments/regression/scripts/audit_venn_abers_validation_readiness.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "venn_abers_validation_readiness_audit.json"),
            str(REPORT_DIR / "venn_abers_validation_readiness_audit.md"),
        ),
    ),
    GateStep(
        "venn_abers_grid_ivapd_validation_protocol",
        "manuscript",
        "Refresh exact-grid and IVAPD validation protocol claim-boundary checks.",
        (
            "experiments/regression/scripts/audit_venn_abers_grid_ivapd_validation_protocol.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "venn_abers_grid_ivapd_validation_protocol.json"),
            str(REPORT_DIR / "venn_abers_grid_ivapd_validation_protocol.md"),
        ),
    ),
    GateStep(
        "venn_abers_grid_expansion_plan",
        "manuscript",
        "Refresh the resumable row-level score-grid expansion plan.",
        (
            "experiments/regression/scripts/build_venn_abers_grid_expansion_plan.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "venn_abers_grid_expansion_plan.json"),
            str(REPORT_DIR / "venn_abers_grid_expansion_plan.md"),
        ),
    ),
    GateStep(
        "venn_abers_grid_failure_mode_decomposition",
        "manuscript",
        "Refresh completed score-grid blocker and no-claim failure-mode decomposition.",
        (
            "experiments/regression/scripts/analyze_venn_abers_grid_failure_modes.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "venn_abers_grid_failure_mode_decomposition.json"),
            str(REPORT_DIR / "venn_abers_grid_failure_mode_decomposition.md"),
        ),
    ),
    GateStep(
        "method_literature_coverage",
        "methodology",
        "Refresh regression conformal method-literature coverage and tracked-gap audit.",
        (
            "experiments/regression/scripts/audit_method_literature_coverage.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "method_literature_coverage_audit.json"),
            str(REPORT_DIR / "method_literature_coverage_audit.md"),
        ),
    ),
    GateStep(
        "manuscript_evidence_view",
        "manuscript",
        "Refresh claim-to-manifest-to-endpoint manuscript extraction view.",
        (
            "experiments/regression/scripts/build_manuscript_evidence_view.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/evidence_view.json",
            "experiments/regression/manuscript/evidence_view.md",
        ),
    ),
    GateStep(
        "fairness_sampling_weight_policy",
        "manuscript",
        "Refresh fairness sampling/weighting policy contract.",
        (
            "experiments/regression/scripts/build_fairness_sampling_weight_policy.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/fairness_sampling_weight_policy.json",
            "experiments/regression/manuscript/fairness_sampling_weight_policy.md",
        ),
    ),
    GateStep(
        "fairness_group_diagnostic_audit",
        "manuscript",
        "Refresh diagnostic group counts, missingness, coverage gaps, width gaps, and uncertainty evidence.",
        (
            "experiments/regression/scripts/build_fairness_group_diagnostic_audit.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "fairness_group_diagnostic_audit.json"),
            str(REPORT_DIR / "fairness_group_diagnostic_audit.md"),
        ),
    ),
    GateStep(
        "fairness_group_multiplicity_scope",
        "manuscript",
        "Refresh diagnostic group-comparison multiplicity scope and claim-register citation.",
        (
            "experiments/regression/scripts/build_fairness_group_multiplicity_scope.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/fairness_group_multiplicity_scope.json",
            "experiments/regression/manuscript/fairness_group_multiplicity_scope.md",
        ),
    ),
    GateStep(
        "fairness_population_readiness",
        "manuscript",
        "Refresh fairness/population diagnostic-vs-claim boundary checks.",
        (
            "experiments/regression/scripts/audit_fairness_population_readiness.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "fairness_population_readiness_audit.json"),
            str(REPORT_DIR / "fairness_population_readiness_audit.md"),
        ),
    ),
    GateStep(
        "publication_methodology_readiness",
        "manuscript",
        "Refresh publication-methodology readiness and claim-boundary checks.",
        (
            "experiments/regression/scripts/audit_publication_methodology_readiness.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "publication_methodology_audit.json"),
            str(REPORT_DIR / "publication_methodology_audit.md"),
        ),
    ),
    GateStep(
        "venn_abers_claim_gate_matrix",
        "manuscript",
        "Refresh joined Venn-Abers positive-claim requirement matrix.",
        (
            "experiments/regression/scripts/audit_venn_abers_claim_gate_matrix.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "venn_abers_claim_gate_matrix.json"),
            str(REPORT_DIR / "venn_abers_claim_gate_matrix.md"),
        ),
    ),
    GateStep(
        "selection_multiplicity_protocol",
        "manuscript",
        "Refresh final-selection ranking and multiplicity accounting protocol.",
        (
            "experiments/regression/scripts/build_selection_multiplicity_protocol.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/selection_multiplicity_protocol.json",
            "experiments/regression/manuscript/selection_multiplicity_protocol.md",
        ),
    ),
    GateStep(
        "bounded_support_protocol",
        "manuscript",
        "Refresh bounded-support and endpoint-domain claim-boundary protocol.",
        (
            "experiments/regression/scripts/build_bounded_support_protocol.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/bounded_support_protocol.json",
            "experiments/regression/manuscript/bounded_support_protocol.md",
        ),
    ),
    GateStep(
        "target_domain_provenance",
        "manuscript",
        "Refresh source-backed target-domain natural-bound provenance catalog.",
        (
            "experiments/regression/scripts/build_target_domain_provenance_catalog.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/catalogs/target_domain_provenance.json",
            "experiments/regression/catalogs/target_domain_provenance.md",
        ),
    ),
    GateStep(
        "external_source_discovery_watchlist",
        "data",
        "Refresh external source-family discovery coverage watchlist.",
        (
            "experiments/regression/scripts/build_external_source_discovery_watchlist.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/catalogs/external_source_discovery_watchlist.json",
            "experiments/regression/catalogs/external_source_discovery_watchlist.md",
        ),
    ),
    GateStep(
        "bounded_support_posthandling_validation",
        "manuscript",
        "Refresh manuscript-wide bounded-support post-handling validation metrics.",
        (
            "experiments/regression/scripts/build_bounded_support_posthandling_validation.py",
            "--repo-root",
            ".",
            "--state-dir",
            "experiments/regression/results/_bounded_support_posthandling_validation_state/manuscript_bounded_support_20260701",
            "--progress-every",
            "0",
        ),
        (
            "experiments/regression/manuscript/bounded_support_posthandling_validation.json",
            "experiments/regression/manuscript/bounded_support_posthandling_validation.md",
        ),
    ),
    GateStep(
        "bounded_support_dataset_audit",
        "manuscript",
        "Refresh dataset-level bounded-support and endpoint-domain audit.",
        (
            "experiments/regression/scripts/build_bounded_support_dataset_audit.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/bounded_support_dataset_audit.json",
            "experiments/regression/manuscript/bounded_support_dataset_audit.md",
        ),
    ),
    GateStep(
        "bounded_support_endpoint_closure",
        "manuscript",
        "Refresh endpoint-policy closure audit for natural-domain endpoint excursions.",
        (
            "experiments/regression/scripts/audit_bounded_support_endpoint_closure.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "bounded_support_endpoint_closure_audit.json"),
            str(REPORT_DIR / "bounded_support_endpoint_closure_audit.md"),
        ),
    ),
    GateStep(
        "bounded_support_positive_validation_protocol",
        "manuscript",
        "Run the bounded-support positive-validity protocol and preserve no-claim evidence.",
        (
            "experiments/regression/scripts/run_bounded_support_positive_validation_protocol.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/bounded_support_positive_validation_protocol.json",
            "experiments/regression/manuscript/bounded_support_positive_validation_protocol.md",
        ),
    ),
    GateStep(
        "experiment_accounting",
        "methodology",
        "Refresh raw, canonical, publication, manuscript, and Venn-Abers row accounting.",
        (
            "experiments/regression/scripts/audit_experiment_accounting.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "experiment_accounting_audit.json"),
            str(REPORT_DIR / "experiment_accounting_audit.md"),
        ),
    ),
    GateStep(
        "method_performance_synthesis",
        "methodology",
        "Refresh descriptive method-performance synthesis over the audited publication surface.",
        (
            "experiments/regression/scripts/build_method_performance_synthesis.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "method_performance_synthesis.json"),
            str(REPORT_DIR / "method_performance_synthesis.md"),
        ),
    ),
    GateStep(
        "method_selection_candidate_audit",
        "methodology",
        "Refresh candidate shortlist and paired diagnostics without promoting final selection.",
        (
            "experiments/regression/scripts/build_method_selection_candidate_audit.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "method_selection_candidate_audit.json"),
            str(REPORT_DIR / "method_selection_candidate_audit.md"),
        ),
    ),
    GateStep(
        "method_selection_robustness_audit",
        "methodology",
        "Refresh candidate-selection stability diagnostics without promoting final selection.",
        (
            "experiments/regression/scripts/build_method_selection_robustness_audit.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "method_selection_robustness_audit.json"),
            str(REPORT_DIR / "method_selection_robustness_audit.md"),
        ),
    ),
    GateStep(
        "method_selection_alpha_expansion_plan",
        "methodology",
        "Refresh alpha-support expansion work queue for method-selection robustness.",
        (
            "experiments/regression/scripts/build_method_selection_alpha_expansion_plan.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "method_selection_alpha_expansion_plan.json"),
            str(REPORT_DIR / "method_selection_alpha_expansion_plan.md"),
        ),
    ),
    GateStep(
        "method_selection_post_selection_validation_batch",
        "methodology",
        "Refresh independent post-selection validation batch manifest.",
        (
            "experiments/regression/scripts/build_method_selection_post_selection_validation_batch.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "method_selection_post_selection_validation_batch.json"),
            str(REPORT_DIR / "method_selection_post_selection_validation_batch.md"),
        ),
    ),
    GateStep(
        "method_selection_post_selection_validation_results",
        "methodology",
        "Refresh completed post-selection validation result synthesis.",
        (
            "experiments/regression/scripts/build_method_selection_post_selection_validation_results.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "method_selection_post_selection_validation_results.json"),
            str(REPORT_DIR / "method_selection_post_selection_validation_results.md"),
        ),
    ),
    GateStep(
        "selection_multiplicity_evidence_record",
        "manuscript",
        "Refresh paper-facing selection and multiplicity evidence record.",
        (
            "experiments/regression/scripts/build_selection_multiplicity_evidence_record.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/selection_multiplicity_evidence_record.json",
            "experiments/regression/manuscript/selection_multiplicity_evidence_record.md",
        ),
    ),
    GateStep(
        "method_selection_alpha_expansion_execution",
        "methodology",
        "Audit alpha-expansion execution closure against completed ledgers.",
        (
            "experiments/regression/scripts/audit_method_selection_alpha_expansion_execution.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "method_selection_alpha_expansion_execution_audit.json"),
            str(REPORT_DIR / "method_selection_alpha_expansion_execution_audit.md"),
        ),
    ),
    GateStep(
        "method_selection_inferential_audit",
        "methodology",
        "Refresh inferential method-selection diagnostics without final selection.",
        (
            "experiments/regression/scripts/build_method_selection_inferential_audit.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "method_selection_inferential_audit.json"),
            str(REPORT_DIR / "method_selection_inferential_audit.md"),
        ),
    ),
    GateStep(
        "manuscript_readiness_map",
        "manuscript",
        "Refresh paper-readiness map from final-claim gates and manuscript evidence.",
        (
            "experiments/regression/scripts/build_manuscript_readiness_map.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/paper_readiness_map.json",
            "experiments/regression/manuscript/paper_readiness_map.md",
        ),
    ),
    GateStep(
        "manuscript_bundle_eligibility_matrix",
        "manuscript",
        "Refresh bundle-level manuscript table eligibility matrix.",
        (
            "experiments/regression/scripts/build_manuscript_bundle_eligibility_matrix.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/bundle_eligibility_matrix.json",
            "experiments/regression/manuscript/bundle_eligibility_matrix.md",
        ),
    ),
    GateStep(
        "dataset_specific_final_gate_audit",
        "manuscript",
        "Refresh dataset-specific final-result gate audit.",
        (
            "experiments/regression/scripts/audit_dataset_specific_final_gate_readiness.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "dataset_specific_final_gate_audit.json"),
            str(REPORT_DIR / "dataset_specific_final_gate_audit.md"),
        ),
    ),
    GateStep(
        "dataset_final_gate_post_selection_validation_bridge",
        "manuscript",
        "Refresh dataset-final post-selection validation bridge manifest.",
        (
            "experiments/regression/scripts/build_dataset_final_gate_post_selection_validation_bridge.py",
            "--repo-root",
            ".",
        ),
        (
            str(
                REPORT_DIR / "dataset_final_gate_post_selection_validation_bridge.json"
            ),
            str(REPORT_DIR / "dataset_final_gate_post_selection_validation_bridge.md"),
        ),
    ),
    GateStep(
        "dataset_final_gate_post_selection_validation_bridge_results",
        "manuscript",
        "Refresh completed dataset-final bridge validation result synthesis.",
        (
            "experiments/regression/scripts/build_method_selection_post_selection_validation_results.py",
            "--repo-root",
            ".",
            "--batch",
            str(
                REPORT_DIR / "dataset_final_gate_post_selection_validation_bridge.json"
            ),
            "--out",
            str(
                REPORT_DIR
                / "dataset_final_gate_post_selection_validation_bridge_results.json"
            ),
        ),
        (
            str(
                REPORT_DIR
                / "dataset_final_gate_post_selection_validation_bridge_results.json"
            ),
            str(
                REPORT_DIR
                / "dataset_final_gate_post_selection_validation_bridge_results.md"
            ),
        ),
    ),
    GateStep(
        "main_result_candidate_bundle_plan",
        "manuscript",
        "Refresh main-result candidate bundle plan without final promotions.",
        (
            "experiments/regression/scripts/build_main_result_candidate_bundle_plan.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "main_result_candidate_bundle_plan.json"),
            str(REPORT_DIR / "main_result_candidate_bundle_plan.md"),
        ),
    ),
    GateStep(
        "main_result_candidate_bundle_results",
        "manuscript",
        "Refresh completed main-result candidate bundle result synthesis.",
        (
            "experiments/regression/scripts/build_main_result_candidate_bundle_results.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "main_result_candidate_bundle_results.json"),
            str(REPORT_DIR / "main_result_candidate_bundle_results.md"),
        ),
    ),
    GateStep(
        "main_result_candidate_post_run_closure",
        "manuscript",
        "Refresh post-run closure audit for main-result candidate bundles.",
        (
            "experiments/regression/scripts/audit_main_result_candidate_post_run_closure.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "main_result_candidate_post_run_closure_audit.json"),
            str(REPORT_DIR / "main_result_candidate_post_run_closure_audit.md"),
        ),
    ),
    GateStep(
        "dataset_final_gate_remediation_plan",
        "manuscript",
        "Refresh dataset-final remediation plan and action-scope semantics.",
        (
            "experiments/regression/scripts/build_dataset_final_gate_remediation_plan.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "dataset_final_gate_remediation_plan.json"),
            str(REPORT_DIR / "dataset_final_gate_remediation_plan.md"),
        ),
    ),
    GateStep(
        "venn_abers_negative_evidence_disposition",
        "manuscript",
        "Audit Venn-Abers negative evidence disposition across selection and manuscript surfaces.",
        (
            "experiments/regression/scripts/audit_venn_abers_negative_evidence_disposition.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "venn_abers_negative_evidence_disposition_audit.json"),
            str(REPORT_DIR / "venn_abers_negative_evidence_disposition_audit.md"),
        ),
    ),
    GateStep(
        "publication_methodology_readiness_after_venn_abers_disposition",
        "manuscript",
        "Refresh publication-methodology readiness after Venn-Abers negative-result disposition.",
        (
            "experiments/regression/scripts/audit_publication_methodology_readiness.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "publication_methodology_audit.json"),
            str(REPORT_DIR / "publication_methodology_audit.md"),
        ),
    ),
    GateStep(
        "duplicate_sensitivity_closure",
        "split",
        "Refresh scoped duplicate-sensitivity closure and claim-boundary checks after publication audit.",
        (
            "experiments/regression/scripts/audit_duplicate_sensitivity_closure.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "duplicate_sensitivity_closure_audit.json"),
            str(REPORT_DIR / "duplicate_sensitivity_closure_audit.md"),
        ),
    ),
    GateStep(
        "manuscript_readiness_map_after_venn_abers_disposition",
        "manuscript",
        "Refresh paper-readiness map after Venn-Abers negative-result disposition.",
        (
            "experiments/regression/scripts/build_manuscript_readiness_map.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/paper_readiness_map.json",
            "experiments/regression/manuscript/paper_readiness_map.md",
        ),
    ),
    GateStep(
        "paper_gate_closure_map",
        "manuscript",
        "Refresh positive-claim versus scoped/negative manuscript gate closure map.",
        (
            "experiments/regression/scripts/build_paper_gate_closure_map.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/paper_gate_closure_map.json",
            "experiments/regression/manuscript/paper_gate_closure_map.md",
        ),
    ),
    GateStep(
        "paper_gate_closure_execution_plan",
        "manuscript",
        "Refresh executable protocol plan for closing blocked positive paper gates.",
        (
            "experiments/regression/scripts/build_paper_gate_closure_execution_plan.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/paper_gate_closure_execution_plan.json",
            "experiments/regression/manuscript/paper_gate_closure_execution_plan.md",
        ),
    ),
    GateStep(
        "paper_gate_protocol_design_bundle",
        "manuscript",
        "Refresh completed protocol-design contracts for initially ready paper-gate actions.",
        (
            "experiments/regression/scripts/build_paper_gate_protocol_design_bundle.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/paper_gate_protocol_design_bundle.json",
            "experiments/regression/manuscript/paper_gate_protocol_design_bundle.md",
        ),
    ),
    GateStep(
        "paper_gate_closure_execution_plan_after_protocol_design",
        "manuscript",
        "Refresh executable paper-gate plan after protocol-design contracts.",
        (
            "experiments/regression/scripts/build_paper_gate_closure_execution_plan.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/paper_gate_closure_execution_plan.json",
            "experiments/regression/manuscript/paper_gate_closure_execution_plan.md",
        ),
    ),
    GateStep(
        "manuscript_readiness_map_after_dataset_final",
        "manuscript",
        "Refresh paper-readiness map after dataset-final gate artifacts.",
        (
            "experiments/regression/scripts/build_manuscript_readiness_map.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/paper_readiness_map.json",
            "experiments/regression/manuscript/paper_readiness_map.md",
        ),
    ),
    GateStep(
        "manuscript_bundle_eligibility_matrix_after_dataset_final",
        "manuscript",
        "Refresh bundle eligibility matrix after dataset-final gate artifacts.",
        (
            "experiments/regression/scripts/build_manuscript_bundle_eligibility_matrix.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/bundle_eligibility_matrix.json",
            "experiments/regression/manuscript/bundle_eligibility_matrix.md",
        ),
    ),
    GateStep(
        "duplicate_content_quarantine",
        "manuscript",
        "Audit duplicate-sensitive evidence quarantine from final manuscript claims.",
        (
            "experiments/regression/scripts/audit_duplicate_content_quarantine.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "duplicate_content_quarantine_audit.json"),
            str(REPORT_DIR / "duplicate_content_quarantine_audit.md"),
        ),
    ),
    GateStep(
        "graph_artifact_readiness",
        "knowledge_graph",
        "Refresh Mermaid graph artifact freshness and KG traceability checks.",
        (
            "experiments/regression/scripts/audit_graph_artifact_readiness.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "graph_artifact_readiness_audit.json"),
            str(REPORT_DIR / "graph_artifact_readiness_audit.md"),
        ),
    ),
    GateStep(
        "goal_completion_audit",
        "manuscript",
        "Refresh original-goal completion audit and remaining blocker map.",
        (
            "experiments/regression/scripts/build_goal_completion_audit.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/goal_completion_audit.json",
            "experiments/regression/manuscript/goal_completion_audit.md",
        ),
    ),
    GateStep(
        "post_experiment_publication_activation_audit",
        "manuscript",
        "Refresh stop/go audit for neutral post-experiment publication preparation.",
        (
            "experiments/regression/scripts/audit_post_experiment_publication_activation.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/post_experiment_publication_activation_audit.json",
            "experiments/regression/manuscript/post_experiment_publication_activation_audit.md",
        ),
    ),
    GateStep(
        "neutral_reporting_language_audit",
        "manuscript",
        "Refresh neutral scientific-reporting language and method-promotion controls.",
        (
            "experiments/regression/scripts/audit_neutral_reporting_language.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "neutral_reporting_language_audit.json"),
            str(REPORT_DIR / "neutral_reporting_language_audit.md"),
        ),
    ),
    GateStep(
        "publication_preparation_packets",
        "manuscript",
        "Build neutral reviewer design packets and visual/table inventory planning artifact.",
        (
            "experiments/regression/scripts/build_publication_preparation_packets.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/publication_preparation_packets.json",
            "experiments/regression/manuscript/publication_preparation_packets.md",
        ),
    ),
    GateStep(
        "reviewer_design_brief",
        "manuscript",
        "Build neutral pre-prose reviewer advice, reconciliation, content-matrix, and site-decision artifacts.",
        (
            "experiments/regression/scripts/build_reviewer_design_brief.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/reviewer_design_brief.json",
            "experiments/regression/manuscript/reviewer_design_brief.md",
            "experiments/regression/manuscript/reviewer_reconciliation_matrix.json",
            "experiments/regression/manuscript/article_supplement_content_matrix.json",
            "experiments/regression/manuscript/publication_site_decision_record.json",
        ),
    ),
    GateStep(
        "neutral_reporting_language_post_reviewer_design_audit",
        "manuscript",
        "Re-scan neutral language after reviewer design artifacts are generated.",
        (
            "experiments/regression/scripts/audit_neutral_reporting_language.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "neutral_reporting_language_audit.json"),
            str(REPORT_DIR / "neutral_reporting_language_audit.md"),
        ),
    ),
    GateStep(
        "publication_visual_audit_plan",
        "manuscript",
        "Build neutral pre-prose visual/table audit plan and triptych decision artifacts.",
        (
            "experiments/regression/scripts/build_publication_visual_audit_plan.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/visual_table_audit_plan.json",
            "experiments/regression/manuscript/visual_table_audit_plan.md",
            "experiments/regression/manuscript/article_supplement_kg_triptych_decision.json",
            "experiments/regression/manuscript/article_supplement_kg_triptych_decision.md",
        ),
    ),
    GateStep(
        "publication_visual_table_audit_execution",
        "manuscript",
        "Build pre-retention visual/table audit execution artifacts without retaining visuals or tables.",
        (
            "experiments/regression/scripts/build_visual_table_audit_execution.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/visual_table_inventory.json",
            "experiments/regression/manuscript/visual_table_audit_report.json",
            "experiments/regression/manuscript/visual_table_audit_report.md",
            "experiments/regression/manuscript/visual_table_iteration_register.json",
            "experiments/regression/manuscript/kg_navigation_usability_audit.json",
            "experiments/regression/manuscript/figure_quality_decision_log.md",
            "experiments/regression/manuscript/table_quality_decision_log.md",
        ),
    ),
    GateStep(
        "publication_visual_table_render_candidate_audit",
        "manuscript",
        "Build draft visual/table render candidates and layout audit without final retention.",
        (
            "experiments/regression/scripts/build_visual_table_render_candidate_audit.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/visual_table_render_candidate_audit.json",
            "experiments/regression/manuscript/visual_table_render_candidate_audit.md",
            "experiments/regression/manuscript/visual_table_render_candidate_inventory.json",
            "experiments/regression/manuscript/visual_table_layout_quality_audit.json",
            "experiments/regression/manuscript/draft_visual_table_artifacts/README.md",
        ),
    ),
    GateStep(
        "neutral_reporting_language_post_visual_audit_plan_audit",
        "manuscript",
        "Re-scan neutral language after visual/table planning, pre-retention, and draft render artifacts are generated.",
        (
            "experiments/regression/scripts/audit_neutral_reporting_language.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "neutral_reporting_language_audit.json"),
            str(REPORT_DIR / "neutral_reporting_language_audit.md"),
        ),
    ),
    GateStep(
        "publication_retention_readiness_audit",
        "manuscript",
        "Build pre-manuscript article/supplement/KG retention-readiness recommendations without final retention.",
        (
            "experiments/regression/scripts/build_publication_retention_readiness_audit.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/publication_retention_readiness_audit.json",
            "experiments/regression/manuscript/publication_retention_readiness_audit.md",
            "experiments/regression/manuscript/article_supplement_retention_recommendation_matrix.json",
        ),
    ),
    GateStep(
        "neutral_reporting_language_post_retention_readiness_audit",
        "manuscript",
        "Re-scan neutral language after retention-readiness recommendations are generated.",
        (
            "experiments/regression/scripts/audit_neutral_reporting_language.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "neutral_reporting_language_audit.json"),
            str(REPORT_DIR / "neutral_reporting_language_audit.md"),
        ),
    ),
    GateStep(
        "post_experiment_publication_activation_post_retention_refresh",
        "manuscript",
        "Refresh publication activation after reviewer and retention-readiness artifacts exist.",
        (
            "experiments/regression/scripts/audit_post_experiment_publication_activation.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/post_experiment_publication_activation_audit.json",
            "experiments/regression/manuscript/post_experiment_publication_activation_audit.md",
        ),
    ),
    GateStep(
        "neutral_reporting_language_post_activation_refresh_audit",
        "manuscript",
        "Re-scan neutral language after the late publication-activation refresh.",
        (
            "experiments/regression/scripts/audit_neutral_reporting_language.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "neutral_reporting_language_audit.json"),
            str(REPORT_DIR / "neutral_reporting_language_audit.md"),
        ),
    ),
    GateStep(
        "neutral_result_ledger",
        "manuscript",
        "Build neutral claim-bounded result ledger without method promotion or final prose.",
        (
            "experiments/regression/scripts/build_neutral_result_ledger.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/neutral_result_ledger.json",
            "experiments/regression/manuscript/neutral_result_ledger.md",
        ),
    ),
    GateStep(
        "article_supplement_blueprint_alignment",
        "manuscript",
        "Build neutral article/supplement/KG blueprint alignment without final prose or method promotion.",
        (
            "experiments/regression/scripts/build_article_supplement_blueprint_alignment.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/article_supplement_blueprint_alignment.json",
            "experiments/regression/manuscript/article_supplement_blueprint_alignment.md",
        ),
    ),
    GateStep(
        "neutral_reporting_language_post_result_ledger_audit",
        "manuscript",
        "Re-scan neutral language after result and blueprint-alignment artifacts are generated.",
        (
            "experiments/regression/scripts/audit_neutral_reporting_language.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "neutral_reporting_language_audit.json"),
            str(REPORT_DIR / "neutral_reporting_language_audit.md"),
        ),
    ),
    GateStep(
        "knowledge_graph_build",
        "knowledge_graph",
        "Rebuild the machine-readable regression knowledge graph.",
        ("experiments/regression/scripts/build_knowledge_graph.py",),
        ("experiments/regression/catalogs/knowledge_graph.json",),
    ),
    GateStep(
        "knowledge_graph_quality",
        "knowledge_graph",
        "Refresh KG quality, ontology, provenance, confidence, and freshness metrics.",
        (
            "experiments/regression/scripts/audit_knowledge_graph_quality.py",
            "--repo-root",
            ".",
            "--out",
            str(KG_QUALITY_OUT),
            "--fail-on",
            "medium",
        ),
        (str(KG_QUALITY_OUT),),
    ),
    GateStep(
        "kg_publication_quality",
        "knowledge_graph",
        "Refresh publication-facing KG readiness and claim-boundary checks.",
        (
            "experiments/regression/scripts/audit_kg_publication_quality_readiness.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "kg_publication_quality_audit.json"),
            str(REPORT_DIR / "kg_publication_quality_audit.md"),
        ),
    ),
    GateStep(
        "post_experiment_publication_activation_post_kg_publication_refresh",
        "manuscript",
        "Refresh publication activation after the final KG publication-quality audit.",
        (
            "experiments/regression/scripts/audit_post_experiment_publication_activation.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/post_experiment_publication_activation_audit.json",
            "experiments/regression/manuscript/post_experiment_publication_activation_audit.md",
        ),
    ),
    GateStep(
        "neutral_reporting_language_post_kg_activation_refresh_audit",
        "manuscript",
        "Re-scan neutral language after the final post-KG publication activation refresh.",
        (
            "experiments/regression/scripts/audit_neutral_reporting_language.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "neutral_reporting_language_audit.json"),
            str(REPORT_DIR / "neutral_reporting_language_audit.md"),
        ),
    ),
    GateStep(
        "goal_completion_audit_post_kg_activation_refresh",
        "manuscript",
        "Refresh goal-completion audit after the final post-KG publication activation refresh.",
        (
            "experiments/regression/scripts/build_goal_completion_audit.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/goal_completion_audit.json",
            "experiments/regression/manuscript/goal_completion_audit.md",
        ),
    ),
    GateStep(
        "publication_release_gap_register",
        "manuscript",
        "Build neutral publication release-gap register after the refreshed KG publication and goal gates.",
        (
            "experiments/regression/scripts/build_publication_release_gap_register.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/publication_release_gap_register.json",
            "experiments/regression/manuscript/publication_release_gap_register.md",
        ),
    ),
    GateStep(
        "individual_experiment_report_blueprint",
        "manuscript",
        "Build the author-stamped individual report blueprint without final prose or method promotion.",
        (
            "experiments/regression/scripts/build_individual_experiment_report_blueprint.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/individual_experiment_report_blueprint.json",
            "experiments/regression/manuscript/individual_experiment_report_blueprint.md",
        ),
    ),
    GateStep(
        "claim_safe_result_extraction_matrix",
        "manuscript",
        "Build the claim-safe pre-prose result extraction matrix without final claims or method promotion.",
        (
            "experiments/regression/scripts/build_claim_safe_result_extraction_matrix.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/claim_safe_result_extraction_matrix.json",
            "experiments/regression/manuscript/claim_safe_result_extraction_matrix.md",
        ),
    ),
    GateStep(
        "manuscript_section_evidence_packet",
        "manuscript",
        "Build section-level evidence packets from the claim-safe matrix without final prose or method promotion.",
        (
            "experiments/regression/scripts/build_manuscript_section_evidence_packet.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/manuscript_section_evidence_packet.json",
            "experiments/regression/manuscript/manuscript_section_evidence_packet.md",
        ),
    ),
    GateStep(
        "section_claim_boundary_audit",
        "manuscript",
        "Audit section-level allowed/blocked-use boundaries against claim-safe surfaces and release gates.",
        (
            "experiments/regression/scripts/audit_section_claim_boundary_alignment.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/section_claim_boundary_audit.json",
            "experiments/regression/manuscript/section_claim_boundary_audit.md",
        ),
    ),
    GateStep(
        "article_supplement_kg_navigation_index",
        "manuscript",
        "Build the neutral article/supplement/KG navigation index without final release, citation, or method promotion.",
        (
            "experiments/regression/scripts/build_article_supplement_kg_navigation_index.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/article_supplement_kg_navigation_index.json",
            "experiments/regression/manuscript/article_supplement_kg_navigation_index.md",
        ),
    ),
    GateStep(
        "final_publication_visual_auditor_readiness",
        "manuscript",
        "Build the final visual/table auditor feedback-loop readiness artifact without final retention.",
        (
            "experiments/regression/scripts/build_final_publication_visual_auditor_readiness.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/final_publication_visual_auditor_readiness.json",
            "experiments/regression/manuscript/final_publication_visual_auditor_readiness.md",
        ),
    ),
    GateStep(
        "publication_phase_progress_reconciliation_audit",
        "manuscript",
        "Reconcile pre-prose publication progress while keeping final outputs, method recommendation, and positive claims blocked.",
        (
            "experiments/regression/scripts/audit_publication_phase_progress_reconciliation.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/publication_phase_progress_reconciliation_audit.json",
            "experiments/regression/manuscript/publication_phase_progress_reconciliation_audit.md",
        ),
    ),
    GateStep(
        "neutral_reporting_language_post_release_gap_audit",
        "manuscript",
        "Re-scan neutral language after release-gap, individual-report, result-extraction, section-packet, boundary-audit, navigation-index, and publication-progress reconciliation refresh.",
        (
            "experiments/regression/scripts/audit_neutral_reporting_language.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "neutral_reporting_language_audit.json"),
            str(REPORT_DIR / "neutral_reporting_language_audit.md"),
        ),
    ),
    GateStep(
        "scientific_neutrality_interpretation_lock",
        "manuscript",
        "Lock allowed and blocked interpretation language without authorizing final prose, method recommendation, or positive claims.",
        (
            "experiments/regression/scripts/audit_scientific_neutrality_interpretation_lock.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/scientific_neutrality_interpretation_lock.json",
            "experiments/regression/manuscript/scientific_neutrality_interpretation_lock.md",
        ),
    ),
    GateStep(
        "final_publication_output_authorization_protocol",
        "manuscript",
        "Map active final-output blockers to required evidence without authorizing final outputs.",
        (
            "experiments/regression/scripts/build_final_publication_output_authorization_protocol.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/final_publication_output_authorization_protocol.json",
            "experiments/regression/manuscript/final_publication_output_authorization_protocol.md",
        ),
    ),
    GateStep(
        "publication_claim_evidence_verification_matrix",
        "manuscript",
        "Verify pre-prose claim/evidence alignment across section packets, claim boundaries, and KG navigation without authorizing final prose.",
        (
            "experiments/regression/scripts/build_publication_claim_evidence_verification_matrix.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/publication_claim_evidence_verification_matrix.json",
            "experiments/regression/manuscript/publication_claim_evidence_verification_matrix.md",
        ),
    ),
    GateStep(
        "sterile_repository_staging_manifest",
        "manuscript",
        "Build the sterile final-repository staging manifest and exclusion policy without creating a repository.",
        (
            "experiments/regression/scripts/build_sterile_repository_staging_manifest.py",
            "--repo-root",
            ".",
        ),
        (
            "experiments/regression/manuscript/sterile_repository_staging_manifest.json",
            "experiments/regression/manuscript/sterile_repository_staging_manifest.md",
        ),
    ),
    GateStep(
        "knowledge_graph_build_post_release_gap_refresh",
        "knowledge_graph",
        "Rebuild the knowledge graph after release-gap, individual-report, result-extraction, section-packet, boundary, navigation-index, publication-progress reconciliation, interpretation-lock, final-output authorization, claim/evidence verification, and sterile-repository staging refresh.",
        ("experiments/regression/scripts/build_knowledge_graph.py",),
        ("experiments/regression/catalogs/knowledge_graph.json",),
    ),
    GateStep(
        "knowledge_graph_quality_post_release_gap_refresh",
        "knowledge_graph",
        "Refresh KG quality after release-gap, individual-report, result-extraction, section-packet, boundary, navigation-index, publication-progress reconciliation, interpretation-lock, and final-output authorization protocol refresh.",
        (
            "experiments/regression/scripts/audit_knowledge_graph_quality.py",
            "--repo-root",
            ".",
            "--out",
            str(KG_QUALITY_OUT),
            "--fail-on",
            "medium",
        ),
        (str(KG_QUALITY_OUT),),
    ),
    GateStep(
        "kg_publication_quality_post_release_gap_refresh",
        "knowledge_graph",
        "Refresh publication-facing KG readiness after final release-gap/result-extraction graph rebuild.",
        (
            "experiments/regression/scripts/audit_kg_publication_quality_readiness.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "kg_publication_quality_audit.json"),
            str(REPORT_DIR / "kg_publication_quality_audit.md"),
        ),
    ),
    GateStep(
        "scientific_review_finding_register",
        "methodology",
        "Refresh external KG/methodology review-finding closure register.",
        (
            "experiments/regression/scripts/build_scientific_review_finding_register.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "scientific_review_finding_register.json"),
            str(REPORT_DIR / "scientific_review_finding_register.md"),
        ),
    ),
    GateStep(
        "neutral_experiment_closure_audit",
        "methodology",
        "Audit neutral no-promotion experiment-closure readiness before any goal-policy update.",
        (
            "experiments/regression/scripts/audit_neutral_experiment_closure.py",
            "--repo-root",
            ".",
        ),
        (
            str(REPORT_DIR / "neutral_experiment_closure_audit.json"),
            str(REPORT_DIR / "neutral_experiment_closure_audit.md"),
        ),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help=(
            "Refresh the gate manifest from existing step results without "
            "rerunning the audit steps."
        ),
    )
    parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Stop after the first required step failure.",
    )
    return parser.parse_args()


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def read_json_if_present(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def existing_step_results_for_summary(path: Path) -> tuple[list[dict[str, Any]], bool]:
    payload = read_json_if_present(path)
    raw_steps = payload.get("steps")
    steps = (
        [step for step in raw_steps if isinstance(step, dict)]
        if isinstance(raw_steps, list)
        else []
    )
    return steps, bool(payload.get("complete")) if steps else False


def tail_text(value: str, limit: int = 3000) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[-limit:]


def command_for_step(step: GateStep) -> list[str]:
    return [sys.executable, *step.args]


def output_status(paths: tuple[str, ...], root: Path) -> dict[str, Any]:
    rows = []
    for value in paths:
        path = resolve(root, value)
        rows.append(
            {
                "path": rel(path, root),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else 0,
            }
        )
    return {
        "all_present": all(row["exists"] for row in rows),
        "paths": rows,
    }


def run_step(step: GateStep, root: Path) -> dict[str, Any]:
    env = os.environ.copy()
    current_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(root)
        if not current_pythonpath
        else os.pathsep.join([str(root), current_pythonpath])
    )
    started = time.time()
    result = subprocess.run(
        command_for_step(step),
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    finished = time.time()
    outputs = output_status(step.outputs, root)
    ok = result.returncode == 0 and outputs["all_present"]
    return {
        "step_id": step.step_id,
        "family": step.family,
        "description": step.description,
        "required": step.required,
        "command": command_for_step(step),
        "returncode": result.returncode,
        "status": "pass" if ok else "fail",
        "duration_seconds": round(finished - started, 3),
        "started_at_utc": datetime.fromtimestamp(started, timezone.utc).isoformat(),
        "finished_at_utc": datetime.fromtimestamp(finished, timezone.utc).isoformat(),
        "outputs": outputs,
        "stdout_tail": tail_text(result.stdout),
        "stderr_tail": tail_text(result.stderr),
    }


def current_commit(root: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--short=12", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    sha = result.stdout.strip()
    return sha or None


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def git_stdout(root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def porcelain_paths(raw_path: str) -> list[str]:
    path = raw_path.strip()
    parts = path.split(" -> ") if " -> " in path else [path]
    return [part.strip().strip('"').lstrip("./") for part in parts if part.strip()]


def parse_porcelain_status(status: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in status.splitlines():
        if len(line) < 4:
            continue
        status_code = line[:2].strip() or line[:2]
        for path in porcelain_paths(line[3:]):
            rows.append({"status": status_code, "path": path})
    return rows


def unique_ordered(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def dirty_relevant_path(path: str) -> bool:
    return path.startswith(DIRTY_RELEVANT_PATH_PREFIXES)


def dirty_snapshot(root: Path) -> dict[str, Any]:
    status = git_stdout(root, ["status", "--porcelain", "--untracked-files=all"])
    status_tracked = git_stdout(root, ["status", "--porcelain", "--untracked-files=no"])
    diff_stat = git_stdout(root, ["diff", "--stat"])
    diff_name_status = git_stdout(root, ["diff", "--name-status"])
    diff_patch = git_stdout(root, ["diff", "--binary"])
    status_rows = parse_porcelain_status(status)
    tracked_status_rows = parse_porcelain_status(status_tracked)
    dirty_paths = unique_ordered([row["path"] for row in status_rows])
    tracked_dirty_paths = unique_ordered([row["path"] for row in tracked_status_rows])
    untracked_paths = unique_ordered(
        [row["path"] for row in status_rows if row["status"] == "??"]
    )
    relevant_dirty_paths = [path for path in dirty_paths if dirty_relevant_path(path)]
    relevant_diff_patch = ""
    if relevant_dirty_paths:
        relevant_diff_patch = git_stdout(
            root, ["diff", "--binary", "--", *relevant_dirty_paths]
        )
    dirty_digest = sha256_text(
        "\n".join(
            [
                "schema=retrospective_dirty_snapshot_digest_v2",
                "[status_all]",
                status,
                "[status_tracked]",
                status_tracked,
                "[diff_stat]",
                diff_stat,
                "[diff_name_status]",
                diff_name_status,
                "[diff_patch]",
                diff_patch,
                "[relevant_diff_patch]",
                relevant_diff_patch,
            ]
        )
    )
    return {
        "schema": DIRTY_SNAPSHOT_SCHEMA,
        "is_dirty": bool(status.strip()),
        "tracked_dirty": bool(status_tracked.strip()),
        "dirty_path_count": len(dirty_paths),
        "tracked_dirty_path_count": len(tracked_dirty_paths),
        "untracked_path_count": len(untracked_paths),
        "relevant_dirty_path_count": len(relevant_dirty_paths),
        "dirty_path_samples": dirty_paths[:DIRTY_PATH_SAMPLE_LIMIT],
        "untracked_path_samples": untracked_paths[:DIRTY_PATH_SAMPLE_LIMIT],
        "relevant_dirty_paths": relevant_dirty_paths,
        "status_sha256": sha256_text(status),
        "tracked_status_sha256": sha256_text(status_tracked),
        "diff_stat_sha256": sha256_text(diff_stat),
        "diff_name_status_sha256": sha256_text(diff_name_status),
        "diff_patch_sha256": sha256_text(diff_patch),
        "relevant_diff_patch_sha256": sha256_text(relevant_diff_patch),
        "dirty_digest_sha256": dirty_digest,
        "untracked_content_policy": (
            "untracked_path_names_recorded_but_untracked_file_contents_not_hashed"
        ),
    }


def required_failures(steps: list[dict[str, Any]]) -> list[str]:
    return [
        str(step["step_id"])
        for step in steps
        if step.get("required") is True and step.get("status") != "pass"
    ]


def severity_gate(kg: dict[str, Any]) -> str:
    counts = kg.get("issue_counts_by_severity")
    if not isinstance(counts, dict) or not counts:
        return "pass"
    blocking = sum(
        int(counts.get(key, 0) or 0) for key in ("medium", "high", "critical")
    )
    return "fail" if blocking else "caveat"


def build_scientific_summary(
    root: Path, step_results: list[dict[str, Any]]
) -> dict[str, Any]:
    cross = read_json_if_present(root / REPORT_DIR / "cross_run_integrity_audit.json")
    controls = read_json_if_present(
        root / REPORT_DIR / "retrospective_methodology_controls.json"
    )
    feature = read_json_if_present(
        root / REPORT_DIR / "feature_leakage_metadata_completeness_triage.json"
    )
    backlog = read_json_if_present(
        root / REPORT_DIR / "integrity_remediation_backlog.json"
    )
    duplicate_closure = read_json_if_present(
        root / REPORT_DIR / "duplicate_sensitivity_closure_audit.json"
    )
    endpoint = read_json_if_present(
        root / REPORT_DIR / "endpoint_schema_backfill_feasibility.json"
    )
    manuscript = read_json_if_present(
        root / REPORT_DIR / "manuscript_manifest_completeness_audit.json"
    )
    claim_register = read_json_if_present(
        root / REPORT_DIR / "manuscript_claim_register_consistency_audit.json"
    )
    final_selection = read_json_if_present(
        root / REPORT_DIR / "final_selection_claim_boundary_audit.json"
    )
    fairness_sampling_weight_policy = read_json_if_present(
        root / "experiments/regression/manuscript/fairness_sampling_weight_policy.json"
    )
    fairness_group_diagnostic = read_json_if_present(
        root / REPORT_DIR / "fairness_group_diagnostic_audit.json"
    )
    fairness_group_multiplicity_scope = read_json_if_present(
        root / "experiments/regression/manuscript/fairness_group_multiplicity_scope.json"
    )
    fairness_population = read_json_if_present(
        root / REPORT_DIR / "fairness_population_readiness_audit.json"
    )
    venn_abers_validation = read_json_if_present(
        root / REPORT_DIR / "venn_abers_validation_readiness_audit.json"
    )
    venn_abers_grid_ivapd = read_json_if_present(
        root / REPORT_DIR / "venn_abers_grid_ivapd_validation_protocol.json"
    )
    venn_abers_grid_expansion = read_json_if_present(
        root / REPORT_DIR / "venn_abers_grid_expansion_plan.json"
    )
    venn_abers_grid_failure_modes = read_json_if_present(
        root / REPORT_DIR / "venn_abers_grid_failure_mode_decomposition.json"
    )
    venn_abers_claim_gate_matrix = read_json_if_present(
        root / REPORT_DIR / "venn_abers_claim_gate_matrix.json"
    )
    venn_abers_grid_expansion_batch = read_json_if_present(
        root / REPORT_DIR / "venn_abers_grid_expansion_batch.json"
    )
    publication = read_json_if_present(
        root / REPORT_DIR / "publication_methodology_audit.json"
    )
    method_literature = read_json_if_present(
        root / REPORT_DIR / "method_literature_coverage_audit.json"
    )
    selection_multiplicity = read_json_if_present(
        root / "experiments/regression/manuscript/selection_multiplicity_protocol.json"
    )
    bounded_support = read_json_if_present(
        root / "experiments/regression/manuscript/bounded_support_protocol.json"
    )
    target_domain_provenance = read_json_if_present(
        root / "experiments/regression/catalogs/target_domain_provenance.json"
    )
    external_source_discovery = read_json_if_present(
        root
        / "experiments/regression/catalogs/external_source_discovery_watchlist.json"
    )
    bounded_support_posthandling = read_json_if_present(
        root
        / "experiments/regression/manuscript/bounded_support_posthandling_validation.json"
    )
    bounded_support_dataset = read_json_if_present(
        root / "experiments/regression/manuscript/bounded_support_dataset_audit.json"
    )
    bounded_support_endpoint_closure = read_json_if_present(
        root / REPORT_DIR / "bounded_support_endpoint_closure_audit.json"
    )
    bounded_support_positive_validation = read_json_if_present(
        root
        / "experiments/regression/manuscript/"
        / "bounded_support_positive_validation_protocol.json"
    )
    experiment_accounting = read_json_if_present(
        root / REPORT_DIR / "experiment_accounting_audit.json"
    )
    method_performance = read_json_if_present(
        root / REPORT_DIR / "method_performance_synthesis.json"
    )
    method_selection_candidate = read_json_if_present(
        root / REPORT_DIR / "method_selection_candidate_audit.json"
    )
    method_selection_robustness = read_json_if_present(
        root / REPORT_DIR / "method_selection_robustness_audit.json"
    )
    method_selection_alpha_expansion = read_json_if_present(
        root / REPORT_DIR / "method_selection_alpha_expansion_plan.json"
    )
    method_selection_post_selection_validation_batch = read_json_if_present(
        root / REPORT_DIR / "method_selection_post_selection_validation_batch.json"
    )
    method_selection_post_selection_validation_results = read_json_if_present(
        root / REPORT_DIR / "method_selection_post_selection_validation_results.json"
    )
    selection_multiplicity_evidence = read_json_if_present(
        root
        / "experiments/regression/manuscript/selection_multiplicity_evidence_record.json"
    )
    method_selection_alpha_expansion_execution = read_json_if_present(
        root / REPORT_DIR / "method_selection_alpha_expansion_execution_audit.json"
    )
    method_selection_inferential = read_json_if_present(
        root / REPORT_DIR / "method_selection_inferential_audit.json"
    )
    manuscript_readiness = read_json_if_present(
        root / "experiments/regression/manuscript/paper_readiness_map.json"
    )
    manuscript_bundle_eligibility = read_json_if_present(
        root / "experiments/regression/manuscript/bundle_eligibility_matrix.json"
    )
    dataset_specific_final_gate = read_json_if_present(
        root / REPORT_DIR / "dataset_specific_final_gate_audit.json"
    )
    dataset_final_bridge = read_json_if_present(
        root / REPORT_DIR / "dataset_final_gate_post_selection_validation_bridge.json"
    )
    dataset_final_bridge_results = read_json_if_present(
        root
        / REPORT_DIR
        / "dataset_final_gate_post_selection_validation_bridge_results.json"
    )
    main_result_candidate_plan = read_json_if_present(
        root / REPORT_DIR / "main_result_candidate_bundle_plan.json"
    )
    main_result_candidate_results = read_json_if_present(
        root / REPORT_DIR / "main_result_candidate_bundle_results.json"
    )
    main_result_candidate_closure = read_json_if_present(
        root / REPORT_DIR / "main_result_candidate_post_run_closure_audit.json"
    )
    dataset_final_remediation = read_json_if_present(
        root / REPORT_DIR / "dataset_final_gate_remediation_plan.json"
    )
    duplicate_content_quarantine = read_json_if_present(
        root / REPORT_DIR / "duplicate_content_quarantine_audit.json"
    )
    venn_abers_negative_disposition = read_json_if_present(
        root / REPORT_DIR / "venn_abers_negative_evidence_disposition_audit.json"
    )
    graph_artifact = read_json_if_present(
        root / REPORT_DIR / "graph_artifact_readiness_audit.json"
    )
    paper_gate_protocol_design = read_json_if_present(
        root / "experiments/regression/manuscript/paper_gate_protocol_design_bundle.json"
    )
    paper_gate_execution_plan = read_json_if_present(
        root / "experiments/regression/manuscript/paper_gate_closure_execution_plan.json"
    )
    kg_publication = read_json_if_present(
        root / REPORT_DIR / "kg_publication_quality_audit.json"
    )
    scientific_review = read_json_if_present(
        root / REPORT_DIR / "scientific_review_finding_register.json"
    )
    goal_completion = read_json_if_present(
        root / "experiments/regression/manuscript/goal_completion_audit.json"
    )
    post_experiment_publication_activation = read_json_if_present(
        root
        / "experiments/regression/manuscript/"
        / "post_experiment_publication_activation_audit.json"
    )
    publication_preparation_packets = read_json_if_present(
        root / "experiments/regression/manuscript/publication_preparation_packets.json"
    )
    reviewer_design_brief = read_json_if_present(
        root / "experiments/regression/manuscript/reviewer_design_brief.json"
    )
    publication_visual_audit_plan = read_json_if_present(
        root / "experiments/regression/manuscript/visual_table_audit_plan.json"
    )
    visual_table_audit_report = read_json_if_present(
        root / "experiments/regression/manuscript/visual_table_audit_report.json"
    )
    visual_table_render_candidate_audit = read_json_if_present(
        root
        / "experiments/regression/manuscript/"
        / "visual_table_render_candidate_audit.json"
    )
    publication_retention_readiness_audit = read_json_if_present(
        root
        / "experiments/regression/manuscript/"
        / "publication_retention_readiness_audit.json"
    )
    final_publication_visual_auditor_readiness = read_json_if_present(
        root
        / "experiments/regression/manuscript/"
        / "final_publication_visual_auditor_readiness.json"
    )
    neutral_result_ledger = read_json_if_present(
        root / "experiments/regression/manuscript/neutral_result_ledger.json"
    )
    article_supplement_blueprint_alignment = read_json_if_present(
        root
        / "experiments/regression/manuscript/"
        / "article_supplement_blueprint_alignment.json"
    )
    publication_release_gap_register = read_json_if_present(
        root
        / "experiments/regression/manuscript/"
        / "publication_release_gap_register.json"
    )
    individual_experiment_report_blueprint = read_json_if_present(
        root
        / "experiments/regression/manuscript/"
        / "individual_experiment_report_blueprint.json"
    )
    claim_safe_result_extraction_matrix = read_json_if_present(
        root
        / "experiments/regression/manuscript/"
        / "claim_safe_result_extraction_matrix.json"
    )
    manuscript_section_evidence_packet = read_json_if_present(
        root
        / "experiments/regression/manuscript/"
        / "manuscript_section_evidence_packet.json"
    )
    section_claim_boundary_audit = read_json_if_present(
        root
        / "experiments/regression/manuscript/"
        / "section_claim_boundary_audit.json"
    )
    article_supplement_kg_navigation_index = read_json_if_present(
        root
        / "experiments/regression/manuscript/"
        / "article_supplement_kg_navigation_index.json"
    )
    publication_phase_progress_reconciliation = read_json_if_present(
        root
        / "experiments/regression/manuscript/"
        / "publication_phase_progress_reconciliation_audit.json"
    )
    neutral_reporting_language = read_json_if_present(
        root / REPORT_DIR / "neutral_reporting_language_audit.json"
    )
    scientific_neutrality_interpretation_lock = read_json_if_present(
        root
        / "experiments/regression/manuscript/"
        / "scientific_neutrality_interpretation_lock.json"
    )
    final_publication_output_authorization_protocol = read_json_if_present(
        root
        / "experiments/regression/manuscript/"
        / "final_publication_output_authorization_protocol.json"
    )
    publication_claim_evidence_verification_matrix = read_json_if_present(
        root
        / "experiments/regression/manuscript/"
        / "publication_claim_evidence_verification_matrix.json"
    )
    sterile_repository_staging_manifest = read_json_if_present(
        root
        / "experiments/regression/manuscript/"
        / "sterile_repository_staging_manifest.json"
    )
    neutral_experiment_closure = read_json_if_present(
        root / REPORT_DIR / "neutral_experiment_closure_audit.json"
    )
    kg = read_json_if_present(root / KG_QUALITY_OUT)

    cross_summary = cross.get("summary") or {}
    controls_summary = controls.get("summary") or {}
    feature_summary = feature.get("summary") or {}
    backlog_summary = backlog.get("summary") or {}
    duplicate_closure_summary = duplicate_closure.get("summary") or {}
    duplicate_closure_checks = {
        str(item.get("check_id")): item
        for item in duplicate_closure.get("checks", [])
        if isinstance(item, dict) and item.get("check_id")
    }
    duplicate_output_contract = duplicate_closure_checks.get(
        "covered_actions_output_contract_is_strict",
        {},
    )
    endpoint_summary = endpoint.get("summary") or {}
    manuscript_summary = manuscript.get("summary") or {}
    claim_register_summary = claim_register.get("summary") or {}
    final_selection_summary = final_selection.get("summary") or {}
    fairness_population_summary = fairness_population.get("summary") or {}
    venn_abers_validation_summary = venn_abers_validation.get("summary") or {}
    venn_abers_grid_ivapd_summary = venn_abers_grid_ivapd.get("summary") or {}
    venn_abers_grid_expansion_summary = venn_abers_grid_expansion.get("summary") or {}
    venn_abers_grid_failure_modes_summary = (
        venn_abers_grid_failure_modes.get("summary") or {}
    )
    venn_abers_claim_gate_matrix_summary = (
        venn_abers_claim_gate_matrix.get("summary") or {}
    )
    venn_abers_grid_expansion_batch_summary = (
        venn_abers_grid_expansion_batch.get("summary") or {}
    )
    venn_abers_grid_expansion_batch_state = (
        venn_abers_grid_expansion_batch.get("state_summary") or {}
    )
    publication_summary = publication.get("summary") or {}
    method_literature_summary = method_literature.get("summary") or {}
    selection_multiplicity_summary = selection_multiplicity.get("summary") or {}
    bounded_support_summary = bounded_support.get("summary") or {}
    target_domain_provenance_summary = target_domain_provenance.get("summary") or {}
    external_source_discovery_summary = external_source_discovery.get("summary") or {}
    bounded_support_posthandling_summary = (
        bounded_support_posthandling.get("summary") or {}
    )
    bounded_support_dataset_summary = bounded_support_dataset.get("summary") or {}
    bounded_support_endpoint_closure_summary = (
        bounded_support_endpoint_closure.get("summary") or {}
    )
    bounded_support_positive_validation_summary = (
        bounded_support_positive_validation.get("summary") or {}
    )
    experiment_accounting_summary = experiment_accounting.get("summary") or {}
    method_performance_summary = method_performance.get("summary") or {}
    method_selection_candidate_summary = method_selection_candidate.get("summary") or {}
    method_selection_robustness_summary = (
        method_selection_robustness.get("summary") or {}
    )
    method_selection_alpha_expansion_summary = (
        method_selection_alpha_expansion.get("summary") or {}
    )
    method_selection_post_selection_validation_batch_summary = (
        method_selection_post_selection_validation_batch.get("summary") or {}
    )
    method_selection_post_selection_validation_results_summary = (
        method_selection_post_selection_validation_results.get("summary") or {}
    )
    selection_multiplicity_evidence_summary = (
        selection_multiplicity_evidence.get("summary") or {}
    )
    method_selection_alpha_expansion_execution_summary = (
        method_selection_alpha_expansion_execution.get("summary") or {}
    )
    method_selection_inferential_summary = (
        method_selection_inferential.get("summary") or {}
    )
    manuscript_readiness_summary = manuscript_readiness.get("summary") or {}
    manuscript_bundle_eligibility_summary = (
        manuscript_bundle_eligibility.get("summary") or {}
    )
    dataset_specific_final_gate_summary = (
        dataset_specific_final_gate.get("summary") or {}
    )
    dataset_final_bridge_summary = dataset_final_bridge.get("summary") or {}
    dataset_final_bridge_results_summary = (
        dataset_final_bridge_results.get("summary") or {}
    )
    main_result_candidate_plan_summary = main_result_candidate_plan.get("summary") or {}
    main_result_candidate_results_summary = (
        main_result_candidate_results.get("summary") or {}
    )
    main_result_candidate_closure_summary = (
        main_result_candidate_closure.get("summary") or {}
    )
    dataset_final_remediation_summary = dataset_final_remediation.get("summary") or {}
    duplicate_content_quarantine_summary = (
        duplicate_content_quarantine.get("summary") or {}
    )
    venn_abers_negative_disposition_summary = (
        venn_abers_negative_disposition.get("summary") or {}
    )
    graph_artifact_summary = graph_artifact.get("summary") or {}
    paper_gate_protocol_design_summary = (
        paper_gate_protocol_design.get("summary") or {}
    )
    fairness_sampling_weight_policy_summary = (
        fairness_sampling_weight_policy.get("summary") or {}
    )
    fairness_group_diagnostic_summary = fairness_group_diagnostic.get("summary") or {}
    fairness_group_multiplicity_scope_summary = (
        fairness_group_multiplicity_scope.get("summary") or {}
    )
    paper_gate_execution_plan_summary = paper_gate_execution_plan.get("summary") or {}
    kg_publication_summary = kg_publication.get("summary") or {}
    scientific_review_summary = scientific_review.get("summary") or {}
    goal_completion_summary = goal_completion.get("summary") or {}
    post_experiment_publication_activation_summary = (
        post_experiment_publication_activation.get("summary") or {}
    )
    publication_preparation_packets_summary = (
        publication_preparation_packets.get("summary") or {}
    )
    reviewer_design_brief_summary = reviewer_design_brief.get("summary") or {}
    publication_visual_audit_plan_summary = (
        publication_visual_audit_plan.get("summary") or {}
    )
    visual_table_audit_report_summary = (
        visual_table_audit_report.get("summary") or {}
    )
    visual_table_render_candidate_audit_summary = (
        visual_table_render_candidate_audit.get("summary") or {}
    )
    publication_retention_readiness_audit_summary = (
        publication_retention_readiness_audit.get("summary") or {}
    )
    final_publication_visual_auditor_readiness_summary = (
        final_publication_visual_auditor_readiness.get("summary") or {}
    )
    neutral_result_ledger_summary = neutral_result_ledger.get("summary") or {}
    article_supplement_blueprint_alignment_summary = (
        article_supplement_blueprint_alignment.get("summary") or {}
    )
    publication_release_gap_register_summary = (
        publication_release_gap_register.get("summary") or {}
    )
    individual_experiment_report_blueprint_summary = (
        individual_experiment_report_blueprint.get("summary") or {}
    )
    claim_safe_result_extraction_matrix_summary = (
        claim_safe_result_extraction_matrix.get("summary") or {}
    )
    manuscript_section_evidence_packet_summary = (
        manuscript_section_evidence_packet.get("summary") or {}
    )
    section_claim_boundary_audit_summary = (
        section_claim_boundary_audit.get("summary") or {}
    )
    article_supplement_kg_navigation_index_summary = (
        article_supplement_kg_navigation_index.get("summary") or {}
    )
    publication_phase_progress_reconciliation_summary = (
        publication_phase_progress_reconciliation.get("summary") or {}
    )
    neutral_reporting_language_summary = neutral_reporting_language.get("summary") or {}
    scientific_neutrality_interpretation_lock_summary = (
        scientific_neutrality_interpretation_lock.get("summary") or {}
    )
    final_publication_output_authorization_protocol_summary = (
        final_publication_output_authorization_protocol.get("summary") or {}
    )
    publication_claim_evidence_verification_matrix_summary = (
        publication_claim_evidence_verification_matrix.get("summary") or {}
    )
    sterile_repository_staging_manifest_summary = (
        sterile_repository_staging_manifest.get("summary") or {}
    )
    neutral_experiment_closure_summary = (
        neutral_experiment_closure.get("summary") or {}
    )
    kg_graph = kg.get("graph") or {}
    kg_traceability = kg.get("traceability") or {}
    kg_claim_traceability = kg.get("claim_traceability") or {}
    kg_observations = kg.get("observations") or {}
    kg_summaries = kg.get("summaries") or {}
    kg_ontology = kg.get("ontology") or {}
    kg_critical = kg.get("critical_linkage") or {}
    kg_endpoint = kg.get("endpoint_linkage") or {}
    failures = required_failures(step_results)
    hard_leakage_clean = (
        cross_summary.get("leakage_status")
        == "hard_leakage_not_detected_in_scanned_artifacts"
        and controls_summary.get("hard_leakage_status")
        == "no_hard_leakage_detected_in_scanned_artifacts"
        and int(feature_summary.get("hard_feature_leakage_violation_row_count") or 0)
        == 0
    )
    kg_status = severity_gate(kg)
    claim_register_clean = claim_register_summary.get("overall_status") == "pass"
    final_selection_clean = final_selection_summary.get("overall_status") == "pass"
    fairness_population_clean = (
        fairness_population_summary.get("overall_status")
        == "fairness_population_readiness_audit_completed_no_fairness_claim"
        and int(fairness_population_summary.get("failed_check_count") or 0) == 0
        and fairness_population_summary.get("can_support_publication_ready_fairness")
        is False
        and fairness_population_summary.get("fairness_population_claim_status")
        == "blocked_diagnostic_only"
        and fairness_population_summary.get("fairness_requirement_status") == "blocked"
    )
    fairness_group_diagnostic_clean = (
        fairness_group_diagnostic_summary.get("overall_status")
        == "fairness_group_diagnostic_audit_completed_no_fairness_claim"
        and fairness_group_diagnostic_summary.get("action_status")
        == "empirical_execution_complete"
        and int(fairness_group_diagnostic_summary.get("failed_check_count") or 0) == 0
        and int(
            fairness_group_diagnostic_summary.get(
                "group_gap_uncertainty_recorded_bundle_count"
            )
            or 0
        )
        == int(fairness_group_diagnostic_summary.get("bundle_count") or 0)
    )
    fairness_group_multiplicity_scope_clean = (
        fairness_group_multiplicity_scope_summary.get("overall_status")
        == "fairness_group_multiplicity_scope_declared_no_fairness_claim"
        and fairness_group_multiplicity_scope_summary.get("action_status")
        == "multiplicity_control_complete"
        and int(
            fairness_group_multiplicity_scope_summary.get("failed_check_count") or 0
        )
        == 0
        and fairness_group_multiplicity_scope_summary.get(
            "claim_register_cites_multiplicity_record"
        )
        is True
        and fairness_group_multiplicity_scope_summary.get(
            "current_manuscript_fairness_population_claim_ready"
        )
        is False
    )
    publication_clean = (
        publication_summary.get("overall_status")
        in {"publication_workbench_ready", "publication_workbench_ready_with_caveats"}
        and int(publication_summary.get("failed_check_count") or 0) == 0
    )
    method_literature_clean = (
        method_literature_summary.get("overall_status")
        in {
            "method_literature_coverage_pass",
            "method_literature_coverage_pass_with_tracked_gaps",
        }
        and int(method_literature_summary.get("failed_check_count") or 0) == 0
    )
    selection_multiplicity_clean = (
        selection_multiplicity_summary.get("overall_status")
        == "selection_multiplicity_protocol_defined_no_final_selection"
        and int(selection_multiplicity_summary.get("failed_check_count") or 0) == 0
        and selection_multiplicity_summary.get("can_support_final_method_selection")
        is False
        and selection_multiplicity_summary.get("final_selection_claim_status")
        == "blocked"
    )
    bounded_support_clean = (
        bounded_support_summary.get("overall_status")
        == "bounded_support_protocol_defined_no_validity_claim"
        and int(bounded_support_summary.get("failed_check_count") or 0) == 0
        and bounded_support_summary.get("can_support_bounded_support_validity") is False
        and bounded_support_summary.get(
            "publication_can_support_bounded_support_validity"
        )
        is False
        and bounded_support_summary.get("endpoint_bounded_support_gate_status")
        == "blocked"
        and bounded_support_summary.get("final_selection_claim_status") == "blocked"
    )
    target_domain_provenance_clean = (
        target_domain_provenance_summary.get("overall_status")
        == "target_domain_provenance_ready"
        and int(target_domain_provenance_summary.get("failed_check_count") or 0) == 0
        and int(target_domain_provenance_summary.get("row_count") or 0) >= 5
        and int(target_domain_provenance_summary.get("bounded_ordinal_row_count") or 0)
        >= 1
    )
    external_source_discovery_clean = (
        external_source_discovery_summary.get("overall_status")
        == "external_source_discovery_watchlist_ready_with_gaps"
        and int(external_source_discovery_summary.get("failed_check_count") or 0) == 0
        and int(external_source_discovery_summary.get("source_family_count") or 0) >= 14
        and int(
            external_source_discovery_summary.get("primary_source_family_count") or 0
        )
        >= 13
        and int(
            external_source_discovery_summary.get("local_audited_family_count") or 0
        )
        >= 10
        and int(external_source_discovery_summary.get("openml_discovery_rows") or 0)
        >= 600
        and int(external_source_discovery_summary.get("openml_ranked_rows") or 0) >= 50
    )
    bounded_support_posthandling_clean = (
        bounded_support_posthandling_summary.get("overall_status")
        in {
            "bounded_support_posthandling_validation_partial",
            "bounded_support_posthandling_validation_completed",
        }
        and int(
            bounded_support_posthandling_summary.get("reconstruction_failures") or 0
        )
        == 0
        and int(bounded_support_posthandling_summary.get("validated_bundle_count") or 0)
        >= 2
        and int(
            bounded_support_posthandling_summary.get(
                "clip_policy_support_clean_bundle_count"
            )
            or 0
        )
        == int(bounded_support_posthandling_summary.get("validated_bundle_count") or 0)
    )
    bounded_support_dataset_clean = (
        bounded_support_dataset_summary.get("overall_status")
        == "dataset_bounded_support_audit_completed_no_validity_claim"
        and int(bounded_support_dataset_summary.get("failed_check_count") or 0) == 0
        and int(bounded_support_dataset_summary.get("bundle_count") or 0)
        == int(manuscript_summary.get("manifest_count") or 0)
        and int(
            bounded_support_dataset_summary.get("bounded_support_ready_bundle_count")
            or 0
        )
        == 0
        and bounded_support_dataset_summary.get("can_support_bounded_support_validity")
        is False
        and bounded_support_dataset_summary.get("endpoint_bounded_support_gate_status")
        == "blocked"
    )
    bounded_support_endpoint_closure_clean = (
        bounded_support_endpoint_closure_summary.get("overall_status")
        == "endpoint_policy_triage_closed_no_bounded_support_validity_claim"
        and bounded_support_endpoint_closure_summary.get("action_status")
        == "empirical_execution_complete"
        and int(bounded_support_endpoint_closure_summary.get("failed_check_count") or 0)
        == 0
        and int(bounded_support_endpoint_closure_summary.get("bundle_count") or 0)
        == int(
            bounded_support_endpoint_closure_summary.get("closed_policy_bundle_count")
            or 0
        )
        and int(
            bounded_support_endpoint_closure_summary.get(
                "open_endpoint_count_backfill_bundle_count"
            )
            or 0
        )
        == 0
        and int(
            bounded_support_endpoint_closure_summary.get(
                "bounded_support_validity_claim_ready_bundle_count"
            )
            or 0
        )
        == 0
        and bounded_support_endpoint_closure_summary.get(
            "can_support_bounded_support_validity"
        )
        is False
        and bounded_support_endpoint_closure_summary.get(
            "current_manuscript_bounded_support_validity_claim_ready"
        )
        is False
    )
    bounded_support_positive_validation_clean = (
        bounded_support_positive_validation_summary.get("overall_status")
        == "bounded_support_positive_validation_protocol_completed_no_validity_claim"
        and bounded_support_positive_validation_summary.get("action_status")
        == "empirical_validation_complete_no_bounded_support_claim"
        and int(
            bounded_support_positive_validation_summary.get("failed_check_count") or 0
        )
        == 0
        and int(
            bounded_support_positive_validation_summary.get("selected_bundle_count")
            or 0
        )
        == int(
            bounded_support_positive_validation_summary.get(
                "posthandling_validated_bundle_count"
            )
            or -1
        )
        and int(
            bounded_support_positive_validation_summary.get(
                "policy_metrics_available_bundle_count"
            )
            or 0
        )
        == int(
            bounded_support_positive_validation_summary.get("selected_bundle_count")
            or -1
        )
        and int(
            bounded_support_positive_validation_summary.get(
                "endpoint_blocked_or_incomplete_bundle_count"
            )
            or 0
        )
        > 0
        and int(
            bounded_support_positive_validation_summary.get(
                "positive_claim_ready_bundle_count"
            )
            or 0
        )
        == 0
        and bounded_support_positive_validation_summary.get(
            "can_support_bounded_support_validity"
        )
        is False
        and bounded_support_positive_validation_summary.get(
            "current_manuscript_bounded_support_validity_claim_ready"
        )
        is False
    )
    experiment_accounting_clean = (
        experiment_accounting_summary.get("overall_status")
        == "experiment_accounting_pass"
        and int(experiment_accounting_summary.get("failed_check_count") or 0) == 0
        and int(experiment_accounting_summary.get("raw_ledger_row_count") or 0)
        >= int(experiment_accounting_summary.get("canonical_ledger_row_count") or 0)
        >= int(experiment_accounting_summary.get("canonical_completed_row_count") or 0)
        and int(experiment_accounting_summary.get("cross_run_completed_rows") or 0)
        == int(experiment_accounting_summary.get("publication_completed_rows") or 0)
        == int(
            experiment_accounting_summary.get("selection_completed_rows_scanned") or 0
        )
        and int(
            experiment_accounting_summary.get("bounded_support_selected_completed_rows")
            or 0
        )
        <= int(experiment_accounting_summary.get("cross_run_completed_rows") or 0)
        and int(experiment_accounting_summary.get("venn_grid_rows_pending") or 0) == 0
    )
    method_performance_clean = (
        method_performance_summary.get("overall_status")
        == "method_performance_synthesis_descriptive_no_final_selection"
        and int(method_performance_summary.get("failed_check_count") or 0) == 0
        and int(method_performance_summary.get("completed_ledger_rows") or 0)
        == int(cross_summary.get("total_completed_rows") or 0)
        and int(method_performance_summary.get("source_report_count") or 0)
        == int(cross_summary.get("reports_scanned") or 0)
        and int(method_performance_summary.get("method_count") or 0) > 0
        and int(method_performance_summary.get("frontier_cell_count") or 0) > 0
        and method_performance_summary.get("can_support_final_method_selection")
        is False
        and method_performance_summary.get("claim_status")
        == "descriptive_no_final_selection"
    )
    method_selection_candidate_clean = (
        method_selection_candidate_summary.get("overall_status")
        == "method_selection_candidate_audit_ready_no_final_selection"
        and int(method_selection_candidate_summary.get("failed_check_count") or 0) == 0
        and int(
            method_selection_candidate_summary.get("source_completed_ledger_rows") or 0
        )
        == int(cross_summary.get("total_completed_rows") or 0)
        and int(method_selection_candidate_summary.get("shortlist_method_count") or 0)
        >= 3
        and str(
            method_selection_candidate_summary.get("primary_candidate_method") or ""
        )
        != ""
        and int(method_selection_candidate_summary.get("paired_comparison_count") or 0)
        > 0
        and method_selection_candidate_summary.get("can_support_final_method_selection")
        is False
        and method_selection_candidate_summary.get("claim_status")
        == "candidate_shortlist_ready_no_final_selection"
        and method_selection_candidate_summary.get("final_selection_claim_status")
        == "blocked"
    )
    method_selection_robustness_clean = (
        method_selection_robustness_summary.get("overall_status")
        == "method_selection_robustness_audit_ready_no_final_selection"
        and int(method_selection_robustness_summary.get("failed_check_count") or 0) == 0
        and int(
            method_selection_robustness_summary.get("source_completed_ledger_rows") or 0
        )
        == int(cross_summary.get("total_completed_rows") or 0)
        and method_selection_robustness_summary.get("candidate_primary_method")
        == method_selection_candidate_summary.get("primary_candidate_method")
        and method_selection_robustness_summary.get("common_cell_selected_method")
        == method_selection_robustness_summary.get("candidate_primary_method")
        and str(
            method_selection_robustness_summary.get("alpha_balanced_selected_method")
            or ""
        )
        != ""
        and str(
            method_selection_robustness_summary.get("common_alpha_imbalance_status")
            or ""
        )
        != ""
        and int(
            method_selection_robustness_summary.get("common_dataset_alpha_cell_count")
            or 0
        )
        >= 30
        and int(method_selection_robustness_summary.get("bootstrap_replicates") or 0)
        >= 100
        and float(
            method_selection_robustness_summary.get("bootstrap_primary_selection_rate")
            or 0.0
        )
        >= 0.5
        and method_selection_robustness_summary.get(
            "can_support_final_method_selection"
        )
        is False
        and method_selection_robustness_summary.get("claim_status")
        == "selection_robustness_ready_no_final_selection"
        and method_selection_robustness_summary.get("final_selection_claim_status")
        == "blocked"
    )
    alpha_expansion_status = method_selection_alpha_expansion_summary.get(
        "overall_status"
    )
    alpha_expansion_needed = (
        method_selection_robustness_summary.get("common_alpha_imbalance_status")
        == "imbalanced_common_alpha_support"
    )
    method_selection_alpha_expansion_clean = (
        alpha_expansion_status
        in {
            "method_selection_alpha_expansion_plan_ready",
            "method_selection_alpha_expansion_plan_not_needed",
        }
        and int(method_selection_alpha_expansion_summary.get("failed_check_count") or 0)
        == 0
        and int(
            method_selection_alpha_expansion_summary.get("source_completed_ledger_rows")
            or 0
        )
        == int(cross_summary.get("total_completed_rows") or 0)
        and method_selection_alpha_expansion_summary.get(
            "can_support_final_method_selection"
        )
        is False
        and method_selection_alpha_expansion_summary.get("final_selection_claim_status")
        == "blocked"
        and (
            (
                not alpha_expansion_needed
                and alpha_expansion_status
                == "method_selection_alpha_expansion_plan_not_needed"
            )
            or (
                alpha_expansion_needed
                and alpha_expansion_status
                == "method_selection_alpha_expansion_plan_ready"
                and int(
                    method_selection_alpha_expansion_summary.get(
                        "additional_common_cells_needed_to_clear_threshold"
                    )
                    or 0
                )
                > 0
                and int(
                    method_selection_alpha_expansion_summary.get(
                        "planned_common_cell_gain"
                    )
                    or 0
                )
                >= int(
                    method_selection_alpha_expansion_summary.get(
                        "additional_common_cells_needed_to_clear_threshold"
                    )
                    or 0
                )
                and method_selection_alpha_expansion_summary.get(
                    "projected_common_alpha_imbalance_status_after_next_batch"
                )
                == "no_large_alpha_concentration"
            )
        )
    )
    method_selection_post_selection_validation_batch_clean = (
        method_selection_post_selection_validation_batch_summary.get("overall_status")
        == "method_selection_post_selection_validation_batch_ready"
        and int(
            method_selection_post_selection_validation_batch_summary.get(
                "failed_check_count"
            )
            or 0
        )
        == 0
        and method_selection_post_selection_validation_batch_summary.get(
            "can_support_final_method_selection"
        )
        is False
        and method_selection_post_selection_validation_batch_summary.get("claim_status")
        == "post_selection_validation_batch_ready_no_final_selection"
        and int(
            method_selection_post_selection_validation_batch_summary.get(
                "generated_config_count"
            )
            or 0
        )
        > 0
        and int(
            method_selection_post_selection_validation_batch_summary.get(
                "expected_atomic_run_count"
            )
            or 0
        )
        > 0
    )
    method_selection_post_selection_validation_results_clean = (
        method_selection_post_selection_validation_results_summary.get("overall_status")
        == "method_selection_post_selection_validation_results_ready_no_final_selection"
        and int(
            method_selection_post_selection_validation_results_summary.get(
                "failed_check_count"
            )
            or 0
        )
        == 0
        and method_selection_post_selection_validation_results_summary.get(
            "can_support_final_method_selection"
        )
        is False
        and int(
            method_selection_post_selection_validation_results_summary.get(
                "completed_atomic_run_count"
            )
            or 0
        )
        == int(
            method_selection_post_selection_validation_results_summary.get(
                "expected_atomic_run_count"
            )
            or -1
        )
        and int(
            method_selection_post_selection_validation_results_summary.get(
                "common_dataset_alpha_cell_count"
            )
            or 0
        )
        == int(
            method_selection_post_selection_validation_results_summary.get(
                "expected_common_dataset_alpha_cell_count"
            )
            or -1
        )
        and int(
            method_selection_post_selection_validation_results_summary.get(
                "feature_leakage_violation_count"
            )
            or 0
        )
        == 0
    )
    selection_multiplicity_evidence_clean = (
        selection_multiplicity_evidence_summary.get("overall_status")
        == "selection_multiplicity_evidence_record_ready_no_final_selection"
        and int(selection_multiplicity_evidence_summary.get("failed_check_count") or 0)
        == 0
        and selection_multiplicity_evidence_summary.get(
            "can_support_final_method_selection"
        )
        is False
        and selection_multiplicity_evidence_summary.get("final_selection_claim_status")
        == "blocked"
        and selection_multiplicity_evidence_summary.get("validation_results_status")
        == "method_selection_post_selection_validation_results_ready_no_final_selection"
        and int(
            selection_multiplicity_evidence_summary.get(
                "validation_completed_atomic_rows"
            )
            or 0
        )
        == int(
            selection_multiplicity_evidence_summary.get(
                "validation_expected_atomic_rows"
            )
            or -1
        )
        and int(
            selection_multiplicity_evidence_summary.get(
                "feature_leakage_violation_count"
            )
            or 0
        )
        == 0
    )
    method_selection_alpha_expansion_execution_clean = (
        method_selection_alpha_expansion_execution_summary.get("overall_status")
        == "method_selection_alpha_expansion_execution_closed_no_final_selection"
        and int(
            method_selection_alpha_expansion_execution_summary.get("failed_check_count")
            or 0
        )
        == 0
        and method_selection_alpha_expansion_execution_summary.get(
            "observed_execution_status"
        )
        == "ledgers_completed"
        and int(
            method_selection_alpha_expansion_execution_summary.get(
                "completed_atomic_run_count"
            )
            or 0
        )
        == int(
            method_selection_alpha_expansion_execution_summary.get(
                "expected_atomic_run_count"
            )
            or -1
        )
        and method_selection_alpha_expansion_execution_summary.get(
            "can_support_final_method_selection"
        )
        is False
        and method_selection_alpha_expansion_execution_summary.get(
            "final_selection_claim_status"
        )
        == "blocked"
    )
    method_selection_inferential_clean = (
        method_selection_inferential_summary.get("overall_status")
        == "method_selection_inferential_audit_ready_no_final_selection"
        and int(method_selection_inferential_summary.get("failed_check_count") or 0)
        == 0
        and method_selection_inferential_summary.get("primary_candidate_method")
        == method_selection_candidate_summary.get("primary_candidate_method")
        and int(
            method_selection_inferential_summary.get(
                "candidate_pairwise_comparison_count"
            )
            or 0
        )
        > 0
        and int(
            method_selection_inferential_summary.get(
                "candidate_min_shared_pairwise_cell_count"
            )
            or 0
        )
        >= 30
        and method_selection_inferential_summary.get("bootstrap_primary_selection_rate")
        is not None
        and method_selection_inferential_summary.get(
            "post_selection_validation_primary_win_rate"
        )
        is not None
        and method_selection_inferential_summary.get(
            "main_result_candidate_primary_win_rate"
        )
        is not None
        and method_selection_inferential_summary.get(
            "can_support_final_method_selection"
        )
        is False
        and method_selection_inferential_summary.get("claim_status")
        == "inferential_method_selection_evidence_ready_no_final_selection"
        and method_selection_inferential_summary.get("final_selection_claim_status")
        == "blocked"
    )
    manuscript_readiness_clean = (
        manuscript_readiness_summary.get("overall_status")
        == "paper_readiness_blocked_with_evidence_map"
        and int(manuscript_readiness_summary.get("blocked_gate_count") or 0) == 6
        and int(manuscript_readiness_summary.get("main_surface_blocked_count") or 0)
        >= 1
        and manuscript_readiness_summary.get("final_selection_claim_status")
        == "blocked"
    )
    manuscript_bundle_eligibility_clean = (
        manuscript_bundle_eligibility_summary.get("overall_status")
        == "bundle_eligibility_matrix_ready_no_final_claims"
        and int(manuscript_bundle_eligibility_summary.get("bundle_count") or 0)
        == int(manuscript_summary.get("manifest_count") or 0)
        and int(
            manuscript_bundle_eligibility_summary.get("missing_manifest_count") or 0
        )
        == 0
        and int(manuscript_bundle_eligibility_summary.get("unlinked_bundle_count") or 0)
        == 0
        and int(
            manuscript_bundle_eligibility_summary.get("main_results_eligible_count")
            or 0
        )
        == 0
        and int(
            manuscript_bundle_eligibility_summary.get("final_claim_eligible_count") or 0
        )
        == 0
        and manuscript_bundle_eligibility_summary.get("final_selection_claim_status")
        == "blocked"
    )
    dataset_specific_final_gate_clean = (
        dataset_specific_final_gate_summary.get("overall_status")
        == "dataset_specific_final_gate_audit_completed_no_final_dataset_promotions"
        and int(dataset_specific_final_gate_summary.get("bundle_count") or 0)
        == int(manuscript_summary.get("manifest_count") or 0)
        and int(
            dataset_specific_final_gate_summary.get("main_result_ready_bundle_count")
            or 0
        )
        == 0
        and int(
            dataset_specific_final_gate_summary.get("main_result_ready_dataset_count")
            or 0
        )
        == 0
        and dataset_specific_final_gate_summary.get("final_selection_claim_status")
        == "blocked"
        and dataset_specific_final_gate_summary.get("paper_readiness_status")
        == "paper_readiness_blocked_with_evidence_map"
    )
    dataset_final_bridge_clean = (
        dataset_final_bridge_summary.get("overall_status")
        == "dataset_final_gate_post_selection_validation_bridge_ready_no_promotions"
        and int(dataset_final_bridge_summary.get("failed_check_count") or 0) == 0
        and dataset_final_bridge_summary.get("can_support_final_method_selection")
        is False
        and dataset_final_bridge_summary.get("bridge_results_available") is True
        and dataset_final_bridge_summary.get("execution_reconciliation_requires_action")
        is False
        and dataset_final_bridge_summary.get("execution_status")
        == "completed_bridge_results"
        and int(
            dataset_final_bridge_summary.get(
                "bridge_results_completed_atomic_run_count"
            )
            or 0
        )
        == int(
            dataset_final_bridge_summary.get("bridge_results_expected_atomic_run_count")
            or -1
        )
        and int(
            dataset_final_bridge_summary.get(
                "bridge_results_feature_leakage_violation_count"
            )
            or 0
        )
        == 0
    )
    dataset_final_bridge_results_clean = (
        dataset_final_bridge_results_summary.get("overall_status")
        == "method_selection_post_selection_validation_results_ready_no_final_selection"
        and int(dataset_final_bridge_results_summary.get("failed_check_count") or 0)
        == 0
        and dataset_final_bridge_results_summary.get(
            "can_support_final_method_selection"
        )
        is False
        and int(
            dataset_final_bridge_results_summary.get("completed_atomic_run_count") or 0
        )
        == int(
            dataset_final_bridge_results_summary.get("expected_atomic_run_count") or -1
        )
        and int(
            dataset_final_bridge_results_summary.get("common_dataset_alpha_cell_count")
            or 0
        )
        == int(
            dataset_final_bridge_results_summary.get(
                "expected_common_dataset_alpha_cell_count"
            )
            or -1
        )
        and int(
            dataset_final_bridge_results_summary.get("feature_leakage_violation_count")
            or 0
        )
        == 0
    )
    main_result_candidate_plan_clean = (
        main_result_candidate_plan_summary.get("overall_status")
        == "main_result_candidate_bundle_plan_ready_no_promotions"
        and int(main_result_candidate_plan_summary.get("failed_check_count") or 0) == 0
        and main_result_candidate_plan_summary.get("can_support_main_result_promotion")
        is False
        and int(main_result_candidate_plan_summary.get("generated_config_count") or 0)
        > 0
        and int(
            main_result_candidate_plan_summary.get("expected_atomic_run_count") or 0
        )
        > 0
        and int(
            main_result_candidate_plan_summary.get(
                "source_validation_combined_completed_atomic_rows"
            )
            or 0
        )
        == int(
            main_result_candidate_plan_summary.get("expected_atomic_run_count") or -1
        )
        and int(
            main_result_candidate_plan_summary.get(
                "source_validation_combined_failed_check_count"
            )
            or 0
        )
        == 0
        and int(
            main_result_candidate_plan_summary.get(
                "source_validation_combined_feature_leakage_violation_count"
            )
            or 0
        )
        == 0
    )
    main_result_candidate_results_clean = (
        main_result_candidate_results_summary.get("overall_status")
        == "main_result_candidate_bundle_results_completed_no_promotions"
        and int(main_result_candidate_results_summary.get("failed_check_count") or 0)
        == 0
        and main_result_candidate_results_summary.get(
            "can_support_main_result_promotion"
        )
        is False
        and int(
            main_result_candidate_results_summary.get("completed_atomic_run_count") or 0
        )
        == int(
            main_result_candidate_results_summary.get("expected_atomic_run_count") or -1
        )
        and int(main_result_candidate_results_summary.get("missing_ledger_count") or 0)
        == 0
        and int(main_result_candidate_results_summary.get("unique_run_row_count") or 0)
        == int(main_result_candidate_results_summary.get("raw_ledger_row_count") or -1)
    )
    main_result_candidate_closure_clean = (
        main_result_candidate_closure_summary.get("overall_status")
        == "main_result_candidate_post_run_closure_ready_no_promotions"
        and main_result_candidate_closure_summary.get(
            "can_support_main_result_promotion"
        )
        is False
        and int(main_result_candidate_closure_summary.get("total_blocker_count") or 0)
        == 0
        and int(main_result_candidate_closure_summary.get("dataset_blocked_count") or 0)
        == 0
        and int(
            main_result_candidate_closure_summary.get("completed_atomic_run_count") or 0
        )
        == int(
            main_result_candidate_closure_summary.get("expected_atomic_run_count") or -1
        )
    )
    dataset_final_remediation_action_scopes = (
        dataset_final_remediation_summary.get("action_scope_counts") or {}
    )
    dataset_final_remediation_clean = (
        dataset_final_remediation_summary.get("overall_status")
        == "dataset_final_gate_remediation_plan_ready_no_promotions"
        and isinstance(dataset_final_remediation_action_scopes, dict)
        and int(dataset_final_remediation_summary.get("dataset_count") or 0) > 0
        and int(dataset_final_remediation_summary.get("ready_dataset_count") or 0) == 0
        and int(
            dataset_final_remediation_summary.get(
                "missing_post_selection_validation_bridge_count"
            )
            or 0
        )
        == 0
        and int(
            dataset_final_remediation_summary.get(
                "missing_main_result_candidate_bundle_count"
            )
            or 0
        )
        == 0
        and int(
            dataset_final_remediation_summary.get(
                "completed_main_result_candidate_results_dataset_count"
            )
            or 0
        )
        == int(dataset_final_remediation_summary.get("dataset_count") or -1)
        and int(
            dataset_final_remediation_summary.get(
                "candidate_post_run_closure_ready_dataset_count"
            )
            or 0
        )
        == int(dataset_final_remediation_summary.get("dataset_count") or -1)
        and int(
            dataset_final_remediation_action_scopes.get("global_gate_dependency") or 0
        )
        > 0
        and int(
            dataset_final_remediation_summary.get("global_gate_dependency_action_count")
            or 0
        )
        == int(
            dataset_final_remediation_action_scopes.get("global_gate_dependency") or -1
        )
        and int(
            dataset_final_remediation_summary.get(
                "dataset_with_no_remaining_execution_gap_count"
            )
            or 0
        )
        == int(dataset_final_remediation_summary.get("dataset_count") or -1)
    )
    duplicate_content_quarantine_clean = (
        duplicate_content_quarantine_summary.get("overall_status")
        == "duplicate_content_quarantine_pass"
        and int(duplicate_content_quarantine_summary.get("failed_check_count") or 0)
        == 0
        and int(
            duplicate_content_quarantine_summary.get("unquarantined_action_count") or 0
        )
        == 0
        and int(
            duplicate_content_quarantine_summary.get(
                "main_results_eligible_action_count"
            )
            or 0
        )
        == 0
        and int(
            duplicate_content_quarantine_summary.get(
                "caveat_label_missing_action_count"
            )
            or 0
        )
        == 0
        and int(
            duplicate_content_quarantine_summary.get("linked_final_claim_action_count")
            or 0
        )
        == 0
    )
    venn_abers_negative_disposition_clean = (
        venn_abers_negative_disposition_summary.get("overall_status")
        == "venn_abers_negative_evidence_disposition_pass"
        and int(venn_abers_negative_disposition_summary.get("failed_check_count") or 0)
        == 0
        and int(
            venn_abers_negative_disposition_summary.get(
                "shortlist_venn_abers_method_count"
            )
            or 0
        )
        == 0
        and int(
            venn_abers_negative_disposition_summary.get(
                "excluded_venn_abers_method_count"
            )
            or 0
        )
        >= 2
        and int(
            venn_abers_negative_disposition_summary.get(
                "excluded_with_validation_gate_count"
            )
            or 0
        )
        >= 2
        and int(
            venn_abers_negative_disposition_summary.get(
                "venn_bundle_main_eligible_count"
            )
            or 0
        )
        == 0
        and int(
            venn_abers_negative_disposition_summary.get(
                "venn_bundle_main_unblocked_count"
            )
            or 0
        )
        == 0
        and venn_abers_negative_disposition_summary.get(
            "final_selection_venn_abers_gate_status"
        )
        == "blocked"
    )
    venn_abers_validation_clean = (
        venn_abers_validation_summary.get("overall_status")
        == "venn_abers_validation_blocked_with_negative_evidence"
        and int(venn_abers_validation_summary.get("failed_check_count") or 0) == 0
        and venn_abers_validation_summary.get(
            "can_support_venn_abers_regression_validation"
        )
        is False
    )
    venn_abers_grid_ivapd_clean = (
        venn_abers_grid_ivapd_summary.get("overall_status")
        == "venn_abers_grid_ivapd_validation_protocol_defined_no_claim"
        and int(venn_abers_grid_ivapd_summary.get("failed_check_count") or 0) == 0
        and venn_abers_grid_ivapd_summary.get(
            "can_support_validated_venn_abers_regression"
        )
        is False
        and venn_abers_grid_ivapd_summary.get(
            "can_support_exact_grid_venn_abers_validation"
        )
        is False
        and venn_abers_grid_ivapd_summary.get(
            "can_support_ivapd_interval_cp_validation"
        )
        is False
        and int(venn_abers_grid_ivapd_summary.get("validation_blocker_count") or 0) > 0
    )
    venn_abers_grid_expansion_ready_clean = (
        venn_abers_grid_expansion_summary.get("overall_status")
        == "venn_abers_grid_expansion_plan_ready"
        and int(venn_abers_grid_expansion_summary.get("failed_check_count") or 0) == 0
        and int(venn_abers_grid_expansion_summary.get("run_task_count") or 0) > 0
        and int(venn_abers_grid_expansion_summary.get("total_grid_rows_pending") or 0)
        > 0
        and int(venn_abers_grid_expansion_summary.get("next_batch_total_rows") or 0) > 0
        and int(
            venn_abers_grid_expansion_summary.get("duplicate_next_batch_task_key_count")
            or 0
        )
        == 0
    )
    venn_abers_grid_expansion_complete_clean = (
        venn_abers_grid_expansion_summary.get("overall_status")
        == "venn_abers_grid_expansion_plan_complete"
        and int(venn_abers_grid_expansion_summary.get("failed_check_count") or 0) == 0
        and int(venn_abers_grid_expansion_summary.get("run_task_count") or 0) > 0
        and int(venn_abers_grid_expansion_summary.get("total_grid_rows_pending") or 0)
        == 0
        and int(venn_abers_grid_expansion_summary.get("next_batch_total_rows") or 0)
        == 0
        and int(
            venn_abers_grid_expansion_summary.get("duplicate_next_batch_task_key_count")
            or 0
        )
        == 0
        and int(venn_abers_grid_expansion_summary.get("total_grid_rows_completed") or 0)
        == int(venn_abers_grid_expansion_summary.get("total_test_rows_available") or 0)
    )
    venn_abers_grid_expansion_clean = (
        venn_abers_grid_expansion_ready_clean
        or venn_abers_grid_expansion_complete_clean
    )
    venn_abers_grid_failure_modes_clean = (
        venn_abers_grid_failure_modes_summary.get("overall_status")
        == "venn_abers_grid_failure_modes_decomposed_no_claim"
        and int(venn_abers_grid_failure_modes_summary.get("failed_check_count") or 0)
        == 0
        and venn_abers_grid_failure_modes_summary.get(
            "can_support_validated_venn_abers_regression"
        )
        is False
        and int(
            venn_abers_grid_failure_modes_summary.get("validation_blocker_count") or 0
        )
        > 0
        and venn_abers_grid_failure_modes_summary.get("claim_status")
        == "no_validated_venn_abers_regression_claim"
    )
    venn_abers_claim_gate_matrix_clean = (
        venn_abers_claim_gate_matrix_summary.get("overall_status")
        == "venn_abers_claim_gate_matrix_blocked_with_complete_evidence"
        and int(venn_abers_claim_gate_matrix_summary.get("failed_check_count") or 0)
        == 0
        and venn_abers_claim_gate_matrix_summary.get(
            "can_support_validated_venn_abers_regression"
        )
        is False
        and int(
            venn_abers_claim_gate_matrix_summary.get("positive_claim_requirement_count")
            or 0
        )
        > 0
        and int(
            venn_abers_claim_gate_matrix_summary.get("positive_claim_blocked_count")
            or 0
        )
        > 0
    )
    graph_artifact_clean = (
        graph_artifact_summary.get("overall_status") == "graph_artifact_readiness_pass"
        and int(graph_artifact_summary.get("failed_check_count") or 0) == 0
        and graph_artifact_summary.get("all_required_tokens_present") is True
        and graph_artifact_summary.get("all_kg_graph_nodes_traceable") is True
    )
    duplicate_closure_clean = (
        duplicate_closure_summary.get("overall_status")
        in {
            "scoped_duplicate_sensitivity_closure_pass",
            "scoped_duplicate_sensitivity_closure_pass_with_caveats",
        }
        and int(duplicate_closure_summary.get("hard_failed_check_count") or 0) == 0
    )
    kg_publication_clean = (
        kg_publication_summary.get("overall_status")
        in {"kg_publication_ready", "kg_publication_ready_with_polish_caveats"}
        and int(kg_publication_summary.get("hard_failed_check_count") or 0) == 0
    )
    scientific_review_clean = (
        scientific_review_summary.get("overall_status")
        in {
            "scientific_review_findings_closed",
            "scientific_review_findings_tracked_with_open_caveats",
        }
        and int(scientific_review_summary.get("open_blocker_count") or 0) == 0
        and int(scientific_review_summary.get("hard_open_blocker_count") or 0) == 0
    )
    publication_activation_status = (
        post_experiment_publication_activation_summary.get("overall_status")
    )
    publication_activation_clean = (
        publication_activation_status
        == "post_experiment_publication_activation_blocked"
        and post_experiment_publication_activation_summary.get(
            "publication_phase_start_authorized"
        )
        is False
        and int(
            post_experiment_publication_activation_summary.get("blocked_check_count")
            or 0
        )
        > 0
    ) or (
        publication_activation_status
        == "post_experiment_publication_activation_ready"
        and post_experiment_publication_activation_summary.get(
            "publication_phase_start_authorized"
        )
        is True
        and int(
            post_experiment_publication_activation_summary.get("blocked_check_count")
            or 0
        )
        == 0
    ) or (
        publication_activation_status
        == "post_experiment_publication_preparation_active_with_caveats"
        and post_experiment_publication_activation_summary.get(
            "publication_phase_start_authorized"
        )
        is True
        and post_experiment_publication_activation_summary.get(
            "publication_preparation_authorized"
        )
        is True
        and post_experiment_publication_activation_summary.get(
            "manuscript_drafting_authorized"
        )
        is False
        and post_experiment_publication_activation_summary.get(
            "sterile_repository_creation_authorized"
        )
        is False
        and int(
            post_experiment_publication_activation_summary.get("blocked_check_count")
            or 0
        )
        == 0
    )
    publication_preparation_packets_clean = (
        publication_preparation_packets_summary.get("overall_status")
        == "publication_preparation_packets_ready_no_final_prose"
        and publication_preparation_packets_summary.get(
            "publication_preparation_authorized"
        )
        is True
        and int(
            publication_preparation_packets_summary.get("reviewer_packet_count") or 0
        )
        == int(
            publication_preparation_packets_summary.get("required_reviewer_pass_count")
            or 0
        )
        and int(
            publication_preparation_packets_summary.get(
                "visual_table_candidate_family_count"
            )
            or 0
        )
        > 0
        and publication_preparation_packets_summary.get(
            "manuscript_drafting_authorized"
        )
        is False
        and publication_preparation_packets_summary.get(
            "sterile_repository_creation_authorized"
        )
        is False
        and publication_preparation_packets_summary.get(
            "positive_claim_publication_ready"
        )
        is False
        and publication_preparation_packets_summary.get(
            "neutral_no_method_promotion_guard_active"
        )
        is True
        and int(publication_preparation_packets_summary.get("failed_check_count") or 0)
        == 0
    )
    reviewer_design_brief_clean = (
        reviewer_design_brief_summary.get("overall_status")
        == "reviewer_design_brief_ready_no_final_prose"
        and reviewer_design_brief_summary.get("phase_state")
        == "neutral_pre_prose_design_active_final_prose_and_release_blocked"
        and int(reviewer_design_brief_summary.get("reviewer_count") or 0)
        == int(reviewer_design_brief_summary.get("required_reviewer_count") or 0)
        == 5
        and int(reviewer_design_brief_summary.get("advice_record_count") or 0)
        >= 25
        and int(reviewer_design_brief_summary.get("content_matrix_row_count") or 0)
        == int(
            reviewer_design_brief_summary.get("expected_visual_table_family_count")
            or 0
        )
        == 10
        and reviewer_design_brief_summary.get(
            "neutral_no_method_promotion_guard_active"
        )
        is True
        and reviewer_design_brief_summary.get("manuscript_drafting_authorized")
        is False
        and reviewer_design_brief_summary.get(
            "sterile_repository_creation_authorized"
        )
        is False
        and reviewer_design_brief_summary.get(
            "final_visual_table_retention_authorized"
        )
        is False
        and reviewer_design_brief_summary.get("final_manuscript_prose_permission")
        is False
        and reviewer_design_brief_summary.get("final_retain_decision_authorized")
        is False
        and reviewer_design_brief_summary.get("positive_claim_promotion_authorized")
        is False
        and reviewer_design_brief_summary.get(
            "publication_site_deployment_authorized"
        )
        is False
        and int(reviewer_design_brief_summary.get("failed_check_count") or 0) == 0
    )
    publication_visual_audit_plan_clean = (
        publication_visual_audit_plan_summary.get("overall_status")
        == "publication_visual_audit_plan_ready_no_retained_artifacts"
        and publication_visual_audit_plan_summary.get("phase_state")
        == (
            "neutral_pre_prose_visual_audit_planning_active_"
            "final_visuals_and_release_blocked"
        )
        and int(
            publication_visual_audit_plan_summary.get("candidate_artifact_count") or 0
        )
        == int(
            publication_visual_audit_plan_summary.get(
                "expected_candidate_artifact_count"
            )
            or 0
        )
        == 10
        and int(
            publication_visual_audit_plan_summary.get(
                "visual_table_quality_check_count"
            )
            or 0
        )
        >= 10
        and int(
            publication_visual_audit_plan_summary.get("visual_table_scope_count") or 0
        )
        >= 5
        and int(
            publication_visual_audit_plan_summary.get(
                "visual_table_feedback_loop_step_count"
            )
            or 0
        )
        >= 5
        and int(
            publication_visual_audit_plan_summary.get(
                "visual_table_required_output_artifact_count"
            )
            or 0
        )
        >= 6
        and int(
            publication_visual_audit_plan_summary.get("triptych_component_count") or 0
        )
        == 3
        and publication_visual_audit_plan_summary.get(
            "triptych_decision_status"
        )
        == "candidate_triptych_deferred_until_kg_usability_release_gates"
        and publication_visual_audit_plan_summary.get(
            "kg_citable_component_authorized"
        )
        is False
        and publication_visual_audit_plan_summary.get(
            "publication_site_deployment_authorized"
        )
        is False
        and publication_visual_audit_plan_summary.get(
            "visual_table_audit_plan_authorized"
        )
        is True
        and publication_visual_audit_plan_summary.get(
            "visual_table_audit_execution_authorized"
        )
        is False
        and publication_visual_audit_plan_summary.get(
            "final_visual_table_retention_authorized"
        )
        is False
        and publication_visual_audit_plan_summary.get(
            "final_triptych_release_authorized"
        )
        is False
        and publication_visual_audit_plan_summary.get(
            "final_manuscript_prose_permission"
        )
        is False
        and publication_visual_audit_plan_summary.get(
            "positive_claim_promotion_authorized"
        )
        is False
        and publication_visual_audit_plan_summary.get(
            "neutral_no_method_promotion_guard_active"
        )
        is True
        and int(publication_visual_audit_plan_summary.get("failed_check_count") or 0)
        == 0
    )
    visual_table_audit_report_clean = (
        visual_table_audit_report_summary.get("overall_status")
        == "visual_table_pre_retention_audit_completed_no_retained_artifacts"
        and visual_table_audit_report_summary.get("phase_state")
        == "pre_retention_audit_complete_rendering_and_final_retention_blocked"
        and int(visual_table_audit_report_summary.get("inventory_row_count") or 0)
        == 10
        and int(visual_table_audit_report_summary.get("audit_row_count") or 0)
        == int(
            visual_table_audit_report_summary.get(
                "expected_candidate_artifact_count"
            )
            or 0
        )
        == 10
        and int(
            visual_table_audit_report_summary.get(
                "pre_retention_audit_completed_count"
            )
            or 0
        )
        == 10
        and int(
            visual_table_audit_report_summary.get(
                "source_traceable_candidate_count"
            )
            or 0
        )
        == 10
        and int(
            visual_table_audit_report_summary.get("pre_retention_decision_count") or 0
        )
        == 10
        and int(visual_table_audit_report_summary.get("actionable_feedback_count") or 0)
        >= 10
        and int(visual_table_audit_report_summary.get("iteration_action_count") or 0)
        == 10
        and int(visual_table_audit_report_summary.get("rendered_artifact_count") or 0)
        == 0
        and int(
            visual_table_audit_report_summary.get("layout_check_deferred_count") or 0
        )
        == 10
        and int(
            visual_table_audit_report_summary.get("final_retained_artifact_count") or 0
        )
        == 0
        and visual_table_audit_report_summary.get(
            "final_visual_table_retention_authorized"
        )
        is False
        and visual_table_audit_report_summary.get(
            "kg_citable_component_authorized"
        )
        is False
        and visual_table_audit_report_summary.get(
            "publication_site_deployment_authorized"
        )
        is False
        and visual_table_audit_report_summary.get(
            "final_triptych_release_authorized"
        )
        is False
        and visual_table_audit_report_summary.get(
            "final_manuscript_prose_permission"
        )
        is False
        and visual_table_audit_report_summary.get(
            "positive_claim_promotion_authorized"
        )
        is False
        and visual_table_audit_report_summary.get(
            "neutral_no_method_promotion_guard_active"
        )
        is True
        and int(visual_table_audit_report_summary.get("failed_check_count") or 0) == 0
    )
    visual_table_render_candidate_audit_clean = (
        visual_table_render_candidate_audit_summary.get("overall_status")
        == "draft_visual_table_render_audit_completed_no_final_retention"
        and visual_table_render_candidate_audit_summary.get("phase_state")
        == "draft_render_candidates_complete_final_retention_and_release_blocked"
        and int(
            visual_table_render_candidate_audit_summary.get(
                "pre_retention_input_row_count"
            )
            or 0
        )
        == 10
        and int(
            visual_table_render_candidate_audit_summary.get("candidate_row_count") or 0
        )
        == 10
        and int(
            visual_table_render_candidate_audit_summary.get(
                "rendered_draft_artifact_count"
            )
            or 0
        )
        == 10
        and int(
            visual_table_render_candidate_audit_summary.get(
                "primary_rendered_artifact_count"
            )
            or 0
        )
        == 10
        and int(
            visual_table_render_candidate_audit_summary.get("layout_audit_row_count")
            or 0
        )
        == 10
        and int(
            visual_table_render_candidate_audit_summary.get("layout_pass_count") or 0
        )
        == 10
        and int(
            visual_table_render_candidate_audit_summary.get("layout_revise_count") or 0
        )
        == 0
        and int(
            visual_table_render_candidate_audit_summary.get("caption_pass_count") or 0
        )
        == 10
        and int(
            visual_table_render_candidate_audit_summary.get(
                "source_traceability_pass_count"
            )
            or 0
        )
        == 10
        and int(
            visual_table_render_candidate_audit_summary.get(
                "svg_static_text_overlap_detected_count"
            )
            or 0
        )
        == 0
        and int(
            visual_table_render_candidate_audit_summary.get(
                "final_retained_artifact_count"
            )
            or 0
        )
        == 0
        and visual_table_render_candidate_audit_summary.get(
            "final_visual_table_retention_authorized"
        )
        is False
        and visual_table_render_candidate_audit_summary.get(
            "kg_citable_component_authorized"
        )
        is False
        and visual_table_render_candidate_audit_summary.get(
            "publication_site_deployment_authorized"
        )
        is False
        and visual_table_render_candidate_audit_summary.get(
            "final_triptych_release_authorized"
        )
        is False
        and visual_table_render_candidate_audit_summary.get(
            "final_manuscript_prose_permission"
        )
        is False
        and visual_table_render_candidate_audit_summary.get(
            "positive_claim_promotion_authorized"
        )
        is False
        and visual_table_render_candidate_audit_summary.get(
            "neutral_no_method_promotion_guard_active"
        )
        is True
        and int(
            visual_table_render_candidate_audit_summary.get("failed_check_count") or 0
        )
        == 0
    )
    publication_retention_readiness_audit_clean = (
        publication_retention_readiness_audit_summary.get("overall_status")
        == "publication_retention_readiness_ready_no_final_prose"
        and publication_retention_readiness_audit_summary.get("phase_state")
        == (
            "pre_manuscript_retention_recommendations_ready_"
            "final_prose_and_release_blocked"
        )
        and int(
            publication_retention_readiness_audit_summary.get(
                "recommendation_row_count"
            )
            or 0
        )
        == 10
        and int(
            publication_retention_readiness_audit_summary.get("render_candidate_count")
            or 0
        )
        == 10
        and int(
            publication_retention_readiness_audit_summary.get(
                "main_article_candidate_count"
            )
            or 0
        )
        == 4
        and int(
            publication_retention_readiness_audit_summary.get(
                "supplement_candidate_count"
            )
            or 0
        )
        == 5
        and int(
            publication_retention_readiness_audit_summary.get(
                "kg_or_site_candidate_count"
            )
            or 0
        )
        == 1
        and publication_retention_readiness_audit_summary.get(
            "retention_recommendation_complete"
        )
        is True
        and publication_retention_readiness_audit_summary.get(
            "reviewer_design_reconciled"
        )
        is True
        and publication_retention_readiness_audit_summary.get(
            "neutral_result_ledger_clean"
        )
        is True
        and int(
            publication_retention_readiness_audit_summary.get(
                "neutral_language_unguarded_hit_count"
            )
            or 0
        )
        == 0
        and int(
            publication_retention_readiness_audit_summary.get(
                "final_retained_artifact_count"
            )
            or 0
        )
        == 0
        and publication_retention_readiness_audit_summary.get(
            "final_visual_table_retention_authorized"
        )
        is False
        and publication_retention_readiness_audit_summary.get(
            "final_manuscript_prose_permission"
        )
        is False
        and publication_retention_readiness_audit_summary.get(
            "publication_site_deployment_authorized"
        )
        is False
        and publication_retention_readiness_audit_summary.get(
            "kg_citable_component_authorized"
        )
        is False
        and publication_retention_readiness_audit_summary.get(
            "positive_claim_promotion_authorized"
        )
        is False
        and publication_retention_readiness_audit_summary.get(
            "sterile_repository_creation_authorized"
        )
        is False
        and int(
            publication_retention_readiness_audit_summary.get("failed_check_count")
            or 0
        )
        == 0
    )
    final_publication_visual_auditor_readiness_clean = (
        final_publication_visual_auditor_readiness_summary.get("overall_status")
        == "final_publication_visual_auditor_feedback_loop_ready_no_retention"
        and final_publication_visual_auditor_readiness_summary.get("phase_state")
        == "pre_final_visual_auditor_feedback_ready_final_retention_blocked"
        and final_publication_visual_auditor_readiness_summary.get(
            "final_publication_visual_auditor_status"
        )
        == "feedback_loop_ready_no_final_retention"
        and final_publication_visual_auditor_readiness_summary.get(
            "feedback_loop_ready"
        )
        is True
        and int(
            final_publication_visual_auditor_readiness_summary.get(
                "feedback_row_count"
            )
            or 0
        )
        == 10
        and int(
            final_publication_visual_auditor_readiness_summary.get(
                "feedback_ready_row_count"
            )
            or 0
        )
        == 10
        and int(
            final_publication_visual_auditor_readiness_summary.get(
                "feedback_blocked_row_count"
            )
            or 0
        )
        == 0
        and int(
            final_publication_visual_auditor_readiness_summary.get(
                "feedback_item_count"
            )
            or 0
        )
        >= 30
        and int(
            final_publication_visual_auditor_readiness_summary.get(
                "missing_rendered_artifact_count"
            )
            or 0
        )
        == 0
        and int(
            final_publication_visual_auditor_readiness_summary.get(
                "authorization_violation_count"
            )
            or 0
        )
        == 0
        and int(
            final_publication_visual_auditor_readiness_summary.get(
                "release_authorized_count"
            )
            or 0
        )
        == 0
        and int(
            final_publication_visual_auditor_readiness_summary.get(
                "final_retained_artifact_count"
            )
            or 0
        )
        == 0
        and final_publication_visual_auditor_readiness_summary.get(
            "final_visual_table_retention_authorized"
        )
        is False
        and final_publication_visual_auditor_readiness_summary.get(
            "final_manuscript_prose_permission"
        )
        is False
        and final_publication_visual_auditor_readiness_summary.get(
            "publication_site_deployment_authorized"
        )
        is False
        and final_publication_visual_auditor_readiness_summary.get(
            "kg_citable_component_authorized"
        )
        is False
        and final_publication_visual_auditor_readiness_summary.get(
            "sterile_repository_creation_authorized"
        )
        is False
        and final_publication_visual_auditor_readiness_summary.get(
            "method_recommendation_authorized"
        )
        is False
        and final_publication_visual_auditor_readiness_summary.get(
            "positive_claim_promotion_authorized"
        )
        is False
        and int(
            final_publication_visual_auditor_readiness_summary.get(
                "neutral_language_unguarded_hit_count"
            )
            or 0
        )
        == 0
        and int(
            final_publication_visual_auditor_readiness_summary.get(
                "missing_source_artifact_count"
            )
            or 0
        )
        == 0
        and int(
            final_publication_visual_auditor_readiness_summary.get(
                "failed_check_count"
            )
            or 0
        )
        == 0
    )
    neutral_result_ledger_clean = (
        neutral_result_ledger_summary.get("overall_status")
        == "neutral_result_ledger_ready_no_method_promotion"
        and int(neutral_result_ledger_summary.get("row_count") or 0) == 9
        and int(neutral_result_ledger_summary.get("source_artifact_count") or 0)
        >= 15
        and int(
            neutral_result_ledger_summary.get("missing_source_artifact_count") or 0
        )
        == 0
        and int(
            neutral_result_ledger_summary.get(
                "positive_claim_promotion_authorized_count"
            )
            or 0
        )
        == 0
        and int(
            neutral_result_ledger_summary.get(
                "final_method_selection_authorized_count"
            )
            or 0
        )
        == 0
        and int(
            neutral_result_ledger_summary.get(
                "final_visual_table_retention_authorized_count"
            )
            or 0
        )
        == 0
        and int(
            neutral_result_ledger_summary.get("final_manuscript_prose_permission_count")
            or 0
        )
        == 0
        and int(
            neutral_result_ledger_summary.get(
                "sterile_repository_creation_authorized_count"
            )
            or 0
        )
        == 0
        and neutral_result_ledger_summary.get(
            "neutral_no_method_promotion_guard_active"
        )
        is True
        and neutral_result_ledger_summary.get("cqr_descriptive_candidate_recorded")
        is True
        and neutral_result_ledger_summary.get("venn_abers_negative_result_recorded")
        is True
        and int(neutral_result_ledger_summary.get("failed_check_count") or 0) == 0
    )
    article_supplement_blueprint_alignment_clean = (
        article_supplement_blueprint_alignment_summary.get("overall_status")
        == (
            "article_supplement_blueprint_alignment_ready_"
            "no_final_prose_no_method_promotion"
        )
        and article_supplement_blueprint_alignment_summary.get("phase_state")
        == (
            "neutral_pre_prose_blueprint_alignment_active_"
            "final_prose_and_release_blocked"
        )
        and int(
            article_supplement_blueprint_alignment_summary.get("alignment_row_count")
            or 0
        )
        == 10
        and int(
            article_supplement_blueprint_alignment_summary.get("surface_row_count")
            or 0
        )
        == 3
        and int(
            article_supplement_blueprint_alignment_summary.get(
                "reviewer_alignment_issue_count"
            )
            or 0
        )
        == 0
        and int(
            article_supplement_blueprint_alignment_summary.get(
                "linked_neutral_result_issue_count"
            )
            or 0
        )
        == 0
        and int(
            article_supplement_blueprint_alignment_summary.get(
                "source_traceable_row_count"
            )
            or 0
        )
        == 10
        and int(
            article_supplement_blueprint_alignment_summary.get(
                "missing_source_artifact_count"
            )
            or 0
        )
        == 0
        and article_supplement_blueprint_alignment_summary.get(
            "neutral_result_ledger_clean"
        )
        is True
        and int(
            article_supplement_blueprint_alignment_summary.get(
                "neutral_language_unguarded_hit_count"
            )
            or 0
        )
        == 0
        and article_supplement_blueprint_alignment_summary.get(
            "activation_pre_prose_only"
        )
        is True
        and article_supplement_blueprint_alignment_summary.get(
            "venn_abers_negative_no_validated_claim"
        )
        is True
        and int(
            article_supplement_blueprint_alignment_summary.get(
                "final_retained_artifact_count"
            )
            or 0
        )
        == 0
        and article_supplement_blueprint_alignment_summary.get(
            "final_visual_table_retention_authorized"
        )
        is False
        and article_supplement_blueprint_alignment_summary.get(
            "final_manuscript_prose_permission"
        )
        is False
        and article_supplement_blueprint_alignment_summary.get(
            "publication_site_deployment_authorized"
        )
        is False
        and article_supplement_blueprint_alignment_summary.get(
            "kg_citable_component_authorized"
        )
        is False
        and article_supplement_blueprint_alignment_summary.get(
            "positive_claim_promotion_authorized"
        )
        is False
        and article_supplement_blueprint_alignment_summary.get(
            "sterile_repository_creation_authorized"
        )
        is False
        and article_supplement_blueprint_alignment_summary.get(
            "method_recommendation_authorized"
        )
        is False
        and article_supplement_blueprint_alignment_summary.get(
            "scientific_no_method_promotion_guard_active"
        )
        is True
        and int(
            article_supplement_blueprint_alignment_summary.get("failed_check_count")
            or 0
        )
        == 0
    )
    publication_release_gap_register_clean = (
        publication_release_gap_register_summary.get("overall_status")
        == "publication_release_gap_register_ready_no_final_release"
        and publication_release_gap_register_summary.get("phase_state")
        == "neutral_pre_release_gap_register_active_final_release_blocked"
        and int(
            publication_release_gap_register_summary.get("deliverable_row_count") or 0
        )
        == 11
        and int(
            publication_release_gap_register_summary.get(
                "pre_prose_evidence_ready_row_count"
            )
            or 0
        )
        == 11
        and int(
            publication_release_gap_register_summary.get("release_authorized_count")
            or 0
        )
        == 0
        and int(
            publication_release_gap_register_summary.get("blocked_release_row_count")
            or 0
        )
        == 11
        and int(
            publication_release_gap_register_summary.get("source_traceable_row_count")
            or 0
        )
        == 11
        and int(
            publication_release_gap_register_summary.get(
                "missing_source_artifact_count"
            )
            or 0
        )
        == 0
        and publication_release_gap_register_summary.get("goal_can_mark_complete")
        is False
        and int(
            publication_release_gap_register_summary.get("paper_blocked_gate_count")
            or 0
        )
        == 6
        and int(
            publication_release_gap_register_summary.get(
                "positive_claim_ready_gate_count"
            )
            or 0
        )
        == 0
        and publication_release_gap_register_summary.get(
            "final_manuscript_prose_permission"
        )
        is False
        and publication_release_gap_register_summary.get(
            "publication_site_deployment_authorized"
        )
        is False
        and publication_release_gap_register_summary.get(
            "kg_citable_component_authorized"
        )
        is False
        and publication_release_gap_register_summary.get(
            "sterile_repository_creation_authorized"
        )
        is False
        and publication_release_gap_register_summary.get(
            "positive_claim_promotion_authorized"
        )
        is False
        and publication_release_gap_register_summary.get(
            "method_recommendation_authorized"
        )
        is False
        and publication_release_gap_register_summary.get(
            "working_repository_final_citable"
        )
        is False
        and publication_release_gap_register_summary.get(
            "scientific_no_method_promotion_guard_active"
        )
        is True
        and int(
            publication_release_gap_register_summary.get("failed_check_count") or 0
        )
        == 0
    )
    individual_experiment_report_blueprint_clean = (
        individual_experiment_report_blueprint_summary.get("overall_status")
        == "individual_experiment_report_blueprint_ready_no_final_prose"
        and individual_experiment_report_blueprint_summary.get("phase_state")
        == "neutral_pre_prose_individual_report_blueprint_active_final_outputs_blocked"
        and individual_experiment_report_blueprint_summary.get(
            "approved_author_header_present"
        )
        is True
        and individual_experiment_report_blueprint_summary.get("author_header")
        == "Author: Emre Tasar, Data Scientist"
        and individual_experiment_report_blueprint_summary.get("author_email")
        == "detasar@gmail.com"
        and individual_experiment_report_blueprint_summary.get("deliverable_registered")
        is True
        and individual_experiment_report_blueprint_summary.get("deliverable_format")
        == "latex_html_and_markdown"
        and int(
            individual_experiment_report_blueprint_summary.get("section_row_count") or 0
        )
        == 10
        and int(
            individual_experiment_report_blueprint_summary.get(
                "source_traceable_row_count"
            )
            or 0
        )
        == 10
        and int(
            individual_experiment_report_blueprint_summary.get(
                "missing_source_artifact_count"
            )
            or 0
        )
        == 0
        and int(
            individual_experiment_report_blueprint_summary.get(
                "linked_neutral_result_issue_count"
            )
            or 0
        )
        == 0
        and individual_experiment_report_blueprint_summary.get(
            "final_report_prose_permission"
        )
        is False
        and individual_experiment_report_blueprint_summary.get(
            "latex_output_authorized"
        )
        is False
        and individual_experiment_report_blueprint_summary.get(
            "html_output_authorized"
        )
        is False
        and individual_experiment_report_blueprint_summary.get(
            "markdown_output_authorized"
        )
        is False
        and individual_experiment_report_blueprint_summary.get("release_authorized")
        is False
        and individual_experiment_report_blueprint_summary.get(
            "sterile_repository_creation_authorized"
        )
        is False
        and individual_experiment_report_blueprint_summary.get(
            "working_repository_final_citable"
        )
        is False
        and individual_experiment_report_blueprint_summary.get(
            "method_recommendation_authorized"
        )
        is False
        and individual_experiment_report_blueprint_summary.get(
            "positive_claim_promotion_authorized"
        )
        is False
        and individual_experiment_report_blueprint_summary.get("cqr_reporting_role")
        == "descriptive_diagnostic_no_final_selection"
        and individual_experiment_report_blueprint_summary.get(
            "venn_abers_reporting_role"
        )
        == "negative_failure_mode_no_validated_regression_claim"
        and individual_experiment_report_blueprint_summary.get(
            "scientific_no_method_promotion_guard_active"
        )
        is True
        and int(
            individual_experiment_report_blueprint_summary.get("failed_check_count")
            or 0
        )
        == 0
    )
    claim_safe_result_extraction_matrix_clean = (
        claim_safe_result_extraction_matrix_summary.get("overall_status")
        == "claim_safe_result_extraction_matrix_ready_no_final_claims"
        and claim_safe_result_extraction_matrix_summary.get("phase_state")
        == "neutral_pre_prose_result_extraction_active_final_outputs_blocked"
        and int(
            claim_safe_result_extraction_matrix_summary.get("surface_row_count") or 0
        )
        == 8
        and int(
            claim_safe_result_extraction_matrix_summary.get(
                "source_traceable_row_count"
            )
            or 0
        )
        == 8
        and int(
            claim_safe_result_extraction_matrix_summary.get(
                "missing_source_artifact_count"
            )
            or 0
        )
        == 0
        and int(
            claim_safe_result_extraction_matrix_summary.get(
                "linked_neutral_result_issue_count"
            )
            or 0
        )
        == 0
        and int(
            claim_safe_result_extraction_matrix_summary.get(
                "safe_pre_prose_extraction_candidate_count"
            )
            or 0
        )
        == 7
        and int(
            claim_safe_result_extraction_matrix_summary.get(
                "blocked_positive_surface_count"
            )
            or 0
        )
        == 1
        and claim_safe_result_extraction_matrix_summary.get(
            "main_results_surface_status"
        )
        == "blocked_positive_claim_surface"
        and claim_safe_result_extraction_matrix_summary.get(
            "negative_results_surface_status"
        )
        == "candidate_negative_result_surface"
        and claim_safe_result_extraction_matrix_summary.get(
            "main_result_positive_claim_blocked"
        )
        is True
        and claim_safe_result_extraction_matrix_summary.get(
            "negative_result_reporting_ready"
        )
        is True
        and claim_safe_result_extraction_matrix_summary.get(
            "neutral_result_ledger_clean"
        )
        is True
        and claim_safe_result_extraction_matrix_summary.get(
            "final_manuscript_prose_permission"
        )
        is False
        and claim_safe_result_extraction_matrix_summary.get(
            "final_visual_table_retention_authorized"
        )
        is False
        and claim_safe_result_extraction_matrix_summary.get("release_authorized")
        is False
        and claim_safe_result_extraction_matrix_summary.get(
            "publication_site_deployment_authorized"
        )
        is False
        and claim_safe_result_extraction_matrix_summary.get(
            "kg_citable_component_authorized"
        )
        is False
        and claim_safe_result_extraction_matrix_summary.get(
            "sterile_repository_creation_authorized"
        )
        is False
        and claim_safe_result_extraction_matrix_summary.get(
            "working_repository_final_citable"
        )
        is False
        and claim_safe_result_extraction_matrix_summary.get(
            "method_recommendation_authorized"
        )
        is False
        and claim_safe_result_extraction_matrix_summary.get(
            "positive_claim_promotion_authorized"
        )
        is False
        and claim_safe_result_extraction_matrix_summary.get(
            "scientific_no_method_promotion_guard_active"
        )
        is True
        and int(
            claim_safe_result_extraction_matrix_summary.get("failed_check_count") or 0
        )
        == 0
    )
    manuscript_section_evidence_packet_clean = (
        manuscript_section_evidence_packet_summary.get("overall_status")
        == "manuscript_section_evidence_packet_ready_no_final_prose"
        and manuscript_section_evidence_packet_summary.get("phase_state")
        == (
            "neutral_pre_prose_section_evidence_packet_active_"
            "final_outputs_blocked"
        )
        and int(
            manuscript_section_evidence_packet_summary.get("section_packet_row_count")
            or 0
        )
        == 8
        and int(
            manuscript_section_evidence_packet_summary.get(
                "source_traceable_row_count"
            )
            or 0
        )
        == 8
        and int(
            manuscript_section_evidence_packet_summary.get(
                "missing_source_artifact_count"
            )
            or 0
        )
        == 0
        and int(
            manuscript_section_evidence_packet_summary.get(
                "claim_safe_surface_link_issue_count"
            )
            or 0
        )
        == 0
        and int(
            manuscript_section_evidence_packet_summary.get(
                "linked_neutral_result_issue_count"
            )
            or 0
        )
        == 0
        and int(
            manuscript_section_evidence_packet_summary.get(
                "safe_pre_prose_evidence_packet_count"
            )
            or 0
        )
        == 7
        and int(
            manuscript_section_evidence_packet_summary.get(
                "blocked_positive_packet_count"
            )
            or 0
        )
        == 1
        and manuscript_section_evidence_packet_summary.get(
            "main_results_packet_status"
        )
        == "blocked_positive_claim_packet"
        and manuscript_section_evidence_packet_summary.get("negative_packet_status")
        == "pre_prose_negative_evidence_ready"
        and manuscript_section_evidence_packet_summary.get(
            "main_results_packet_blocked"
        )
        is True
        and manuscript_section_evidence_packet_summary.get("negative_packet_ready")
        is True
        and manuscript_section_evidence_packet_summary.get("claim_safe_matrix_clean")
        is True
        and manuscript_section_evidence_packet_summary.get(
            "neutral_result_ledger_clean"
        )
        is True
        and manuscript_section_evidence_packet_summary.get(
            "final_section_prose_authorized"
        )
        is False
        and manuscript_section_evidence_packet_summary.get(
            "final_manuscript_prose_permission"
        )
        is False
        and manuscript_section_evidence_packet_summary.get(
            "final_visual_table_retention_authorized"
        )
        is False
        and manuscript_section_evidence_packet_summary.get("release_authorized")
        is False
        and manuscript_section_evidence_packet_summary.get(
            "publication_site_deployment_authorized"
        )
        is False
        and manuscript_section_evidence_packet_summary.get(
            "kg_citable_component_authorized"
        )
        is False
        and manuscript_section_evidence_packet_summary.get(
            "sterile_repository_creation_authorized"
        )
        is False
        and manuscript_section_evidence_packet_summary.get(
            "working_repository_final_citable"
        )
        is False
        and manuscript_section_evidence_packet_summary.get(
            "method_recommendation_authorized"
        )
        is False
        and manuscript_section_evidence_packet_summary.get(
            "positive_claim_promotion_authorized"
        )
        is False
        and manuscript_section_evidence_packet_summary.get(
            "scientific_no_method_promotion_guard_active"
        )
        is True
        and int(
            manuscript_section_evidence_packet_summary.get("failed_check_count") or 0
        )
        == 0
    )
    section_claim_boundary_audit_clean = (
        section_claim_boundary_audit_summary.get("overall_status")
        == "section_claim_boundary_audit_pass_no_final_claims"
        and section_claim_boundary_audit_summary.get("phase_state")
        == (
            "neutral_pre_prose_section_claim_boundary_alignment_active_"
            "final_outputs_blocked"
        )
        and int(section_claim_boundary_audit_summary.get("boundary_row_count") or 0)
        == 8
        and int(
            section_claim_boundary_audit_summary.get("boundary_complete_row_count")
            or 0
        )
        == 8
        and int(
            section_claim_boundary_audit_summary.get(
                "allowed_use_complete_row_count"
            )
            or 0
        )
        == 8
        and int(
            section_claim_boundary_audit_summary.get(
                "blocked_use_complete_row_count"
            )
            or 0
        )
        == 8
        and int(
            section_claim_boundary_audit_summary.get(
                "claim_safe_surface_consistent_row_count"
            )
            or 0
        )
        == 8
        and int(
            section_claim_boundary_audit_summary.get("neutral_result_linked_row_count")
            or 0
        )
        == 8
        and int(
            section_claim_boundary_audit_summary.get("release_target_linked_row_count")
            or 0
        )
        == 8
        and int(
            section_claim_boundary_audit_summary.get(
                "release_authorized_target_count"
            )
            or 0
        )
        == 0
        and int(
            section_claim_boundary_audit_summary.get(
                "neutral_ledger_prose_boundary_gap_unique_result_count"
            )
            or 0
        )
        == 5
        and int(
            section_claim_boundary_audit_summary.get(
                "section_boundary_backfill_row_count"
            )
            or 0
        )
        == 8
        and section_claim_boundary_audit_summary.get(
            "main_results_positive_boundary_blocked"
        )
        is True
        and section_claim_boundary_audit_summary.get(
            "venn_abers_negative_boundary_preserved"
        )
        is True
        and section_claim_boundary_audit_summary.get("section_packet_clean") is True
        and section_claim_boundary_audit_summary.get("upstream_boundaries_clean")
        is True
        and section_claim_boundary_audit_summary.get("post_program_controlled")
        is True
        and section_claim_boundary_audit_summary.get(
            "final_section_prose_authorized"
        )
        is False
        and section_claim_boundary_audit_summary.get(
            "final_manuscript_prose_permission"
        )
        is False
        and section_claim_boundary_audit_summary.get(
            "final_visual_table_retention_authorized"
        )
        is False
        and section_claim_boundary_audit_summary.get("release_authorized") is False
        and section_claim_boundary_audit_summary.get(
            "publication_site_deployment_authorized"
        )
        is False
        and section_claim_boundary_audit_summary.get(
            "kg_citable_component_authorized"
        )
        is False
        and section_claim_boundary_audit_summary.get(
            "sterile_repository_creation_authorized"
        )
        is False
        and section_claim_boundary_audit_summary.get(
            "working_repository_final_citable"
        )
        is False
        and section_claim_boundary_audit_summary.get(
            "method_recommendation_authorized"
        )
        is False
        and section_claim_boundary_audit_summary.get(
            "positive_claim_promotion_authorized"
        )
        is False
        and section_claim_boundary_audit_summary.get(
            "scientific_no_method_promotion_guard_active"
        )
        is True
        and int(
            section_claim_boundary_audit_summary.get("failed_check_count") or 0
        )
        == 0
    )
    article_supplement_kg_navigation_index_clean = (
        article_supplement_kg_navigation_index_summary.get("overall_status")
        == "article_supplement_kg_navigation_index_ready_no_release"
        and article_supplement_kg_navigation_index_summary.get("phase_state")
        == "neutral_pre_release_navigation_index_active_final_outputs_blocked"
        and int(
            article_supplement_kg_navigation_index_summary.get(
                "navigation_row_count"
            )
            or 0
        )
        == 9
        and int(
            article_supplement_kg_navigation_index_summary.get(
                "section_navigation_row_count"
            )
            or 0
        )
        == 8
        and int(
            article_supplement_kg_navigation_index_summary.get(
                "kg_site_navigation_row_count"
            )
            or 0
        )
        == 1
        and int(
            article_supplement_kg_navigation_index_summary.get(
                "source_traceable_row_count"
            )
            or 0
        )
        == 9
        and int(
            article_supplement_kg_navigation_index_summary.get(
                "visual_table_candidate_index_row_count"
            )
            or 0
        )
        == 10
        and int(
            article_supplement_kg_navigation_index_summary.get(
                "visual_table_source_traceability_pass_count"
            )
            or 0
        )
        == 10
        and int(
            article_supplement_kg_navigation_index_summary.get(
                "visual_table_final_authorized_count"
            )
            or 0
        )
        == 0
        and int(
            article_supplement_kg_navigation_index_summary.get(
                "release_authorized_target_count"
            )
            or 0
        )
        == 0
        and int(
            article_supplement_kg_navigation_index_summary.get(
                "kg_node_reference_issue_count"
            )
            or 0
        )
        == 0
        and int(
            article_supplement_kg_navigation_index_summary.get(
                "missing_source_artifact_count"
            )
            or 0
        )
        == 0
        and article_supplement_kg_navigation_index_summary.get(
            "main_results_positive_boundary_blocked"
        )
        is True
        and article_supplement_kg_navigation_index_summary.get(
            "venn_abers_negative_boundary_preserved"
        )
        is True
        and article_supplement_kg_navigation_index_summary.get(
            "scientific_no_method_promotion_guard_active"
        )
        is True
        and int(
            article_supplement_kg_navigation_index_summary.get(
                "neutral_language_unguarded_hit_count"
            )
            or 0
        )
        == 0
        and article_supplement_kg_navigation_index_summary.get(
            "final_navigation_release_authorized"
        )
        is False
        and article_supplement_kg_navigation_index_summary.get(
            "final_manuscript_prose_permission"
        )
        is False
        and article_supplement_kg_navigation_index_summary.get(
            "final_visual_table_retention_authorized"
        )
        is False
        and article_supplement_kg_navigation_index_summary.get(
            "publication_site_deployment_authorized"
        )
        is False
        and article_supplement_kg_navigation_index_summary.get(
            "kg_citable_component_authorized"
        )
        is False
        and article_supplement_kg_navigation_index_summary.get(
            "sterile_repository_creation_authorized"
        )
        is False
        and article_supplement_kg_navigation_index_summary.get(
            "working_repository_final_citable"
        )
        is False
        and article_supplement_kg_navigation_index_summary.get(
            "method_recommendation_authorized"
        )
        is False
        and article_supplement_kg_navigation_index_summary.get(
            "positive_claim_promotion_authorized"
        )
        is False
        and int(
            article_supplement_kg_navigation_index_summary.get(
                "failed_check_count"
            )
            or 0
        )
        == 0
    )
    publication_phase_progress_reconciliation_clean = (
        publication_phase_progress_reconciliation_summary.get("overall_status")
        == "publication_phase_progress_reconciliation_ready_no_final_outputs"
        and publication_phase_progress_reconciliation_summary.get("phase_state")
        == "neutral_publication_progress_reconciled_final_outputs_blocked"
        and int(
            publication_phase_progress_reconciliation_summary.get(
                "pre_prose_completed_control_count"
            )
            or 0
        )
        == 8
        and int(
            publication_phase_progress_reconciliation_summary.get(
                "pre_prose_control_count"
            )
            or 0
        )
        == 8
        and int(
            publication_phase_progress_reconciliation_summary.get(
                "resolved_prior_blocker_count"
            )
            or 0
        )
        == 2
        and int(
            publication_phase_progress_reconciliation_summary.get(
                "active_final_blocker_count"
            )
            or 0
        )
        == 10
        and int(
            publication_phase_progress_reconciliation_summary.get(
                "stale_goal_blocker_count"
            )
            or 0
        )
        == 0
        and publication_phase_progress_reconciliation_summary.get(
            "reviewer_design_reconciled"
        )
        is True
        and publication_phase_progress_reconciliation_summary.get(
            "pre_retention_visual_audit_completed"
        )
        is True
        and publication_phase_progress_reconciliation_summary.get(
            "claim_boundary_navigation_ready"
        )
        is True
        and publication_phase_progress_reconciliation_summary.get(
            "release_gap_ready"
        )
        is True
        and publication_phase_progress_reconciliation_summary.get(
            "neutral_guard_ready"
        )
        is True
        and publication_phase_progress_reconciliation_summary.get(
            "kg_publication_ready"
        )
        is True
        and publication_phase_progress_reconciliation_summary.get(
            "final_publication_visual_auditor_feedback_ready"
        )
        is True
        and publication_phase_progress_reconciliation_summary.get(
            "final_publication_visual_auditor_status"
        )
        == "feedback_loop_ready_no_final_retention"
        and publication_phase_progress_reconciliation_summary.get(
            "goal_can_mark_complete"
        )
        is False
        and int(
            publication_phase_progress_reconciliation_summary.get(
                "paper_blocked_gate_count"
            )
            or 0
        )
        == 6
        and int(
            publication_phase_progress_reconciliation_summary.get(
                "positive_claim_ready_gate_count"
            )
            or 0
        )
        == 0
        and publication_phase_progress_reconciliation_summary.get(
            "main_results_positive_boundary_blocked"
        )
        is True
        and publication_phase_progress_reconciliation_summary.get(
            "venn_abers_negative_boundary_preserved"
        )
        is True
        and publication_phase_progress_reconciliation_summary.get(
            "validated_venn_abers_regression_claim_ready"
        )
        is False
        and publication_phase_progress_reconciliation_summary.get(
            "final_manuscript_prose_permission"
        )
        is False
        and publication_phase_progress_reconciliation_summary.get(
            "manuscript_drafting_authorized"
        )
        is False
        and publication_phase_progress_reconciliation_summary.get(
            "latex_html_authoring_authorized"
        )
        is False
        and publication_phase_progress_reconciliation_summary.get(
            "final_visual_table_retention_authorized"
        )
        is False
        and publication_phase_progress_reconciliation_summary.get(
            "publication_site_deployment_authorized"
        )
        is False
        and publication_phase_progress_reconciliation_summary.get(
            "kg_citable_component_authorized"
        )
        is False
        and publication_phase_progress_reconciliation_summary.get(
            "sterile_repository_creation_authorized"
        )
        is False
        and publication_phase_progress_reconciliation_summary.get(
            "working_repository_final_citable"
        )
        is False
        and publication_phase_progress_reconciliation_summary.get(
            "method_recommendation_authorized"
        )
        is False
        and publication_phase_progress_reconciliation_summary.get(
            "positive_claim_promotion_authorized"
        )
        is False
        and int(
            publication_phase_progress_reconciliation_summary.get(
                "neutral_language_unguarded_hit_count"
            )
            or 0
        )
        == 0
        and int(
            publication_phase_progress_reconciliation_summary.get(
                "missing_source_artifact_count"
            )
            or 0
        )
        == 0
        and int(
            publication_phase_progress_reconciliation_summary.get(
                "failed_check_count"
            )
            or 0
        )
        == 0
    )
    neutral_reporting_language_clean = (
        neutral_reporting_language_summary.get("overall_status")
        == "neutral_reporting_language_audit_pass"
        and int(neutral_reporting_language_summary.get("failed_check_count") or 0) == 0
        and int(neutral_reporting_language_summary.get("unguarded_hit_count") or 0)
        == 0
    )
    scientific_neutrality_interpretation_lock_clean = (
        scientific_neutrality_interpretation_lock_summary.get("overall_status")
        == "scientific_neutrality_interpretation_lock_ready_no_method_promotion"
        and scientific_neutrality_interpretation_lock_summary.get("phase_state")
        == "neutral_interpretation_locked_final_claims_and_outputs_blocked"
        and int(
            scientific_neutrality_interpretation_lock_summary.get(
                "interpretation_row_count"
            )
            or 0
        )
        == 8
        and scientific_neutrality_interpretation_lock_summary.get(
            "cqr_cvplus_reporting_role"
        )
        == "descriptive_diagnostic_no_final_selection_no_method_promotion"
        and scientific_neutrality_interpretation_lock_summary.get(
            "venn_abers_reporting_role"
        )
        == "negative_failure_mode_no_validated_regression_claim"
        and scientific_neutrality_interpretation_lock_summary.get(
            "main_results_positive_boundary_blocked"
        )
        is True
        and scientific_neutrality_interpretation_lock_summary.get(
            "venn_abers_negative_boundary_preserved"
        )
        is True
        and scientific_neutrality_interpretation_lock_summary.get(
            "validated_venn_abers_regression_claim_ready"
        )
        is False
        and scientific_neutrality_interpretation_lock_summary.get(
            "method_recommendation_authorized"
        )
        is False
        and scientific_neutrality_interpretation_lock_summary.get(
            "positive_claim_promotion_authorized"
        )
        is False
        and scientific_neutrality_interpretation_lock_summary.get(
            "final_manuscript_prose_permission"
        )
        is False
        and scientific_neutrality_interpretation_lock_summary.get(
            "sterile_repository_creation_authorized"
        )
        is False
        and scientific_neutrality_interpretation_lock_summary.get(
            "working_repository_final_citable"
        )
        is False
        and scientific_neutrality_interpretation_lock_summary.get(
            "scientific_test_not_method_promotion"
        )
        is True
        and scientific_neutrality_interpretation_lock_summary.get(
            "analysis_only_no_champion_method"
        )
        is True
        and scientific_neutrality_interpretation_lock_summary.get(
            "method_champion_authorized"
        )
        is False
        and scientific_neutrality_interpretation_lock_summary.get(
            "method_advocacy_authorized"
        )
        is False
        and scientific_neutrality_interpretation_lock_summary.get(
            "result_reporting_policy"
        )
        == "analysis_only_report_observed_behavior_no_method_advocacy"
        and int(
            scientific_neutrality_interpretation_lock_summary.get(
                "neutral_language_unguarded_hit_count"
            )
            or 0
        )
        == 0
        and int(
            scientific_neutrality_interpretation_lock_summary.get(
                "missing_source_artifact_count"
            )
            or 0
        )
        == 0
        and int(
            scientific_neutrality_interpretation_lock_summary.get(
                "authorization_violation_count"
            )
            or 0
        )
        == 0
        and int(
            scientific_neutrality_interpretation_lock_summary.get(
                "promotional_phrase_hit_count"
            )
            or 0
        )
        == 0
        and int(
            scientific_neutrality_interpretation_lock_summary.get(
                "failed_check_count"
            )
            or 0
        )
        == 0
    )
    final_publication_output_authorization_protocol_clean = (
        final_publication_output_authorization_protocol_summary.get("overall_status")
        == "final_publication_output_authorization_protocol_ready_no_authorizations"
        and final_publication_output_authorization_protocol_summary.get("phase_state")
        == "neutral_final_output_authorization_protocol_defined_outputs_blocked"
        and final_publication_output_authorization_protocol_summary.get(
            "final_output_authorization_protocol_status"
        )
        == "protocol_ready_all_final_outputs_blocked"
        and int(
            final_publication_output_authorization_protocol_summary.get(
                "authorization_row_count"
            )
            or 0
        )
        == 10
        and int(
            final_publication_output_authorization_protocol_summary.get(
                "blocked_authorization_row_count"
            )
            or 0
        )
        == 10
        and int(
            final_publication_output_authorization_protocol_summary.get(
                "missing_policy_row_count"
            )
            or 0
        )
        == 0
        and int(
            final_publication_output_authorization_protocol_summary.get(
                "ready_to_authorize_output_count"
            )
            or 0
        )
        == 0
        and int(
            final_publication_output_authorization_protocol_summary.get(
                "active_final_blocker_count"
            )
            or 0
        )
        == 10
        and final_publication_output_authorization_protocol_summary.get(
            "goal_can_mark_complete"
        )
        is False
        and final_publication_output_authorization_protocol_summary.get(
            "neutral_empirical_phase_complete"
        )
        is True
        and final_publication_output_authorization_protocol_summary.get(
            "scientific_test_not_method_promotion"
        )
        is True
        and int(
            final_publication_output_authorization_protocol_summary.get(
                "paper_blocked_gate_count"
            )
            or 0
        )
        == 6
        and int(
            final_publication_output_authorization_protocol_summary.get(
                "positive_claim_ready_gate_count"
            )
            or 0
        )
        == 0
        and int(
            final_publication_output_authorization_protocol_summary.get(
                "release_authorized_count"
            )
            or 0
        )
        == 0
        and final_publication_output_authorization_protocol_summary.get(
            "final_manuscript_prose_permission"
        )
        is False
        and final_publication_output_authorization_protocol_summary.get(
            "final_visual_table_retention_authorized"
        )
        is False
        and final_publication_output_authorization_protocol_summary.get(
            "latex_html_authoring_authorized"
        )
        is False
        and final_publication_output_authorization_protocol_summary.get(
            "publication_site_deployment_authorized"
        )
        is False
        and final_publication_output_authorization_protocol_summary.get(
            "kg_citable_component_authorized"
        )
        is False
        and final_publication_output_authorization_protocol_summary.get(
            "sterile_repository_creation_authorized"
        )
        is False
        and final_publication_output_authorization_protocol_summary.get(
            "working_repository_final_citable"
        )
        is False
        and final_publication_output_authorization_protocol_summary.get(
            "method_recommendation_authorized"
        )
        is False
        and final_publication_output_authorization_protocol_summary.get(
            "positive_claim_promotion_authorized"
        )
        is False
        and final_publication_output_authorization_protocol_summary.get(
            "analysis_only_no_champion_method"
        )
        is True
        and final_publication_output_authorization_protocol_summary.get(
            "method_champion_authorized"
        )
        is False
        and final_publication_output_authorization_protocol_summary.get(
            "method_advocacy_authorized"
        )
        is False
        and final_publication_output_authorization_protocol_summary.get(
            "result_reporting_policy"
        )
        == "analysis_only_report_observed_behavior_no_method_advocacy"
        and int(
            final_publication_output_authorization_protocol_summary.get(
                "authorization_violation_count"
            )
            or 0
        )
        == 0
        and int(
            final_publication_output_authorization_protocol_summary.get(
                "missing_source_artifact_count"
            )
            or 0
        )
        == 0
        and int(
            final_publication_output_authorization_protocol_summary.get(
                "failed_check_count"
            )
            or 0
        )
        == 0
    )
    publication_claim_evidence_verification_matrix_clean = (
        publication_claim_evidence_verification_matrix_summary.get("overall_status")
        == "publication_claim_evidence_verification_ready_no_final_prose"
        and publication_claim_evidence_verification_matrix_summary.get("phase_state")
        == (
            "neutral_pre_prose_claim_evidence_verification_active_"
            "final_outputs_blocked"
        )
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "verification_row_count"
            )
            or 0
        )
        == 8
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "verification_pass_count"
            )
            or 0
        )
        == 8
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "source_traceable_row_count"
            )
            or 0
        )
        == 8
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "boundary_aligned_row_count"
            )
            or 0
        )
        == 8
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "navigation_aligned_row_count"
            )
            or 0
        )
        == 8
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "kg_reference_issue_count"
            )
            or 0
        )
        == 0
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "safe_pre_prose_evidence_row_count"
            )
            or 0
        )
        == 7
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "blocked_positive_row_count"
            )
            or 0
        )
        == 1
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "main_results_blocked_row_count"
            )
            or 0
        )
        == 1
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "venn_abers_negative_ready_row_count"
            )
            or 0
        )
        == 1
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "missing_source_artifact_count"
            )
            or 0
        )
        == 0
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "source_authorization_violation_count"
            )
            or 0
        )
        == 0
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "row_authorization_violation_count"
            )
            or 0
        )
        == 0
        and publication_claim_evidence_verification_matrix_summary.get(
            "final_manuscript_prose_permission"
        )
        is False
        and publication_claim_evidence_verification_matrix_summary.get(
            "final_visual_table_retention_authorized"
        )
        is False
        and publication_claim_evidence_verification_matrix_summary.get(
            "latex_html_authoring_authorized"
        )
        is False
        and publication_claim_evidence_verification_matrix_summary.get(
            "release_authorized"
        )
        is False
        and publication_claim_evidence_verification_matrix_summary.get(
            "method_recommendation_authorized"
        )
        is False
        and publication_claim_evidence_verification_matrix_summary.get(
            "method_champion_authorized"
        )
        is False
        and publication_claim_evidence_verification_matrix_summary.get(
            "method_advocacy_authorized"
        )
        is False
        and publication_claim_evidence_verification_matrix_summary.get(
            "positive_claim_promotion_authorized"
        )
        is False
        and publication_claim_evidence_verification_matrix_summary.get(
            "analysis_only_no_champion_method"
        )
        is True
        and publication_claim_evidence_verification_matrix_summary.get(
            "result_reporting_policy"
        )
        == "analysis_only_report_observed_behavior_no_method_advocacy"
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "neutral_language_unguarded_hit_count"
            )
            or 0
        )
        == 0
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "kg_isolated_node_count"
            )
            or 0
        )
        == 0
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "current_publication_draft_artifact_count"
            )
            or 0
        )
        == 5
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "current_publication_draft_artifact_pass_count"
            )
            or 0
        )
        == 5
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "current_publication_draft_artifact_traceable_count"
            )
            or 0
        )
        == 5
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "current_publication_draft_missing_source_key_count"
            )
            or 0
        )
        == 0
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "current_publication_draft_missing_artifact_count"
            )
            or 0
        )
        == 0
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "current_publication_draft_authorization_violation_count"
            )
            or 0
        )
        == 0
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "current_publication_draft_failed_upstream_check_count"
            )
            or 0
        )
        == 0
        and int(
            publication_claim_evidence_verification_matrix_summary.get(
                "failed_check_count"
            )
            or 0
        )
        == 0
    )
    sterile_repository_staging_manifest_clean = (
        sterile_repository_staging_manifest_summary.get("overall_status")
        == "sterile_repository_staging_manifest_ready_no_repository_created"
        and sterile_repository_staging_manifest_summary.get("phase_state")
        == "neutral_sterile_repository_manifest_ready_creation_blocked"
        and sterile_repository_staging_manifest_summary.get(
            "staging_manifest_status"
        )
        == "manifest_ready_creation_and_release_blocked"
        and int(
            sterile_repository_staging_manifest_summary.get(
                "required_content_row_count"
            )
            or 0
        )
        == 9
        and int(
            sterile_repository_staging_manifest_summary.get(
                "required_content_traceable_count"
            )
            or 0
        )
        == 9
        and int(
            sterile_repository_staging_manifest_summary.get(
                "required_content_with_blocking_gate_count"
            )
            or 0
        )
        == 9
        and int(
            sterile_repository_staging_manifest_summary.get(
                "candidate_inclusion_risk_hit_count"
            )
            or 0
        )
        == 0
        and int(
            sterile_repository_staging_manifest_summary.get(
                "post_program_exclusion_rule_count"
            )
            or 0
        )
        == 3
        and int(
            sterile_repository_staging_manifest_summary.get(
                "expanded_exclusion_rule_count"
            )
            or 0
        )
        == 9
        and int(
            sterile_repository_staging_manifest_summary.get(
                "exclusion_policy_row_count"
            )
            or 0
        )
        == 12
        and int(
            sterile_repository_staging_manifest_summary.get(
                "exclusion_source_traceable_count"
            )
            or 0
        )
        == 12
        and int(
            sterile_repository_staging_manifest_summary.get(
                "missing_source_artifact_count"
            )
            or 0
        )
        == 0
        and sterile_repository_staging_manifest_summary.get(
            "repository_visibility_at_creation"
        )
        == "private"
        and sterile_repository_staging_manifest_summary.get(
            "working_repository_citation_status"
        )
        == "not_final_citable_repository"
        and sterile_repository_staging_manifest_summary.get(
            "private_repository_created"
        )
        is False
        and sterile_repository_staging_manifest_summary.get(
            "sterile_repository_creation_authorized"
        )
        is False
        and sterile_repository_staging_manifest_summary.get(
            "sterile_release_packaging_authorized"
        )
        is False
        and sterile_repository_staging_manifest_summary.get("release_authorized")
        is False
        and sterile_repository_staging_manifest_summary.get(
            "final_manuscript_prose_permission"
        )
        is False
        and sterile_repository_staging_manifest_summary.get(
            "final_visual_table_retention_authorized"
        )
        is False
        and sterile_repository_staging_manifest_summary.get(
            "latex_html_authoring_authorized"
        )
        is False
        and sterile_repository_staging_manifest_summary.get(
            "publication_site_deployment_authorized"
        )
        is False
        and sterile_repository_staging_manifest_summary.get(
            "kg_citable_component_authorized"
        )
        is False
        and sterile_repository_staging_manifest_summary.get(
            "working_repository_final_citable"
        )
        is False
        and sterile_repository_staging_manifest_summary.get(
            "method_recommendation_authorized"
        )
        is False
        and sterile_repository_staging_manifest_summary.get(
            "positive_claim_promotion_authorized"
        )
        is False
        and sterile_repository_staging_manifest_summary.get(
            "analysis_only_no_champion_method"
        )
        is True
        and sterile_repository_staging_manifest_summary.get(
            "method_champion_authorized"
        )
        is False
        and sterile_repository_staging_manifest_summary.get(
            "method_advocacy_authorized"
        )
        is False
        and sterile_repository_staging_manifest_summary.get(
            "result_reporting_policy"
        )
        == "analysis_only_report_observed_behavior_no_method_advocacy"
        and int(
            sterile_repository_staging_manifest_summary.get(
                "authorization_violation_count"
            )
            or 0
        )
        == 0
        and int(
            sterile_repository_staging_manifest_summary.get("failed_check_count")
            or 0
        )
        == 0
    )
    neutral_experiment_closure_clean = (
        neutral_experiment_closure_summary.get("overall_status")
        in {
            "neutral_experiment_closure_ready",
            "neutral_experiment_closure_ready_for_goal_policy_update",
        }
        and neutral_experiment_closure_summary.get("neutral_closure_ready") is True
        and int(neutral_experiment_closure_summary.get("failed_check_count") or 0)
        == 0
    )
    if failures:
        overall_status = "fail"
    elif not hard_leakage_clean:
        overall_status = "fail"
    elif not claim_register_clean:
        overall_status = "fail"
    elif not final_selection_clean:
        overall_status = "fail"
    elif not fairness_group_diagnostic_clean:
        overall_status = "fail"
    elif not fairness_group_multiplicity_scope_clean:
        overall_status = "fail"
    elif not fairness_population_clean:
        overall_status = "fail"
    elif not publication_clean:
        overall_status = "fail"
    elif not method_literature_clean:
        overall_status = "fail"
    elif not selection_multiplicity_clean:
        overall_status = "fail"
    elif not bounded_support_clean:
        overall_status = "fail"
    elif not target_domain_provenance_clean:
        overall_status = "fail"
    elif not external_source_discovery_clean:
        overall_status = "fail"
    elif not bounded_support_posthandling_clean:
        overall_status = "fail"
    elif not bounded_support_dataset_clean:
        overall_status = "fail"
    elif not bounded_support_endpoint_closure_clean:
        overall_status = "fail"
    elif not bounded_support_positive_validation_clean:
        overall_status = "fail"
    elif not experiment_accounting_clean:
        overall_status = "fail"
    elif not method_performance_clean:
        overall_status = "fail"
    elif not method_selection_candidate_clean:
        overall_status = "fail"
    elif not method_selection_robustness_clean:
        overall_status = "fail"
    elif not method_selection_alpha_expansion_clean:
        overall_status = "fail"
    elif not method_selection_post_selection_validation_batch_clean:
        overall_status = "fail"
    elif not method_selection_post_selection_validation_results_clean:
        overall_status = "fail"
    elif not selection_multiplicity_evidence_clean:
        overall_status = "fail"
    elif not method_selection_alpha_expansion_execution_clean:
        overall_status = "fail"
    elif not method_selection_inferential_clean:
        overall_status = "fail"
    elif not manuscript_readiness_clean:
        overall_status = "fail"
    elif not manuscript_bundle_eligibility_clean:
        overall_status = "fail"
    elif not dataset_specific_final_gate_clean:
        overall_status = "fail"
    elif not dataset_final_bridge_clean:
        overall_status = "fail"
    elif not dataset_final_bridge_results_clean:
        overall_status = "fail"
    elif not main_result_candidate_plan_clean:
        overall_status = "fail"
    elif not main_result_candidate_results_clean:
        overall_status = "fail"
    elif not main_result_candidate_closure_clean:
        overall_status = "fail"
    elif not dataset_final_remediation_clean:
        overall_status = "fail"
    elif not duplicate_content_quarantine_clean:
        overall_status = "fail"
    elif not venn_abers_negative_disposition_clean:
        overall_status = "fail"
    elif not venn_abers_validation_clean:
        overall_status = "fail"
    elif not venn_abers_grid_ivapd_clean:
        overall_status = "fail"
    elif not venn_abers_grid_expansion_clean:
        overall_status = "fail"
    elif not venn_abers_grid_failure_modes_clean:
        overall_status = "fail"
    elif not venn_abers_claim_gate_matrix_clean:
        overall_status = "fail"
    elif not graph_artifact_clean:
        overall_status = "fail"
    elif not duplicate_closure_clean:
        overall_status = "fail"
    elif kg_status == "fail":
        overall_status = "fail"
    elif not kg_publication_clean:
        overall_status = "fail"
    elif not scientific_review_clean:
        overall_status = "fail"
    elif not publication_activation_clean:
        overall_status = "fail"
    elif not publication_preparation_packets_clean:
        overall_status = "fail"
    elif not reviewer_design_brief_clean:
        overall_status = "fail"
    elif not publication_visual_audit_plan_clean:
        overall_status = "fail"
    elif not visual_table_audit_report_clean:
        overall_status = "fail"
    elif not visual_table_render_candidate_audit_clean:
        overall_status = "fail"
    elif not publication_retention_readiness_audit_clean:
        overall_status = "fail"
    elif not final_publication_visual_auditor_readiness_clean:
        overall_status = "fail"
    elif not neutral_result_ledger_clean:
        overall_status = "fail"
    elif not article_supplement_blueprint_alignment_clean:
        overall_status = "fail"
    elif not publication_release_gap_register_clean:
        overall_status = "fail"
    elif not individual_experiment_report_blueprint_clean:
        overall_status = "fail"
    elif not claim_safe_result_extraction_matrix_clean:
        overall_status = "fail"
    elif not manuscript_section_evidence_packet_clean:
        overall_status = "fail"
    elif not section_claim_boundary_audit_clean:
        overall_status = "fail"
    elif not article_supplement_kg_navigation_index_clean:
        overall_status = "fail"
    elif not publication_phase_progress_reconciliation_clean:
        overall_status = "fail"
    elif not neutral_reporting_language_clean:
        overall_status = "fail"
    elif not scientific_neutrality_interpretation_lock_clean:
        overall_status = "fail"
    elif not final_publication_output_authorization_protocol_clean:
        overall_status = "fail"
    elif not publication_claim_evidence_verification_matrix_clean:
        overall_status = "fail"
    elif not sterile_repository_staging_manifest_clean:
        overall_status = "fail"
    elif not neutral_experiment_closure_clean:
        overall_status = "fail"
    elif (controls_summary.get("control_status_counts") or {}).get("caveat"):
        overall_status = "pass_with_caveats"
    elif int(scientific_review_summary.get("tracked_caveat_count") or 0) > 0:
        overall_status = "pass_with_caveats"
    else:
        overall_status = "pass"

    return {
        "overall_status": overall_status,
        "step_status_counts": dict(
            sorted(Counter(step["status"] for step in step_results).items())
        ),
        "failed_required_steps": failures,
        "hard_leakage_clean_in_scanned_artifacts": hard_leakage_clean,
        "cross_run": {
            "reports_scanned": cross_summary.get("reports_scanned"),
            "configs_scanned": cross_summary.get("configs_scanned"),
            "total_completed_rows": cross_summary.get("total_completed_rows"),
            "blocking_issue_counts": cross_summary.get("blocking_issue_counts", {}),
            "caveat_counts": cross_summary.get("caveat_counts", {}),
            "unsupported_claim_hits": cross_summary.get("unsupported_claim_hits"),
            "leakage_status": cross_summary.get("leakage_status"),
        },
        "retrospective_controls": {
            "control_status_counts": controls_summary.get("control_status_counts", {}),
            "control_severity_counts": controls_summary.get(
                "control_severity_counts", {}
            ),
            "hard_leakage_status": controls_summary.get("hard_leakage_status"),
        },
        "feature_leakage_metadata": {
            "caveat_rows_triaged": feature_summary.get("caveat_rows_triaged"),
            "triaged_report_count": feature_summary.get("triaged_report_count"),
            "runner_feature_drop_guard_ok": feature_summary.get(
                "runner_feature_drop_guard_ok"
            ),
            "hard_feature_leakage_violation_row_count": feature_summary.get(
                "hard_feature_leakage_violation_row_count"
            ),
            "legacy_provenance_gap_row_count": feature_summary.get(
                "legacy_provenance_gap_row_count"
            ),
            "field_metadata_incomplete_row_count": feature_summary.get(
                "field_metadata_incomplete_row_count"
            ),
            "full_preprocessing_lineage_claim_supported": feature_summary.get(
                "full_preprocessing_lineage_claim_supported"
            ),
            "metadata_limitation_class_counts": feature_summary.get(
                "metadata_limitation_class_counts",
                {},
            ),
            "provenance_limitation_class_counts": feature_summary.get(
                "provenance_limitation_class_counts",
                {},
            ),
        },
        "remediation_backlog": {
            "action_count": backlog_summary.get("action_count"),
            "open_action_count": backlog_summary.get("open_action_count"),
            "covered_action_count": backlog_summary.get("covered_action_count"),
            "status_counts": backlog_summary.get("status_counts", {}),
            "severity_counts": backlog_summary.get("severity_counts", {}),
            "category_counts": backlog_summary.get("category_counts", {}),
            "open_severity_counts": backlog_summary.get("open_severity_counts", {}),
            "open_category_counts": backlog_summary.get("open_category_counts", {}),
        },
        "duplicate_sensitivity_closure": {
            "overall_status": duplicate_closure_summary.get("overall_status"),
            "duplicate_action_count": duplicate_closure_summary.get(
                "duplicate_action_count"
            ),
            "duplicate_caveat_count": duplicate_closure_summary.get(
                "duplicate_caveat_count"
            ),
            "row_signature_caveat_count": duplicate_closure_summary.get(
                "row_signature_caveat_count"
            ),
            "model_visible_caveat_count": duplicate_closure_summary.get(
                "model_visible_caveat_count"
            ),
            "open_action_count": duplicate_closure_summary.get("open_action_count"),
            "covered_action_count": duplicate_closure_summary.get(
                "covered_action_count"
            ),
            "tracked_caveat_action_count": duplicate_closure_summary.get(
                "tracked_caveat_action_count"
            ),
            "covered_action_status_counts": duplicate_closure_summary.get(
                "covered_action_status_counts",
                {},
            ),
            "tracked_caveat_status_counts": duplicate_closure_summary.get(
                "tracked_caveat_status_counts",
                {},
            ),
            "covered_actions_output_contract_status": duplicate_output_contract.get(
                "status"
            ),
            "hard_failed_check_count": duplicate_closure_summary.get(
                "hard_failed_check_count"
            ),
            "scoped_caveat_check_count": duplicate_closure_summary.get(
                "scoped_caveat_check_count"
            ),
            "paired_dataset_count": duplicate_closure_summary.get(
                "paired_dataset_count"
            ),
            "paired_comparison_rows": duplicate_closure_summary.get(
                "paired_comparison_rows"
            ),
            "final_blocked_requirement_count": duplicate_closure_summary.get(
                "final_blocked_requirement_count"
            ),
        },
        "endpoint_backfill_feasibility": {
            "ready_count": endpoint_summary.get("ready_count"),
            "blocked_count": endpoint_summary.get("blocked_count"),
            "status_counts": endpoint_summary.get("status_counts", {}),
            "completed_ledger_rows_ready": endpoint_summary.get(
                "completed_ledger_rows_ready"
            ),
        },
        "manuscript_manifest_completeness": {
            "overall_status": manuscript_summary.get("overall_status"),
            "manifest_count": manuscript_summary.get("manifest_count"),
            "status_counts": manuscript_summary.get("status_counts", {}),
            "bundle_index_status": manuscript_summary.get("bundle_index_status"),
            "bundle_index_manifest_count": manuscript_summary.get(
                "bundle_index_manifest_count"
            ),
        },
        "manuscript_claim_register_consistency": {
            "overall_status": claim_register_summary.get("overall_status"),
            "claim_count": claim_register_summary.get("claim_count"),
            "status_counts": claim_register_summary.get("status_counts", {}),
            "failed_claim_count": claim_register_summary.get("failed_claim_count"),
        },
        "final_selection_claim_boundary": {
            "overall_status": final_selection_summary.get("overall_status"),
            "claim_status": final_selection_summary.get("claim_status"),
            "open_remediation_actions": final_selection_summary.get(
                "open_remediation_actions"
            ),
            "blocked_requirement_count": final_selection_summary.get(
                "blocked_requirement_count"
            ),
            "pass_requirement_count": final_selection_summary.get(
                "pass_requirement_count"
            ),
            "failed_check_count": final_selection_summary.get("failed_check_count"),
        },
        "fairness_sampling_weight_policy": {
            "overall_status": fairness_sampling_weight_policy_summary.get(
                "overall_status"
            ),
            "action_status": fairness_sampling_weight_policy_summary.get(
                "action_status"
            ),
            "policy_declared_bundle_count": (
                fairness_sampling_weight_policy_summary.get(
                    "policy_declared_bundle_count"
                )
            ),
            "weighted_estimand_applied_bundle_count": (
                fairness_sampling_weight_policy_summary.get(
                    "weighted_estimand_applied_bundle_count"
                )
            ),
            "unweighted_diagnostic_only_bundle_count": (
                fairness_sampling_weight_policy_summary.get(
                    "unweighted_diagnostic_only_bundle_count"
                )
            ),
            "population_fairness_ready_bundle_count": (
                fairness_sampling_weight_policy_summary.get(
                    "population_fairness_ready_bundle_count"
                )
            ),
            "failed_check_count": fairness_sampling_weight_policy_summary.get(
                "failed_check_count"
            ),
        },
        "fairness_group_diagnostic_audit": {
            "overall_status": fairness_group_diagnostic_summary.get("overall_status"),
            "action_status": fairness_group_diagnostic_summary.get("action_status"),
            "bundle_count": fairness_group_diagnostic_summary.get("bundle_count"),
            "dataset_count": fairness_group_diagnostic_summary.get("dataset_count"),
            "group_counts_recorded_bundle_count": (
                fairness_group_diagnostic_summary.get(
                    "group_counts_recorded_bundle_count"
                )
            ),
            "missingness_by_group_audited_bundle_count": (
                fairness_group_diagnostic_summary.get(
                    "missingness_by_group_audited_bundle_count"
                )
            ),
            "coverage_by_group_recorded_bundle_count": (
                fairness_group_diagnostic_summary.get(
                    "coverage_by_group_recorded_bundle_count"
                )
            ),
            "width_by_group_recorded_bundle_count": (
                fairness_group_diagnostic_summary.get(
                    "width_by_group_recorded_bundle_count"
                )
            ),
            "group_gap_uncertainty_recorded_bundle_count": (
                fairness_group_diagnostic_summary.get(
                    "group_gap_uncertainty_recorded_bundle_count"
                )
            ),
            "failed_check_count": fairness_group_diagnostic_summary.get(
                "failed_check_count"
            ),
        },
        "fairness_group_multiplicity_scope": {
            "overall_status": fairness_group_multiplicity_scope_summary.get(
                "overall_status"
            ),
            "action_status": fairness_group_multiplicity_scope_summary.get(
                "action_status"
            ),
            "bundle_count": fairness_group_multiplicity_scope_summary.get(
                "bundle_count"
            ),
            "dataset_count": fairness_group_multiplicity_scope_summary.get(
                "dataset_count"
            ),
            "comparison_family_count": (
                fairness_group_multiplicity_scope_summary.get(
                    "comparison_family_count"
                )
            ),
            "pairwise_group_comparison_count": (
                fairness_group_multiplicity_scope_summary.get(
                    "pairwise_group_comparison_count"
                )
            ),
            "multiplicity_scope_declared_bundle_count": (
                fairness_group_multiplicity_scope_summary.get(
                    "multiplicity_scope_declared_bundle_count"
                )
            ),
            "claim_register_cites_multiplicity_record": (
                fairness_group_multiplicity_scope_summary.get(
                    "claim_register_cites_multiplicity_record"
                )
            ),
            "current_manuscript_fairness_population_claim_ready": (
                fairness_group_multiplicity_scope_summary.get(
                    "current_manuscript_fairness_population_claim_ready"
                )
            ),
            "failed_check_count": fairness_group_multiplicity_scope_summary.get(
                "failed_check_count"
            ),
        },
        "fairness_population_readiness": {
            "overall_status": fairness_population_summary.get("overall_status"),
            "can_support_publication_ready_fairness": fairness_population_summary.get(
                "can_support_publication_ready_fairness"
            ),
            "fairness_population_claim_status": fairness_population_summary.get(
                "fairness_population_claim_status"
            ),
            "fairness_requirement_status": fairness_population_summary.get(
                "fairness_requirement_status"
            ),
            "final_selection_claim_status": fairness_population_summary.get(
                "final_selection_claim_status"
            ),
            "bundle_count": fairness_population_summary.get("bundle_count"),
            "diagnostic_group_bundle_count": fairness_population_summary.get(
                "diagnostic_group_bundle_count"
            ),
            "explicit_nonclaim_boundary_bundle_count": fairness_population_summary.get(
                "explicit_nonclaim_boundary_bundle_count"
            ),
            "population_fairness_ready_bundle_count": fairness_population_summary.get(
                "population_fairness_ready_bundle_count"
            ),
            "sampling_weight_policy_declared_bundle_count": (
                fairness_population_summary.get(
                    "sampling_weight_policy_declared_bundle_count"
                )
            ),
            "weighted_estimand_applied_bundle_count": (
                fairness_population_summary.get(
                    "weighted_estimand_applied_bundle_count"
                )
            ),
            "sampling_weight_policy_artifact_status": (
                fairness_population_summary.get(
                    "sampling_weight_policy_artifact_status"
                )
            ),
            "failed_check_count": fairness_population_summary.get("failed_check_count"),
        },
        "publication_methodology_readiness": {
            "overall_status": publication_summary.get("overall_status"),
            "reports_scanned": publication_summary.get("reports_scanned"),
            "total_completed_rows": publication_summary.get("total_completed_rows"),
            "unsupported_claim_hits": publication_summary.get("unsupported_claim_hits"),
            "open_remediation_actions": publication_summary.get(
                "open_remediation_actions"
            ),
            "blocked_final_requirement_count": publication_summary.get(
                "blocked_final_requirement_count"
            ),
            "failed_check_count": publication_summary.get("failed_check_count"),
            "can_support_final_method_selection": publication_summary.get(
                "can_support_final_method_selection"
            ),
            "can_support_publication_ready_fairness": publication_summary.get(
                "can_support_publication_ready_fairness"
            ),
            "can_support_bounded_support_validity": publication_summary.get(
                "can_support_bounded_support_validity"
            ),
            "can_support_venn_abers_regression_validation": publication_summary.get(
                "can_support_venn_abers_regression_validation"
            ),
        },
        "venn_abers_validation_readiness": {
            "overall_status": venn_abers_validation_summary.get("overall_status"),
            "can_support_venn_abers_regression_validation": venn_abers_validation_summary.get(
                "can_support_venn_abers_regression_validation"
            ),
            "failed_check_count": venn_abers_validation_summary.get(
                "failed_check_count"
            ),
            "diagnostic_panel_count": venn_abers_validation_summary.get(
                "diagnostic_panel_count"
            ),
            "undercoverage_panel_count": venn_abers_validation_summary.get(
                "undercoverage_panel_count"
            ),
            "diagnostic_run_count": venn_abers_validation_summary.get(
                "diagnostic_run_count"
            ),
            "undercoverage_run_count": venn_abers_validation_summary.get(
                "undercoverage_run_count"
            ),
            "min_venn_abers_run_coverage": venn_abers_validation_summary.get(
                "min_venn_abers_run_coverage"
            ),
            "max_venn_abers_run_coverage": venn_abers_validation_summary.get(
                "max_venn_abers_run_coverage"
            ),
            "grid_reference_stronger_panel_count": venn_abers_validation_summary.get(
                "grid_reference_stronger_panel_count"
            ),
            "split_fallback_near_nominal_panel_count": venn_abers_validation_summary.get(
                "split_fallback_near_nominal_panel_count"
            ),
            "validation_requirement_status": venn_abers_validation_summary.get(
                "validation_requirement_status"
            ),
            "negative_evidence_requirement_status": venn_abers_validation_summary.get(
                "negative_evidence_requirement_status"
            ),
            "mean_venn_abers_coverage_by_panel": venn_abers_validation_summary.get(
                "mean_venn_abers_coverage_by_panel",
                {},
            ),
        },
        "venn_abers_grid_ivapd_validation_protocol": {
            "overall_status": venn_abers_grid_ivapd_summary.get("overall_status"),
            "failed_check_count": venn_abers_grid_ivapd_summary.get(
                "failed_check_count"
            ),
            "can_support_validated_venn_abers_regression": venn_abers_grid_ivapd_summary.get(
                "can_support_validated_venn_abers_regression"
            ),
            "can_support_exact_grid_venn_abers_validation": venn_abers_grid_ivapd_summary.get(
                "can_support_exact_grid_venn_abers_validation"
            ),
            "can_support_ivapd_interval_cp_validation": venn_abers_grid_ivapd_summary.get(
                "can_support_ivapd_interval_cp_validation"
            ),
            "grid_reference_validation_status": venn_abers_grid_ivapd_summary.get(
                "grid_reference_validation_status"
            ),
            "ivapd_interval_cp_status": venn_abers_grid_ivapd_summary.get(
                "ivapd_interval_cp_status"
            ),
            "validation_blocker_count": venn_abers_grid_ivapd_summary.get(
                "validation_blocker_count"
            ),
            "validation_blocker_ids": venn_abers_grid_ivapd_summary.get(
                "validation_blocker_ids",
                [],
            ),
            "total_grid_reference_rows_scored": venn_abers_grid_ivapd_summary.get(
                "total_grid_reference_rows_scored"
            ),
            "source_grid_reference_rows_scored": venn_abers_grid_ivapd_summary.get(
                "source_grid_reference_rows_scored"
            ),
            "worker_grid_reference_rows_scored": venn_abers_grid_ivapd_summary.get(
                "worker_grid_reference_rows_scored"
            ),
            "worker_grid_reference_rows_failed": venn_abers_grid_ivapd_summary.get(
                "worker_grid_reference_rows_failed"
            ),
            "worker_grid_hit_upper_count": venn_abers_grid_ivapd_summary.get(
                "worker_grid_hit_upper_count"
            ),
            "worker_grid_hit_upper_rate": venn_abers_grid_ivapd_summary.get(
                "worker_grid_hit_upper_rate"
            ),
            "total_grid_reference_rows_available": venn_abers_grid_ivapd_summary.get(
                "total_grid_reference_rows_available"
            ),
            "grid_reference_scored_fraction": venn_abers_grid_ivapd_summary.get(
                "grid_reference_scored_fraction"
            ),
            "min_panel_grid_reference_coverage": venn_abers_grid_ivapd_summary.get(
                "min_panel_grid_reference_coverage"
            ),
            "max_panel_grid_reference_coverage": venn_abers_grid_ivapd_summary.get(
                "max_panel_grid_reference_coverage"
            ),
            "max_panel_grid_hit_upper_rate": venn_abers_grid_ivapd_summary.get(
                "max_panel_grid_hit_upper_rate"
            ),
            "total_ivapd_rows_scored": venn_abers_grid_ivapd_summary.get(
                "total_ivapd_rows_scored"
            ),
            "total_ivapd_rows_available": venn_abers_grid_ivapd_summary.get(
                "total_ivapd_rows_available"
            ),
            "ivapd_scored_fraction": venn_abers_grid_ivapd_summary.get(
                "ivapd_scored_fraction"
            ),
            "final_validation_requirement_status": venn_abers_grid_ivapd_summary.get(
                "final_validation_requirement_status"
            ),
        },
        "venn_abers_grid_expansion_plan": {
            "overall_status": venn_abers_grid_expansion_summary.get("overall_status"),
            "failed_check_count": venn_abers_grid_expansion_summary.get(
                "failed_check_count"
            ),
            "source_report_count": venn_abers_grid_expansion_summary.get(
                "source_report_count"
            ),
            "run_task_count": venn_abers_grid_expansion_summary.get("run_task_count"),
            "task_status_counts": venn_abers_grid_expansion_summary.get(
                "task_status_counts",
                {},
            ),
            "task_count_by_report": venn_abers_grid_expansion_summary.get(
                "task_count_by_report",
                {},
            ),
            "total_test_rows_available": venn_abers_grid_expansion_summary.get(
                "total_test_rows_available"
            ),
            "total_grid_rows_completed": venn_abers_grid_expansion_summary.get(
                "total_grid_rows_completed"
            ),
            "source_grid_rows_completed": venn_abers_grid_expansion_summary.get(
                "source_grid_rows_completed"
            ),
            "worker_grid_rows_completed": venn_abers_grid_expansion_summary.get(
                "worker_grid_rows_completed"
            ),
            "worker_grid_rows_failed": venn_abers_grid_expansion_summary.get(
                "worker_grid_rows_failed"
            ),
            "total_grid_rows_pending": venn_abers_grid_expansion_summary.get(
                "total_grid_rows_pending"
            ),
            "grid_completion_fraction": venn_abers_grid_expansion_summary.get(
                "grid_completion_fraction"
            ),
            "next_batch_total_rows": venn_abers_grid_expansion_summary.get(
                "next_batch_total_rows"
            ),
            "duplicate_next_batch_task_key_count": venn_abers_grid_expansion_summary.get(
                "duplicate_next_batch_task_key_count"
            ),
            "largest_pending_tasks": venn_abers_grid_expansion_summary.get(
                "largest_pending_tasks",
                [],
            ),
        },
        "venn_abers_grid_failure_mode_decomposition": {
            "overall_status": venn_abers_grid_failure_modes_summary.get(
                "overall_status"
            ),
            "failed_check_count": venn_abers_grid_failure_modes_summary.get(
                "failed_check_count"
            ),
            "claim_status": venn_abers_grid_failure_modes_summary.get("claim_status"),
            "can_support_validated_venn_abers_regression": venn_abers_grid_failure_modes_summary.get(
                "can_support_validated_venn_abers_regression"
            ),
            "validation_blocker_count": venn_abers_grid_failure_modes_summary.get(
                "validation_blocker_count"
            ),
            "validation_blocker_ids": venn_abers_grid_failure_modes_summary.get(
                "validation_blocker_ids",
                [],
            ),
            "coverage_failure_panel_count": venn_abers_grid_failure_modes_summary.get(
                "coverage_failure_panel_count"
            ),
            "coverage_failure_run_count": venn_abers_grid_failure_modes_summary.get(
                "coverage_failure_run_count"
            ),
            "coverage_failure_dataset_count": venn_abers_grid_failure_modes_summary.get(
                "coverage_failure_dataset_count"
            ),
            "upper_boundary_failure_panel_count": venn_abers_grid_failure_modes_summary.get(
                "upper_boundary_failure_panel_count"
            ),
            "upper_boundary_failure_run_count": venn_abers_grid_failure_modes_summary.get(
                "upper_boundary_failure_run_count"
            ),
            "upper_boundary_failure_dataset_count": venn_abers_grid_failure_modes_summary.get(
                "upper_boundary_failure_dataset_count"
            ),
            "total_grid_reference_rows_scored": venn_abers_grid_failure_modes_summary.get(
                "total_grid_reference_rows_scored"
            ),
            "total_grid_reference_rows_available": venn_abers_grid_failure_modes_summary.get(
                "total_grid_reference_rows_available"
            ),
            "min_run_grid_reference_coverage": venn_abers_grid_failure_modes_summary.get(
                "min_run_grid_reference_coverage"
            ),
            "max_run_grid_hit_upper_rate": venn_abers_grid_failure_modes_summary.get(
                "max_run_grid_hit_upper_rate"
            ),
            "dominant_coverage_deficit_run_id": venn_abers_grid_failure_modes_summary.get(
                "dominant_coverage_deficit_run_id"
            ),
            "dominant_upper_boundary_run_id": venn_abers_grid_failure_modes_summary.get(
                "dominant_upper_boundary_run_id"
            ),
        },
        "venn_abers_claim_gate_matrix": {
            "overall_status": venn_abers_claim_gate_matrix_summary.get(
                "overall_status"
            ),
            "failed_check_count": venn_abers_claim_gate_matrix_summary.get(
                "failed_check_count"
            ),
            "can_support_validated_venn_abers_regression": venn_abers_claim_gate_matrix_summary.get(
                "can_support_validated_venn_abers_regression"
            ),
            "positive_claim_requirement_count": venn_abers_claim_gate_matrix_summary.get(
                "positive_claim_requirement_count"
            ),
            "positive_claim_pass_count": venn_abers_claim_gate_matrix_summary.get(
                "positive_claim_pass_count"
            ),
            "positive_claim_blocked_count": venn_abers_claim_gate_matrix_summary.get(
                "positive_claim_blocked_count"
            ),
            "blocked_positive_requirement_ids": venn_abers_claim_gate_matrix_summary.get(
                "blocked_positive_requirement_ids",
                [],
            ),
            "total_grid_reference_rows_scored": venn_abers_claim_gate_matrix_summary.get(
                "total_grid_reference_rows_scored"
            ),
            "total_grid_reference_rows_available": venn_abers_claim_gate_matrix_summary.get(
                "total_grid_reference_rows_available"
            ),
            "min_panel_grid_reference_coverage": venn_abers_claim_gate_matrix_summary.get(
                "min_panel_grid_reference_coverage"
            ),
            "max_panel_grid_hit_upper_rate": venn_abers_claim_gate_matrix_summary.get(
                "max_panel_grid_hit_upper_rate"
            ),
            "ivapd_interval_cp_status": venn_abers_claim_gate_matrix_summary.get(
                "ivapd_interval_cp_status"
            ),
        },
        "venn_abers_grid_expansion_batch": {
            "completed_new_row_tasks": venn_abers_grid_expansion_batch_summary.get(
                "completed_new_row_tasks"
            ),
            "failed_new_row_tasks": venn_abers_grid_expansion_batch_summary.get(
                "failed_new_row_tasks"
            ),
            "planned_new_row_tasks": venn_abers_grid_expansion_batch_summary.get(
                "planned_new_row_tasks"
            ),
            "skipped_existing_completed_rows": venn_abers_grid_expansion_batch_summary.get(
                "skipped_existing_completed_rows"
            ),
            "after_completed_row_count": venn_abers_grid_expansion_batch_summary.get(
                "after_completed_row_count"
            ),
            "after_unique_completed_row_count": venn_abers_grid_expansion_batch_summary.get(
                "after_unique_completed_row_count"
            ),
            "after_failed_row_count": venn_abers_grid_expansion_batch_summary.get(
                "after_failed_row_count"
            ),
            "ledger_record_count": venn_abers_grid_expansion_batch_state.get(
                "ledger_record_count"
            ),
            "duplicate_completed_key_count": venn_abers_grid_expansion_batch_state.get(
                "duplicate_completed_key_count"
            ),
            "grid_hit_upper_completed_count": venn_abers_grid_expansion_batch_state.get(
                "grid_hit_upper_completed_count"
            ),
            "completed_by_report": venn_abers_grid_expansion_batch_state.get(
                "completed_by_report",
                {},
            ),
            "completed_by_dataset": venn_abers_grid_expansion_batch_state.get(
                "completed_by_dataset",
                {},
            ),
        },
        "method_literature_coverage": {
            "overall_status": method_literature_summary.get("overall_status"),
            "literature_requirement_count": method_literature_summary.get(
                "literature_requirement_count"
            ),
            "status_counts": method_literature_summary.get("status_counts", {}),
            "hard_failed_requirement_count": method_literature_summary.get(
                "hard_failed_requirement_count"
            ),
            "tracked_gap_count": method_literature_summary.get("tracked_gap_count"),
            "registry_method_count": method_literature_summary.get(
                "registry_method_count"
            ),
            "runner_dispatch_method_count": method_literature_summary.get(
                "runner_dispatch_method_count"
            ),
            "configured_cp_method_count": method_literature_summary.get(
                "configured_cp_method_count"
            ),
            "primary_source_url_count": method_literature_summary.get(
                "primary_source_url_count"
            ),
            "failed_check_count": method_literature_summary.get("failed_check_count"),
        },
        "selection_multiplicity_protocol": {
            "overall_status": selection_multiplicity_summary.get("overall_status"),
            "required_manifest_field_count": selection_multiplicity_summary.get(
                "required_manifest_field_count"
            ),
            "covered_manifest_field_count": selection_multiplicity_summary.get(
                "covered_manifest_field_count"
            ),
            "failed_check_count": selection_multiplicity_summary.get(
                "failed_check_count"
            ),
            "eligibility_filter_count": selection_multiplicity_summary.get(
                "eligibility_filter_count"
            ),
            "ranking_scope_count": selection_multiplicity_summary.get(
                "ranking_scope_count"
            ),
            "selection_record_count": selection_multiplicity_summary.get(
                "selection_record_count"
            ),
            "linked_indexed_bundle_count": selection_multiplicity_summary.get(
                "linked_indexed_bundle_count"
            ),
            "unlinked_indexed_bundle_count": selection_multiplicity_summary.get(
                "unlinked_indexed_bundle_count"
            ),
            "completed_ledger_rows_scanned": selection_multiplicity_summary.get(
                "completed_ledger_rows_scanned"
            ),
            "can_support_final_method_selection": selection_multiplicity_summary.get(
                "can_support_final_method_selection"
            ),
            "final_selection_claim_status": selection_multiplicity_summary.get(
                "final_selection_claim_status"
            ),
        },
        "bounded_support_protocol": {
            "overall_status": bounded_support_summary.get("overall_status"),
            "failed_check_count": bounded_support_summary.get("failed_check_count"),
            "target_domain_class_count": bounded_support_summary.get(
                "target_domain_class_count"
            ),
            "interval_handling_policy_count": bounded_support_summary.get(
                "interval_handling_policy_count"
            ),
            "required_evidence_count": bounded_support_summary.get(
                "required_evidence_count"
            ),
            "bounded_support_policy_field_present": bounded_support_summary.get(
                "bounded_support_policy_field_present"
            ),
            "can_support_bounded_support_validity": bounded_support_summary.get(
                "can_support_bounded_support_validity"
            ),
            "publication_can_support_bounded_support_validity": bounded_support_summary.get(
                "publication_can_support_bounded_support_validity"
            ),
            "endpoint_bounded_support_gate_status": bounded_support_summary.get(
                "endpoint_bounded_support_gate_status"
            ),
            "final_selection_claim_status": bounded_support_summary.get(
                "final_selection_claim_status"
            ),
            "manuscript_endpoint_result_count": bounded_support_summary.get(
                "manuscript_endpoint_result_count"
            ),
            "manuscript_endpoint_caveat_count": bounded_support_summary.get(
                "manuscript_endpoint_caveat_count"
            ),
            "kg_endpoint_result_count": bounded_support_summary.get(
                "kg_endpoint_result_count"
            ),
            "kg_endpoint_caveat_count": bounded_support_summary.get(
                "kg_endpoint_caveat_count"
            ),
        },
        "target_domain_provenance": {
            "overall_status": target_domain_provenance_summary.get("overall_status"),
            "failed_check_count": target_domain_provenance_summary.get(
                "failed_check_count"
            ),
            "row_count": target_domain_provenance_summary.get("row_count"),
            "source_artifact_complete_count": target_domain_provenance_summary.get(
                "source_artifact_complete_count"
            ),
            "external_source_row_count": target_domain_provenance_summary.get(
                "external_source_row_count"
            ),
            "bounded_ordinal_row_count": target_domain_provenance_summary.get(
                "bounded_ordinal_row_count"
            ),
        },
        "external_source_discovery_watchlist": {
            "overall_status": external_source_discovery_summary.get("overall_status"),
            "source_family_count": external_source_discovery_summary.get(
                "source_family_count"
            ),
            "primary_source_family_count": external_source_discovery_summary.get(
                "primary_source_family_count"
            ),
            "secondary_source_family_count": external_source_discovery_summary.get(
                "secondary_source_family_count"
            ),
            "implemented_or_active_family_count": external_source_discovery_summary.get(
                "implemented_or_active_family_count"
            ),
            "pending_primary_family_count": external_source_discovery_summary.get(
                "pending_primary_family_count"
            ),
            "local_audited_family_count": external_source_discovery_summary.get(
                "local_audited_family_count"
            ),
            "local_reported_family_count": external_source_discovery_summary.get(
                "local_reported_family_count"
            ),
            "official_url_count": external_source_discovery_summary.get(
                "official_url_count"
            ),
            "openml_discovery_rows": external_source_discovery_summary.get(
                "openml_discovery_rows"
            ),
            "openml_ranked_rows": external_source_discovery_summary.get(
                "openml_ranked_rows"
            ),
            "dataset_candidate_rows": external_source_discovery_summary.get(
                "dataset_candidate_rows"
            ),
            "failed_check_count": external_source_discovery_summary.get(
                "failed_check_count"
            ),
        },
        "bounded_support_posthandling_validation": {
            "overall_status": bounded_support_posthandling_summary.get(
                "overall_status"
            ),
            "available_bundle_count": bounded_support_posthandling_summary.get(
                "available_bundle_count"
            ),
            "selected_bundle_count": bounded_support_posthandling_summary.get(
                "selected_bundle_count"
            ),
            "validated_bundle_count": bounded_support_posthandling_summary.get(
                "validated_bundle_count"
            ),
            "unvalidated_bundle_count": bounded_support_posthandling_summary.get(
                "unvalidated_bundle_count"
            ),
            "reconstructed_runs": bounded_support_posthandling_summary.get(
                "reconstructed_runs"
            ),
            "completed_ledger_rows": bounded_support_posthandling_summary.get(
                "completed_ledger_rows"
            ),
            "filtered_completed_ledger_rows": bounded_support_posthandling_summary.get(
                "filtered_completed_ledger_rows"
            ),
            "total_completed_ledger_rows_in_selected_bundles": bounded_support_posthandling_summary.get(
                "total_completed_ledger_rows_in_selected_bundles"
            ),
            "reconstruction_failures": bounded_support_posthandling_summary.get(
                "reconstruction_failures"
            ),
            "state_resumed_records": bounded_support_posthandling_summary.get(
                "state_resumed_records"
            ),
            "state_written_records": bounded_support_posthandling_summary.get(
                "state_written_records"
            ),
            "clip_policy_support_clean_bundle_count": bounded_support_posthandling_summary.get(
                "clip_policy_support_clean_bundle_count"
            ),
            "can_support_all_current_bounded_support_claims": bounded_support_posthandling_summary.get(
                "can_support_all_current_bounded_support_claims"
            ),
        },
        "bounded_support_dataset_audit": {
            "overall_status": bounded_support_dataset_summary.get("overall_status"),
            "failed_check_count": bounded_support_dataset_summary.get(
                "failed_check_count"
            ),
            "bundle_count": bounded_support_dataset_summary.get("bundle_count"),
            "unique_dataset_count": bounded_support_dataset_summary.get(
                "unique_dataset_count"
            ),
            "endpoint_audited_bundle_count": bounded_support_dataset_summary.get(
                "endpoint_audited_bundle_count"
            ),
            "bounded_support_ready_bundle_count": bounded_support_dataset_summary.get(
                "bounded_support_ready_bundle_count"
            ),
            "endpoint_support_clean_bundle_count": bounded_support_dataset_summary.get(
                "endpoint_support_clean_bundle_count"
            ),
            "endpoint_support_not_applicable_bundle_count": bounded_support_dataset_summary.get(
                "endpoint_support_not_applicable_bundle_count"
            ),
            "endpoint_support_blocked_or_incomplete_bundle_count": bounded_support_dataset_summary.get(
                "endpoint_support_blocked_or_incomplete_bundle_count"
            ),
            "endpoint_support_status_counts": bounded_support_dataset_summary.get(
                "endpoint_support_status_counts", {}
            ),
            "posthandling_support_status_counts": bounded_support_dataset_summary.get(
                "posthandling_support_status_counts", {}
            ),
            "target_domain_class_counts": bounded_support_dataset_summary.get(
                "target_domain_class_counts", {}
            ),
            "blocker_counts": bounded_support_dataset_summary.get("blocker_counts", {}),
            "natural_domain_excursion_bundle_count": bounded_support_dataset_summary.get(
                "natural_domain_excursion_bundle_count"
            ),
            "natural_domain_excursion_unknown_count_bundle_count": bounded_support_dataset_summary.get(
                "natural_domain_excursion_unknown_count_bundle_count"
            ),
            "observed_range_excursion_bundle_count": bounded_support_dataset_summary.get(
                "observed_range_excursion_bundle_count"
            ),
            "target_domain_provenance_status": bounded_support_dataset_summary.get(
                "target_domain_provenance_status"
            ),
            "can_support_bounded_support_validity": bounded_support_dataset_summary.get(
                "can_support_bounded_support_validity"
            ),
            "endpoint_bounded_support_gate_status": bounded_support_dataset_summary.get(
                "endpoint_bounded_support_gate_status"
            ),
        },
        "bounded_support_endpoint_closure_audit": {
            "overall_status": bounded_support_endpoint_closure_summary.get(
                "overall_status"
            ),
            "action_id": bounded_support_endpoint_closure_summary.get("action_id"),
            "action_status": bounded_support_endpoint_closure_summary.get(
                "action_status"
            ),
            "failed_check_count": bounded_support_endpoint_closure_summary.get(
                "failed_check_count"
            ),
            "bundle_count": bounded_support_endpoint_closure_summary.get(
                "bundle_count"
            ),
            "dataset_count": bounded_support_endpoint_closure_summary.get(
                "dataset_count"
            ),
            "closed_policy_bundle_count": (
                bounded_support_endpoint_closure_summary.get(
                    "closed_policy_bundle_count"
                )
            ),
            "open_endpoint_count_backfill_bundle_count": (
                bounded_support_endpoint_closure_summary.get(
                    "open_endpoint_count_backfill_bundle_count"
                )
            ),
            "raw_endpoint_excursion_bundle_count": (
                bounded_support_endpoint_closure_summary.get(
                    "raw_endpoint_excursion_bundle_count"
                )
            ),
            "endpoint_clean_or_not_applicable_bundle_count": (
                bounded_support_endpoint_closure_summary.get(
                    "endpoint_clean_or_not_applicable_bundle_count"
                )
            ),
            "global_no_claim_bundle_count": (
                bounded_support_endpoint_closure_summary.get(
                    "global_no_claim_bundle_count"
                )
            ),
            "bounded_support_validity_claim_ready_bundle_count": (
                bounded_support_endpoint_closure_summary.get(
                    "bounded_support_validity_claim_ready_bundle_count"
                )
            ),
            "current_manuscript_bounded_support_validity_claim_ready": (
                bounded_support_endpoint_closure_summary.get(
                    "current_manuscript_bounded_support_validity_claim_ready"
                )
            ),
        },
        "bounded_support_positive_validation_protocol": {
            "overall_status": bounded_support_positive_validation_summary.get(
                "overall_status"
            ),
            "action_id": bounded_support_positive_validation_summary.get("action_id"),
            "action_status": bounded_support_positive_validation_summary.get(
                "action_status"
            ),
            "failed_check_count": bounded_support_positive_validation_summary.get(
                "failed_check_count"
            ),
            "selected_bundle_count": bounded_support_positive_validation_summary.get(
                "selected_bundle_count"
            ),
            "posthandling_validated_bundle_count": bounded_support_positive_validation_summary.get(
                "posthandling_validated_bundle_count"
            ),
            "policy_metrics_available_bundle_count": bounded_support_positive_validation_summary.get(
                "policy_metrics_available_bundle_count"
            ),
            "interval_score_metrics_missing_bundle_count": bounded_support_positive_validation_summary.get(
                "interval_score_metrics_missing_bundle_count"
            ),
            "endpoint_blocked_or_incomplete_bundle_count": bounded_support_positive_validation_summary.get(
                "endpoint_blocked_or_incomplete_bundle_count"
            ),
            "positive_claim_ready_bundle_count": bounded_support_positive_validation_summary.get(
                "positive_claim_ready_bundle_count"
            ),
            "positive_acceptance_failed_count": bounded_support_positive_validation_summary.get(
                "positive_acceptance_failed_count"
            ),
            "can_support_bounded_support_validity": bounded_support_positive_validation_summary.get(
                "can_support_bounded_support_validity"
            ),
            "current_manuscript_bounded_support_validity_claim_ready": bounded_support_positive_validation_summary.get(
                "current_manuscript_bounded_support_validity_claim_ready"
            ),
        },
        "experiment_accounting": {
            "overall_status": experiment_accounting_summary.get("overall_status"),
            "failed_check_count": experiment_accounting_summary.get(
                "failed_check_count"
            ),
            "ledger_file_count": experiment_accounting_summary.get("ledger_file_count"),
            "raw_ledger_row_count": experiment_accounting_summary.get(
                "raw_ledger_row_count"
            ),
            "canonical_ledger_row_count": experiment_accounting_summary.get(
                "canonical_ledger_row_count"
            ),
            "raw_completed_row_count": experiment_accounting_summary.get(
                "raw_completed_row_count"
            ),
            "canonical_completed_row_count": experiment_accounting_summary.get(
                "canonical_completed_row_count"
            ),
            "canonical_failed_row_count": experiment_accounting_summary.get(
                "canonical_failed_row_count"
            ),
            "regular_canonical_completed_row_count": experiment_accounting_summary.get(
                "regular_canonical_completed_row_count"
            ),
            "cross_run_completed_rows": experiment_accounting_summary.get(
                "cross_run_completed_rows"
            ),
            "publication_completed_rows": experiment_accounting_summary.get(
                "publication_completed_rows"
            ),
            "selection_completed_rows_scanned": experiment_accounting_summary.get(
                "selection_completed_rows_scanned"
            ),
            "regular_completed_minus_cross_run_completed_rows": experiment_accounting_summary.get(
                "regular_completed_minus_cross_run_completed_rows"
            ),
            "invalidated_canonical_completed_row_count": experiment_accounting_summary.get(
                "invalidated_canonical_completed_row_count"
            ),
            "aborted_canonical_completed_row_count": experiment_accounting_summary.get(
                "aborted_canonical_completed_row_count"
            ),
            "bounded_support_selected_completed_rows": experiment_accounting_summary.get(
                "bounded_support_selected_completed_rows"
            ),
            "venn_grid_rows_completed": experiment_accounting_summary.get(
                "venn_grid_rows_completed"
            ),
            "venn_grid_rows_pending": experiment_accounting_summary.get(
                "venn_grid_rows_pending"
            ),
            "venn_grid_worker_rows_completed": experiment_accounting_summary.get(
                "venn_grid_worker_rows_completed"
            ),
            "venn_grid_worker_rows_failed": experiment_accounting_summary.get(
                "venn_grid_worker_rows_failed"
            ),
        },
        "method_performance_synthesis": {
            "overall_status": method_performance_summary.get("overall_status"),
            "failed_check_count": method_performance_summary.get("failed_check_count"),
            "completed_ledger_rows": method_performance_summary.get(
                "completed_ledger_rows"
            ),
            "source_report_count": method_performance_summary.get(
                "source_report_count"
            ),
            "method_count": method_performance_summary.get("method_count"),
            "broad_support_method_count": method_performance_summary.get(
                "broad_support_method_count"
            ),
            "dataset_count": method_performance_summary.get("dataset_count"),
            "dataset_alpha_cell_count": method_performance_summary.get(
                "dataset_alpha_cell_count"
            ),
            "frontier_cell_count": method_performance_summary.get(
                "frontier_cell_count"
            ),
            "top_frontier_methods": method_performance_summary.get(
                "top_frontier_methods"
            ),
            "can_support_final_method_selection": method_performance_summary.get(
                "can_support_final_method_selection"
            ),
            "claim_status": method_performance_summary.get("claim_status"),
        },
        "method_selection_candidate_audit": {
            "overall_status": method_selection_candidate_summary.get("overall_status"),
            "failed_check_count": method_selection_candidate_summary.get(
                "failed_check_count"
            ),
            "source_completed_ledger_rows": method_selection_candidate_summary.get(
                "source_completed_ledger_rows"
            ),
            "source_dataset_alpha_cell_count": method_selection_candidate_summary.get(
                "source_dataset_alpha_cell_count"
            ),
            "source_method_count": method_selection_candidate_summary.get(
                "source_method_count"
            ),
            "shortlist_method_count": method_selection_candidate_summary.get(
                "shortlist_method_count"
            ),
            "primary_candidate_method": method_selection_candidate_summary.get(
                "primary_candidate_method"
            ),
            "paired_comparison_count": method_selection_candidate_summary.get(
                "paired_comparison_count"
            ),
            "minimum_shared_pairwise_cell_count": method_selection_candidate_summary.get(
                "minimum_shared_pairwise_cell_count"
            ),
            "excluded_method_count": method_selection_candidate_summary.get(
                "excluded_method_count"
            ),
            "venn_abers_excluded_count": method_selection_candidate_summary.get(
                "venn_abers_excluded_count"
            ),
            "can_support_final_method_selection": method_selection_candidate_summary.get(
                "can_support_final_method_selection"
            ),
            "claim_status": method_selection_candidate_summary.get("claim_status"),
            "selection_protocol_status": method_selection_candidate_summary.get(
                "selection_protocol_status"
            ),
            "final_selection_claim_status": method_selection_candidate_summary.get(
                "final_selection_claim_status"
            ),
            "venn_abers_validation_status": method_selection_candidate_summary.get(
                "venn_abers_validation_status"
            ),
        },
        "method_selection_robustness_audit": {
            "overall_status": method_selection_robustness_summary.get("overall_status"),
            "failed_check_count": method_selection_robustness_summary.get(
                "failed_check_count"
            ),
            "source_completed_ledger_rows": method_selection_robustness_summary.get(
                "source_completed_ledger_rows"
            ),
            "candidate_primary_method": method_selection_robustness_summary.get(
                "candidate_primary_method"
            ),
            "candidate_method_count": method_selection_robustness_summary.get(
                "candidate_method_count"
            ),
            "common_dataset_alpha_cell_count": method_selection_robustness_summary.get(
                "common_dataset_alpha_cell_count"
            ),
            "common_dataset_count": method_selection_robustness_summary.get(
                "common_dataset_count"
            ),
            "common_alpha_count": method_selection_robustness_summary.get(
                "common_alpha_count"
            ),
            "common_alpha_distribution": method_selection_robustness_summary.get(
                "common_alpha_distribution"
            ),
            "common_alpha_max_cell_share": method_selection_robustness_summary.get(
                "common_alpha_max_cell_share"
            ),
            "common_alpha_imbalance_status": method_selection_robustness_summary.get(
                "common_alpha_imbalance_status"
            ),
            "alpha_balanced_selected_method": method_selection_robustness_summary.get(
                "alpha_balanced_selected_method"
            ),
            "alpha_balanced_primary_retained": method_selection_robustness_summary.get(
                "alpha_balanced_primary_retained"
            ),
            "alpha_stratum_selection_counts": method_selection_robustness_summary.get(
                "alpha_stratum_selection_counts"
            ),
            "common_cell_selected_method": method_selection_robustness_summary.get(
                "common_cell_selected_method"
            ),
            "common_cell_primary_win_count": method_selection_robustness_summary.get(
                "common_cell_primary_win_count"
            ),
            "common_cell_winner_counts": method_selection_robustness_summary.get(
                "common_cell_winner_counts"
            ),
            "common_cell_winner_margin_to_runner_up": method_selection_robustness_summary.get(
                "common_cell_winner_margin_to_runner_up"
            ),
            "leave_one_dataset_count": method_selection_robustness_summary.get(
                "leave_one_dataset_count"
            ),
            "leave_one_dataset_primary_retention_rate": method_selection_robustness_summary.get(
                "leave_one_dataset_primary_retention_rate"
            ),
            "leave_one_alpha_count": method_selection_robustness_summary.get(
                "leave_one_alpha_count"
            ),
            "leave_one_alpha_primary_retention_rate": method_selection_robustness_summary.get(
                "leave_one_alpha_primary_retention_rate"
            ),
            "bootstrap_replicates": method_selection_robustness_summary.get(
                "bootstrap_replicates"
            ),
            "bootstrap_primary_selection_rate": method_selection_robustness_summary.get(
                "bootstrap_primary_selection_rate"
            ),
            "bootstrap_selection_counts": method_selection_robustness_summary.get(
                "bootstrap_selection_counts"
            ),
            "can_support_final_method_selection": method_selection_robustness_summary.get(
                "can_support_final_method_selection"
            ),
            "claim_status": method_selection_robustness_summary.get("claim_status"),
            "selection_protocol_status": method_selection_robustness_summary.get(
                "selection_protocol_status"
            ),
            "final_selection_claim_status": method_selection_robustness_summary.get(
                "final_selection_claim_status"
            ),
        },
        "method_selection_alpha_expansion_plan": {
            "overall_status": method_selection_alpha_expansion_summary.get(
                "overall_status"
            ),
            "failed_check_count": method_selection_alpha_expansion_summary.get(
                "failed_check_count"
            ),
            "source_completed_ledger_rows": method_selection_alpha_expansion_summary.get(
                "source_completed_ledger_rows"
            ),
            "candidate_method_count": method_selection_alpha_expansion_summary.get(
                "candidate_method_count"
            ),
            "dominant_alpha": method_selection_alpha_expansion_summary.get(
                "dominant_alpha"
            ),
            "target_alphas": method_selection_alpha_expansion_summary.get(
                "target_alphas"
            ),
            "current_common_alpha_distribution": method_selection_alpha_expansion_summary.get(
                "current_common_alpha_distribution"
            ),
            "current_common_alpha_max_cell_share": method_selection_alpha_expansion_summary.get(
                "current_common_alpha_max_cell_share"
            ),
            "current_common_alpha_imbalance_status": method_selection_alpha_expansion_summary.get(
                "current_common_alpha_imbalance_status"
            ),
            "additional_common_cells_needed_to_clear_threshold": method_selection_alpha_expansion_summary.get(
                "additional_common_cells_needed_to_clear_threshold"
            ),
            "target_common_alpha_distribution": method_selection_alpha_expansion_summary.get(
                "target_common_alpha_distribution"
            ),
            "task_pool_dataset_alpha_task_count": method_selection_alpha_expansion_summary.get(
                "task_pool_dataset_alpha_task_count"
            ),
            "task_pool_method_run_task_count": method_selection_alpha_expansion_summary.get(
                "task_pool_method_run_task_count"
            ),
            "task_status_counts": method_selection_alpha_expansion_summary.get(
                "task_status_counts",
                {},
            ),
            "next_batch_dataset_alpha_task_count": method_selection_alpha_expansion_summary.get(
                "next_batch_dataset_alpha_task_count"
            ),
            "next_batch_method_run_task_count": method_selection_alpha_expansion_summary.get(
                "next_batch_method_run_task_count"
            ),
            "next_batch_alpha_counts": method_selection_alpha_expansion_summary.get(
                "next_batch_alpha_counts",
                {},
            ),
            "planned_common_cell_gain": method_selection_alpha_expansion_summary.get(
                "planned_common_cell_gain"
            ),
            "projected_common_alpha_distribution_after_next_batch": method_selection_alpha_expansion_summary.get(
                "projected_common_alpha_distribution_after_next_batch"
            ),
            "projected_common_alpha_max_cell_share_after_next_batch": method_selection_alpha_expansion_summary.get(
                "projected_common_alpha_max_cell_share_after_next_batch"
            ),
            "projected_common_alpha_imbalance_status_after_next_batch": method_selection_alpha_expansion_summary.get(
                "projected_common_alpha_imbalance_status_after_next_batch"
            ),
            "can_support_final_method_selection": method_selection_alpha_expansion_summary.get(
                "can_support_final_method_selection"
            ),
            "claim_status": method_selection_alpha_expansion_summary.get(
                "claim_status"
            ),
            "final_selection_claim_status": method_selection_alpha_expansion_summary.get(
                "final_selection_claim_status"
            ),
        },
        "method_selection_post_selection_validation_batch": {
            "overall_status": method_selection_post_selection_validation_batch_summary.get(
                "overall_status"
            ),
            "failed_check_count": method_selection_post_selection_validation_batch_summary.get(
                "failed_check_count"
            ),
            "dataset_count": method_selection_post_selection_validation_batch_summary.get(
                "dataset_count"
            ),
            "generated_config_count": method_selection_post_selection_validation_batch_summary.get(
                "generated_config_count"
            ),
            "expected_atomic_run_count": method_selection_post_selection_validation_batch_summary.get(
                "expected_atomic_run_count"
            ),
            "candidate_methods": method_selection_post_selection_validation_batch_summary.get(
                "candidate_methods"
            ),
            "target_alphas": method_selection_post_selection_validation_batch_summary.get(
                "target_alphas"
            ),
            "execution_status": method_selection_post_selection_validation_batch_summary.get(
                "execution_status"
            ),
            "can_support_final_method_selection": method_selection_post_selection_validation_batch_summary.get(
                "can_support_final_method_selection"
            ),
            "claim_status": method_selection_post_selection_validation_batch_summary.get(
                "claim_status"
            ),
        },
        "method_selection_post_selection_validation_results": {
            "overall_status": method_selection_post_selection_validation_results_summary.get(
                "overall_status"
            ),
            "failed_check_count": method_selection_post_selection_validation_results_summary.get(
                "failed_check_count"
            ),
            "dataset_count": method_selection_post_selection_validation_results_summary.get(
                "dataset_count"
            ),
            "completed_atomic_run_count": method_selection_post_selection_validation_results_summary.get(
                "completed_atomic_run_count"
            ),
            "expected_atomic_run_count": method_selection_post_selection_validation_results_summary.get(
                "expected_atomic_run_count"
            ),
            "common_dataset_alpha_cell_count": method_selection_post_selection_validation_results_summary.get(
                "common_dataset_alpha_cell_count"
            ),
            "expected_common_dataset_alpha_cell_count": method_selection_post_selection_validation_results_summary.get(
                "expected_common_dataset_alpha_cell_count"
            ),
            "diagnostic_winner_counts": method_selection_post_selection_validation_results_summary.get(
                "diagnostic_winner_counts",
                {},
            ),
            "feature_leakage_violation_count": method_selection_post_selection_validation_results_summary.get(
                "feature_leakage_violation_count"
            ),
            "width_pathology_row_count": method_selection_post_selection_validation_results_summary.get(
                "width_pathology_row_count"
            ),
            "can_support_final_method_selection": method_selection_post_selection_validation_results_summary.get(
                "can_support_final_method_selection"
            ),
            "claim_status": method_selection_post_selection_validation_results_summary.get(
                "claim_status"
            ),
        },
        "selection_multiplicity_evidence_record": {
            "overall_status": selection_multiplicity_evidence_summary.get(
                "overall_status"
            ),
            "failed_check_count": selection_multiplicity_evidence_summary.get(
                "failed_check_count"
            ),
            "validation_results_status": selection_multiplicity_evidence_summary.get(
                "validation_results_status"
            ),
            "validation_completed_atomic_rows": selection_multiplicity_evidence_summary.get(
                "validation_completed_atomic_rows"
            ),
            "validation_expected_atomic_rows": selection_multiplicity_evidence_summary.get(
                "validation_expected_atomic_rows"
            ),
            "diagnostic_primary_method": selection_multiplicity_evidence_summary.get(
                "diagnostic_primary_method"
            ),
            "diagnostic_winner_counts": selection_multiplicity_evidence_summary.get(
                "diagnostic_winner_counts",
                {},
            ),
            "feature_leakage_violation_count": selection_multiplicity_evidence_summary.get(
                "feature_leakage_violation_count"
            ),
            "can_support_final_method_selection": selection_multiplicity_evidence_summary.get(
                "can_support_final_method_selection"
            ),
            "claim_status": selection_multiplicity_evidence_summary.get("claim_status"),
            "final_selection_claim_status": selection_multiplicity_evidence_summary.get(
                "final_selection_claim_status"
            ),
        },
        "method_selection_alpha_expansion_execution": {
            "overall_status": method_selection_alpha_expansion_execution_summary.get(
                "overall_status"
            ),
            "failed_check_count": method_selection_alpha_expansion_execution_summary.get(
                "failed_check_count"
            ),
            "batch_overall_status": method_selection_alpha_expansion_execution_summary.get(
                "batch_overall_status"
            ),
            "batch_reported_execution_status": method_selection_alpha_expansion_execution_summary.get(
                "batch_reported_execution_status"
            ),
            "batch_reported_execution_status_is_historical": method_selection_alpha_expansion_execution_summary.get(
                "batch_reported_execution_status_is_historical"
            ),
            "batch_generation_label_stale_after_execution": method_selection_alpha_expansion_execution_summary.get(
                "batch_generation_label_stale_after_execution"
            ),
            "batch_generation_label_historical_only": method_selection_alpha_expansion_execution_summary.get(
                "batch_generation_label_historical_only"
            ),
            "batch_generation_label_reconciliation_status": method_selection_alpha_expansion_execution_summary.get(
                "batch_generation_label_reconciliation_status"
            ),
            "batch_generation_label_requires_action": method_selection_alpha_expansion_execution_summary.get(
                "batch_generation_label_requires_action"
            ),
            "execution_metadata_consistency_status": method_selection_alpha_expansion_execution_summary.get(
                "execution_metadata_consistency_status"
            ),
            "observed_execution_status": method_selection_alpha_expansion_execution_summary.get(
                "observed_execution_status"
            ),
            "active_execution_status": method_selection_alpha_expansion_execution_summary.get(
                "active_execution_status"
            ),
            "reconciled_execution_status": method_selection_alpha_expansion_execution_summary.get(
                "reconciled_execution_status"
            ),
            "generated_config_count": method_selection_alpha_expansion_execution_summary.get(
                "generated_config_count"
            ),
            "dataset_count": method_selection_alpha_expansion_execution_summary.get(
                "dataset_count"
            ),
            "completed_atomic_run_count": method_selection_alpha_expansion_execution_summary.get(
                "completed_atomic_run_count"
            ),
            "expected_atomic_run_count": method_selection_alpha_expansion_execution_summary.get(
                "expected_atomic_run_count"
            ),
            "plan_overall_status": method_selection_alpha_expansion_execution_summary.get(
                "plan_overall_status"
            ),
            "plan_additional_common_cells_needed_to_clear_threshold": method_selection_alpha_expansion_execution_summary.get(
                "plan_additional_common_cells_needed_to_clear_threshold"
            ),
            "post_selection_validation_status": method_selection_alpha_expansion_execution_summary.get(
                "post_selection_validation_status"
            ),
            "post_selection_completed_atomic_run_count": method_selection_alpha_expansion_execution_summary.get(
                "post_selection_completed_atomic_run_count"
            ),
            "post_selection_expected_atomic_run_count": method_selection_alpha_expansion_execution_summary.get(
                "post_selection_expected_atomic_run_count"
            ),
            "can_support_final_method_selection": method_selection_alpha_expansion_execution_summary.get(
                "can_support_final_method_selection"
            ),
            "claim_status": method_selection_alpha_expansion_execution_summary.get(
                "claim_status"
            ),
            "final_selection_claim_status": method_selection_alpha_expansion_execution_summary.get(
                "final_selection_claim_status"
            ),
        },
        "method_selection_inferential_audit": {
            "overall_status": method_selection_inferential_summary.get(
                "overall_status"
            ),
            "failed_check_count": method_selection_inferential_summary.get(
                "failed_check_count"
            ),
            "primary_candidate_method": method_selection_inferential_summary.get(
                "primary_candidate_method"
            ),
            "candidate_methods": method_selection_inferential_summary.get(
                "candidate_methods"
            ),
            "candidate_method_count": method_selection_inferential_summary.get(
                "candidate_method_count"
            ),
            "candidate_pairwise_comparison_count": method_selection_inferential_summary.get(
                "candidate_pairwise_comparison_count"
            ),
            "candidate_min_shared_pairwise_cell_count": method_selection_inferential_summary.get(
                "candidate_min_shared_pairwise_cell_count"
            ),
            "robustness_common_cell_primary_win_rate": method_selection_inferential_summary.get(
                "robustness_common_cell_primary_win_rate"
            ),
            "robustness_common_cell_primary_win_rate_ci95": method_selection_inferential_summary.get(
                "robustness_common_cell_primary_win_rate_ci95"
            ),
            "bootstrap_primary_selection_rate": method_selection_inferential_summary.get(
                "bootstrap_primary_selection_rate"
            ),
            "bootstrap_primary_selection_rate_ci95": method_selection_inferential_summary.get(
                "bootstrap_primary_selection_rate_ci95"
            ),
            "post_selection_validation_primary_win_rate": method_selection_inferential_summary.get(
                "post_selection_validation_primary_win_rate"
            ),
            "post_selection_validation_primary_win_rate_ci95": method_selection_inferential_summary.get(
                "post_selection_validation_primary_win_rate_ci95"
            ),
            "main_result_candidate_primary_win_rate": method_selection_inferential_summary.get(
                "main_result_candidate_primary_win_rate"
            ),
            "main_result_candidate_primary_win_rate_ci95": method_selection_inferential_summary.get(
                "main_result_candidate_primary_win_rate_ci95"
            ),
            "can_support_final_method_selection": method_selection_inferential_summary.get(
                "can_support_final_method_selection"
            ),
            "claim_status": method_selection_inferential_summary.get("claim_status"),
            "final_selection_claim_status": method_selection_inferential_summary.get(
                "final_selection_claim_status"
            ),
        },
        "manuscript_readiness_map": {
            "overall_status": manuscript_readiness_summary.get("overall_status"),
            "blocked_gate_count": manuscript_readiness_summary.get(
                "blocked_gate_count"
            ),
            "gate_count": manuscript_readiness_summary.get("gate_count"),
            "main_surface_blocked_count": manuscript_readiness_summary.get(
                "main_surface_blocked_count"
            ),
            "claim_count": manuscript_readiness_summary.get("claim_count"),
            "manifested_bundle_count": manuscript_readiness_summary.get(
                "manifested_bundle_count"
            ),
            "final_selection_claim_status": manuscript_readiness_summary.get(
                "final_selection_claim_status"
            ),
        },
        "manuscript_bundle_eligibility_matrix": {
            "overall_status": manuscript_bundle_eligibility_summary.get(
                "overall_status"
            ),
            "bundle_count": manuscript_bundle_eligibility_summary.get("bundle_count"),
            "manifest_present_count": manuscript_bundle_eligibility_summary.get(
                "manifest_present_count"
            ),
            "claim_linked_bundle_count": manuscript_bundle_eligibility_summary.get(
                "claim_linked_bundle_count"
            ),
            "missing_manifest_count": manuscript_bundle_eligibility_summary.get(
                "missing_manifest_count"
            ),
            "unlinked_bundle_count": manuscript_bundle_eligibility_summary.get(
                "unlinked_bundle_count"
            ),
            "robustness_candidate_count": manuscript_bundle_eligibility_summary.get(
                "robustness_candidate_count"
            ),
            "caveated_robustness_candidate_count": manuscript_bundle_eligibility_summary.get(
                "caveated_robustness_candidate_count"
            ),
            "main_results_eligible_count": manuscript_bundle_eligibility_summary.get(
                "main_results_eligible_count"
            ),
            "final_claim_eligible_count": manuscript_bundle_eligibility_summary.get(
                "final_claim_eligible_count"
            ),
            "final_selection_claim_status": manuscript_bundle_eligibility_summary.get(
                "final_selection_claim_status"
            ),
        },
        "dataset_specific_final_gate_audit": {
            "overall_status": dataset_specific_final_gate_summary.get("overall_status"),
            "dataset_count": dataset_specific_final_gate_summary.get("dataset_count"),
            "bundle_count": dataset_specific_final_gate_summary.get("bundle_count"),
            "main_result_candidate_diagnostic_bundle_count": dataset_specific_final_gate_summary.get(
                "main_result_candidate_diagnostic_bundle_count"
            ),
            "main_result_ready_bundle_count": dataset_specific_final_gate_summary.get(
                "main_result_ready_bundle_count"
            ),
            "main_result_ready_dataset_count": dataset_specific_final_gate_summary.get(
                "main_result_ready_dataset_count"
            ),
            "blocking_reason_counts": dataset_specific_final_gate_summary.get(
                "blocking_reason_counts",
                {},
            ),
            "paper_readiness_status": dataset_specific_final_gate_summary.get(
                "paper_readiness_status"
            ),
            "paper_blocked_gate_count": dataset_specific_final_gate_summary.get(
                "paper_blocked_gate_count"
            ),
            "final_selection_claim_status": dataset_specific_final_gate_summary.get(
                "final_selection_claim_status"
            ),
        },
        "dataset_final_gate_post_selection_validation_bridge": {
            "overall_status": dataset_final_bridge_summary.get("overall_status"),
            "failed_check_count": dataset_final_bridge_summary.get(
                "failed_check_count"
            ),
            "dataset_count": dataset_final_bridge_summary.get("dataset_count"),
            "generated_config_count": dataset_final_bridge_summary.get(
                "generated_config_count"
            ),
            "expected_atomic_run_count": dataset_final_bridge_summary.get(
                "expected_atomic_run_count"
            ),
            "bridge_results_available": dataset_final_bridge_summary.get(
                "bridge_results_available"
            ),
            "bridge_results_completed_atomic_run_count": dataset_final_bridge_summary.get(
                "bridge_results_completed_atomic_run_count"
            ),
            "bridge_results_expected_atomic_run_count": dataset_final_bridge_summary.get(
                "bridge_results_expected_atomic_run_count"
            ),
            "bridge_results_feature_leakage_violation_count": dataset_final_bridge_summary.get(
                "bridge_results_feature_leakage_violation_count"
            ),
            "execution_status": dataset_final_bridge_summary.get("execution_status"),
            "execution_reconciliation_requires_action": dataset_final_bridge_summary.get(
                "execution_reconciliation_requires_action"
            ),
            "can_support_final_method_selection": dataset_final_bridge_summary.get(
                "can_support_final_method_selection"
            ),
            "claim_status": dataset_final_bridge_summary.get("claim_status"),
        },
        "dataset_final_gate_post_selection_validation_bridge_results": {
            "overall_status": dataset_final_bridge_results_summary.get(
                "overall_status"
            ),
            "failed_check_count": dataset_final_bridge_results_summary.get(
                "failed_check_count"
            ),
            "dataset_count": dataset_final_bridge_results_summary.get("dataset_count"),
            "completed_atomic_run_count": dataset_final_bridge_results_summary.get(
                "completed_atomic_run_count"
            ),
            "expected_atomic_run_count": dataset_final_bridge_results_summary.get(
                "expected_atomic_run_count"
            ),
            "common_dataset_alpha_cell_count": dataset_final_bridge_results_summary.get(
                "common_dataset_alpha_cell_count"
            ),
            "expected_common_dataset_alpha_cell_count": dataset_final_bridge_results_summary.get(
                "expected_common_dataset_alpha_cell_count"
            ),
            "diagnostic_winner_counts": dataset_final_bridge_results_summary.get(
                "diagnostic_winner_counts",
                {},
            ),
            "feature_leakage_violation_count": dataset_final_bridge_results_summary.get(
                "feature_leakage_violation_count"
            ),
            "can_support_final_method_selection": dataset_final_bridge_results_summary.get(
                "can_support_final_method_selection"
            ),
            "claim_status": dataset_final_bridge_results_summary.get("claim_status"),
        },
        "main_result_candidate_bundle_plan": {
            "overall_status": main_result_candidate_plan_summary.get("overall_status"),
            "failed_check_count": main_result_candidate_plan_summary.get(
                "failed_check_count"
            ),
            "candidate_dataset_count": main_result_candidate_plan_summary.get(
                "candidate_dataset_count"
            ),
            "generated_config_count": main_result_candidate_plan_summary.get(
                "generated_config_count"
            ),
            "expected_atomic_run_count": main_result_candidate_plan_summary.get(
                "expected_atomic_run_count"
            ),
            "diagnostic_primary_method": main_result_candidate_plan_summary.get(
                "diagnostic_primary_method"
            ),
            "candidate_primary_consistent_dataset_count": main_result_candidate_plan_summary.get(
                "candidate_primary_consistent_dataset_count"
            ),
            "ambiguous_challenger_control_dataset_count": main_result_candidate_plan_summary.get(
                "ambiguous_challenger_control_dataset_count"
            ),
            "source_validation_combined_completed_atomic_rows": main_result_candidate_plan_summary.get(
                "source_validation_combined_completed_atomic_rows"
            ),
            "source_validation_combined_failed_check_count": main_result_candidate_plan_summary.get(
                "source_validation_combined_failed_check_count"
            ),
            "source_validation_combined_feature_leakage_violation_count": main_result_candidate_plan_summary.get(
                "source_validation_combined_feature_leakage_violation_count"
            ),
            "can_support_main_result_promotion": main_result_candidate_plan_summary.get(
                "can_support_main_result_promotion"
            ),
        },
        "main_result_candidate_bundle_results": {
            "overall_status": main_result_candidate_results_summary.get(
                "overall_status"
            ),
            "failed_check_count": main_result_candidate_results_summary.get(
                "failed_check_count"
            ),
            "completed_atomic_run_count": main_result_candidate_results_summary.get(
                "completed_atomic_run_count"
            ),
            "expected_atomic_run_count": main_result_candidate_results_summary.get(
                "expected_atomic_run_count"
            ),
            "complete_matched_cell_count": main_result_candidate_results_summary.get(
                "complete_matched_cell_count"
            ),
            "diagnostic_winner_counts": main_result_candidate_results_summary.get(
                "diagnostic_winner_counts",
                {},
            ),
            "pathology_flagged_row_count": main_result_candidate_results_summary.get(
                "pathology_flagged_row_count"
            ),
            "missing_ledger_count": main_result_candidate_results_summary.get(
                "missing_ledger_count"
            ),
            "can_support_main_result_promotion": main_result_candidate_results_summary.get(
                "can_support_main_result_promotion"
            ),
        },
        "main_result_candidate_post_run_closure": {
            "overall_status": main_result_candidate_closure_summary.get(
                "overall_status"
            ),
            "candidate_dataset_count": main_result_candidate_closure_summary.get(
                "candidate_dataset_count"
            ),
            "completed_atomic_run_count": main_result_candidate_closure_summary.get(
                "completed_atomic_run_count"
            ),
            "expected_atomic_run_count": main_result_candidate_closure_summary.get(
                "expected_atomic_run_count"
            ),
            "total_blocker_count": main_result_candidate_closure_summary.get(
                "total_blocker_count"
            ),
            "dataset_blocked_count": main_result_candidate_closure_summary.get(
                "dataset_blocked_count"
            ),
            "blocker_counts_by_artifact": main_result_candidate_closure_summary.get(
                "blocker_counts_by_artifact",
                {},
            ),
            "can_support_main_result_promotion": main_result_candidate_closure_summary.get(
                "can_support_main_result_promotion"
            ),
        },
        "dataset_final_gate_remediation_plan": {
            "overall_status": dataset_final_remediation_summary.get("overall_status"),
            "dataset_count": dataset_final_remediation_summary.get("dataset_count"),
            "ready_dataset_count": dataset_final_remediation_summary.get(
                "ready_dataset_count"
            ),
            "executable_action_count": dataset_final_remediation_summary.get(
                "executable_action_count"
            ),
            "action_counts": dataset_final_remediation_summary.get(
                "action_counts",
                {},
            ),
            "action_scope_counts": dataset_final_remediation_summary.get(
                "action_scope_counts",
                {},
            ),
            "local_dataset_remediation_action_count": dataset_final_remediation_summary.get(
                "local_dataset_remediation_action_count"
            ),
            "global_gate_dependency_action_count": dataset_final_remediation_summary.get(
                "global_gate_dependency_action_count"
            ),
            "post_closure_refresh_action_count": dataset_final_remediation_summary.get(
                "post_closure_refresh_action_count"
            ),
            "dataset_with_no_remaining_execution_gap_count": dataset_final_remediation_summary.get(
                "dataset_with_no_remaining_execution_gap_count"
            ),
            "dataset_blocked_only_by_global_gate_dependencies_count": dataset_final_remediation_summary.get(
                "dataset_blocked_only_by_global_gate_dependencies_count"
            ),
            "readiness_status_counts": dataset_final_remediation_summary.get(
                "readiness_status_counts",
                {},
            ),
            "blocked_gate_ids": dataset_final_remediation_summary.get(
                "blocked_gate_ids",
                [],
            ),
        },
        "duplicate_content_quarantine": {
            "overall_status": duplicate_content_quarantine_summary.get(
                "overall_status"
            ),
            "failed_check_count": duplicate_content_quarantine_summary.get(
                "failed_check_count"
            ),
            "duplicate_action_count": duplicate_content_quarantine_summary.get(
                "duplicate_action_count"
            ),
            "manuscript_candidate_action_count": duplicate_content_quarantine_summary.get(
                "manuscript_candidate_action_count"
            ),
            "non_manuscript_action_count": duplicate_content_quarantine_summary.get(
                "non_manuscript_action_count"
            ),
            "quarantined_action_count": duplicate_content_quarantine_summary.get(
                "quarantined_action_count"
            ),
            "unquarantined_action_count": duplicate_content_quarantine_summary.get(
                "unquarantined_action_count"
            ),
            "main_results_eligible_action_count": duplicate_content_quarantine_summary.get(
                "main_results_eligible_action_count"
            ),
            "caveat_label_missing_action_count": duplicate_content_quarantine_summary.get(
                "caveat_label_missing_action_count"
            ),
            "linked_final_claim_action_count": duplicate_content_quarantine_summary.get(
                "linked_final_claim_action_count"
            ),
            "quarantine_status_counts": duplicate_content_quarantine_summary.get(
                "quarantine_status_counts",
                {},
            ),
        },
        "venn_abers_negative_evidence_disposition": {
            "overall_status": venn_abers_negative_disposition_summary.get(
                "overall_status"
            ),
            "failed_check_count": venn_abers_negative_disposition_summary.get(
                "failed_check_count"
            ),
            "negative_claim_present": venn_abers_negative_disposition_summary.get(
                "negative_claim_present"
            ),
            "can_support_validated_venn_abers_regression": (
                venn_abers_negative_disposition_summary.get(
                    "can_support_validated_venn_abers_regression"
                )
            ),
            "undercoverage_run_count": venn_abers_negative_disposition_summary.get(
                "undercoverage_run_count"
            ),
            "validation_blocker_count": venn_abers_negative_disposition_summary.get(
                "validation_blocker_count"
            ),
            "positive_claim_blocked_count": (
                venn_abers_negative_disposition_summary.get(
                    "positive_claim_blocked_count"
                )
            ),
            "shortlist_method_count": venn_abers_negative_disposition_summary.get(
                "shortlist_method_count"
            ),
            "shortlist_venn_abers_method_count": (
                venn_abers_negative_disposition_summary.get(
                    "shortlist_venn_abers_method_count"
                )
            ),
            "excluded_venn_abers_method_count": (
                venn_abers_negative_disposition_summary.get(
                    "excluded_venn_abers_method_count"
                )
            ),
            "excluded_with_validation_gate_count": (
                venn_abers_negative_disposition_summary.get(
                    "excluded_with_validation_gate_count"
                )
            ),
            "venn_bundle_row_count": venn_abers_negative_disposition_summary.get(
                "venn_bundle_row_count"
            ),
            "venn_bundle_main_eligible_count": (
                venn_abers_negative_disposition_summary.get(
                    "venn_bundle_main_eligible_count"
                )
            ),
            "venn_bundle_main_unblocked_count": (
                venn_abers_negative_disposition_summary.get(
                    "venn_bundle_main_unblocked_count"
                )
            ),
            "final_selection_venn_abers_gate_status": (
                venn_abers_negative_disposition_summary.get(
                    "final_selection_venn_abers_gate_status"
                )
            ),
        },
        "graph_artifact_readiness": {
            "overall_status": graph_artifact_summary.get("overall_status"),
            "graph_count": graph_artifact_summary.get("graph_count"),
            "failed_check_count": graph_artifact_summary.get("failed_check_count"),
            "total_node_count_estimate": graph_artifact_summary.get(
                "total_node_count_estimate"
            ),
            "total_edge_count_estimate": graph_artifact_summary.get(
                "total_edge_count_estimate"
            ),
            "all_required_tokens_present": graph_artifact_summary.get(
                "all_required_tokens_present"
            ),
            "all_kg_graph_nodes_traceable": graph_artifact_summary.get(
                "all_kg_graph_nodes_traceable"
            ),
        },
        "paper_gate_protocol_design_bundle": {
            "overall_status": paper_gate_protocol_design_summary.get(
                "overall_status"
            ),
            "protocol_design_count": paper_gate_protocol_design_summary.get(
                "protocol_design_count"
            ),
            "completed_protocol_design_action_count": (
                paper_gate_protocol_design_summary.get(
                    "completed_protocol_design_action_count"
                )
            ),
            "downstream_action_count": paper_gate_protocol_design_summary.get(
                "downstream_action_count"
            ),
            "claim_promoted_action_count": paper_gate_protocol_design_summary.get(
                "claim_promoted_action_count"
            ),
            "status_counts": paper_gate_protocol_design_summary.get(
                "status_counts", {}
            ),
            "downstream_action_ids": paper_gate_protocol_design_summary.get(
                "downstream_action_ids", []
            ),
        },
        "paper_gate_closure_execution_plan": {
            "overall_status": paper_gate_execution_plan_summary.get(
                "overall_status"
            ),
            "gate_count": paper_gate_execution_plan_summary.get("gate_count"),
            "blocked_gate_count": paper_gate_execution_plan_summary.get(
                "blocked_gate_count"
            ),
            "action_count": paper_gate_execution_plan_summary.get("action_count"),
            "ready_action_count": paper_gate_execution_plan_summary.get(
                "ready_action_count"
            ),
            "blocked_action_count": paper_gate_execution_plan_summary.get(
                "blocked_action_count"
            ),
            "ready_for_protocol_design_action_count": (
                paper_gate_execution_plan_summary.get(
                    "ready_for_protocol_design_action_count"
                )
            ),
            "ready_for_empirical_execution_action_count": (
                paper_gate_execution_plan_summary.get(
                    "ready_for_empirical_execution_action_count"
                )
            ),
            "protocol_design_complete_action_count": (
                paper_gate_execution_plan_summary.get(
                    "protocol_design_complete_action_count"
                )
            ),
            "empirical_execution_complete_action_count": (
                paper_gate_execution_plan_summary.get(
                    "empirical_execution_complete_action_count"
                )
            ),
            "endpoint_natural_domain_audit_complete_action_count": (
                paper_gate_execution_plan_summary.get(
                    "endpoint_natural_domain_audit_complete_action_count"
                )
            ),
            "current_manuscript_bounded_support_validity_claim_ready": (
                paper_gate_execution_plan_summary.get(
                    "current_manuscript_bounded_support_validity_claim_ready"
                )
            ),
            "can_close_any_positive_gate_now": paper_gate_execution_plan_summary.get(
                "can_close_any_positive_gate_now"
            ),
            "action_status_counts": paper_gate_execution_plan_summary.get(
                "action_status_counts", {}
            ),
            "next_executable_action_ids": paper_gate_execution_plan_summary.get(
                "next_executable_action_ids", []
            ),
        },
        "kg_publication_quality": {
            "overall_status": kg_publication_summary.get("overall_status"),
            "node_count": kg_publication_summary.get("node_count"),
            "edge_count": kg_publication_summary.get("edge_count"),
            "hard_failed_check_count": kg_publication_summary.get(
                "hard_failed_check_count"
            ),
            "polish_caveat_count": kg_publication_summary.get("polish_caveat_count"),
            "specific_edge_provenance_coverage": kg_publication_summary.get(
                "specific_edge_provenance_coverage"
            ),
            "edge_selector_provenance_coverage": kg_publication_summary.get(
                "edge_selector_provenance_coverage"
            ),
            "claim_edge_selector_provenance_coverage": kg_publication_summary.get(
                "claim_edge_selector_provenance_coverage"
            ),
            "claim_edge_missing_selector_count": kg_publication_summary.get(
                "claim_edge_missing_selector_count"
            ),
            "claim_edge_count": kg_publication_summary.get("claim_edge_count"),
            "observation_node_ratio": kg_publication_summary.get(
                "observation_node_ratio"
            ),
            "paper_evidence_observation_node_ratio": kg_publication_summary.get(
                "paper_evidence_observation_node_ratio"
            ),
            "tracked_missing_source_count": kg_publication_summary.get(
                "tracked_missing_source_count"
            ),
            "relevant_untracked_source_count": kg_publication_summary.get(
                "relevant_untracked_source_count"
            ),
        },
        "scientific_review_finding_register": {
            "overall_status": scientific_review_summary.get("overall_status"),
            "finding_count": scientific_review_summary.get("finding_count"),
            "closed_count": scientific_review_summary.get("closed_count"),
            "tracked_caveat_count": scientific_review_summary.get(
                "tracked_caveat_count"
            ),
            "open_blocker_count": scientific_review_summary.get("open_blocker_count"),
            "hard_open_blocker_count": scientific_review_summary.get(
                "hard_open_blocker_count"
            ),
            "status_counts": scientific_review_summary.get("status_counts", {}),
        },
        "post_experiment_publication_activation_audit": {
            "overall_status": post_experiment_publication_activation_summary.get(
                "overall_status"
            ),
            "publication_phase_start_authorized": (
                post_experiment_publication_activation_summary.get(
                    "publication_phase_start_authorized"
                )
            ),
            "publication_preparation_authorized": (
                post_experiment_publication_activation_summary.get(
                    "publication_preparation_authorized"
                )
            ),
            "neutral_empirical_phase_complete": (
                post_experiment_publication_activation_summary.get(
                    "neutral_empirical_phase_complete"
                )
            ),
            "neutral_publication_route_allowed": (
                post_experiment_publication_activation_summary.get(
                    "neutral_publication_route_allowed"
                )
            ),
            "positive_claim_language_blocked": (
                post_experiment_publication_activation_summary.get(
                    "positive_claim_language_blocked"
                )
            ),
            "manuscript_drafting_authorized": (
                post_experiment_publication_activation_summary.get(
                    "manuscript_drafting_authorized"
                )
            ),
            "visual_table_audit_authorized": (
                post_experiment_publication_activation_summary.get(
                    "visual_table_audit_authorized"
                )
            ),
            "sterile_repository_creation_authorized": (
                post_experiment_publication_activation_summary.get(
                    "sterile_repository_creation_authorized"
                )
            ),
            "activation_check_count": (
                post_experiment_publication_activation_summary.get(
                    "activation_check_count"
                )
            ),
            "blocked_check_count": (
                post_experiment_publication_activation_summary.get(
                    "blocked_check_count"
                )
            ),
            "caveat_check_count": (
                post_experiment_publication_activation_summary.get(
                    "caveat_check_count"
                )
            ),
            "deferred_check_count": (
                post_experiment_publication_activation_summary.get(
                    "deferred_check_count"
                )
            ),
            "paper_blocked_gate_count": (
                post_experiment_publication_activation_summary.get(
                    "paper_blocked_gate_count"
                )
            ),
            "paper_blocked_gate_ids": (
                post_experiment_publication_activation_summary.get(
                    "paper_blocked_gate_ids"
                )
            ),
            "goal_can_mark_complete": (
                post_experiment_publication_activation_summary.get(
                    "goal_can_mark_complete"
                )
            ),
            "author_metadata_present": (
                post_experiment_publication_activation_summary.get(
                    "author_metadata_present"
                )
            ),
            "sterile_repository_plan_present": (
                post_experiment_publication_activation_summary.get(
                    "sterile_repository_plan_present"
                )
            ),
        },
        "publication_preparation_packets": {
            "overall_status": publication_preparation_packets_summary.get(
                "overall_status"
            ),
            "publication_preparation_authorized": (
                publication_preparation_packets_summary.get(
                    "publication_preparation_authorized"
                )
            ),
            "reviewer_packet_count": publication_preparation_packets_summary.get(
                "reviewer_packet_count"
            ),
            "required_reviewer_pass_count": publication_preparation_packets_summary.get(
                "required_reviewer_pass_count"
            ),
            "visual_table_candidate_family_count": (
                publication_preparation_packets_summary.get(
                    "visual_table_candidate_family_count"
                )
            ),
            "visual_table_quality_check_count": (
                publication_preparation_packets_summary.get(
                    "visual_table_quality_check_count"
                )
            ),
            "manuscript_drafting_authorized": (
                publication_preparation_packets_summary.get(
                    "manuscript_drafting_authorized"
                )
            ),
            "sterile_repository_creation_authorized": (
                publication_preparation_packets_summary.get(
                    "sterile_repository_creation_authorized"
                )
            ),
            "positive_claim_publication_ready": (
                publication_preparation_packets_summary.get(
                    "positive_claim_publication_ready"
                )
            ),
            "neutral_no_method_promotion_guard_active": (
                publication_preparation_packets_summary.get(
                    "neutral_no_method_promotion_guard_active"
                )
            ),
            "failed_check_count": publication_preparation_packets_summary.get(
                "failed_check_count"
            ),
        },
        "reviewer_design_brief": {
            "overall_status": reviewer_design_brief_summary.get("overall_status"),
            "phase_state": reviewer_design_brief_summary.get("phase_state"),
            "reviewer_count": reviewer_design_brief_summary.get("reviewer_count"),
            "required_reviewer_count": reviewer_design_brief_summary.get(
                "required_reviewer_count"
            ),
            "advice_record_count": reviewer_design_brief_summary.get(
                "advice_record_count"
            ),
            "accepted_advice_count": reviewer_design_brief_summary.get(
                "accepted_advice_count"
            ),
            "deferred_advice_count": reviewer_design_brief_summary.get(
                "deferred_advice_count"
            ),
            "covered_advice_topic_count": reviewer_design_brief_summary.get(
                "covered_advice_topic_count"
            ),
            "required_advice_topic_count": reviewer_design_brief_summary.get(
                "required_advice_topic_count"
            ),
            "content_matrix_row_count": reviewer_design_brief_summary.get(
                "content_matrix_row_count"
            ),
            "expected_visual_table_family_count": reviewer_design_brief_summary.get(
                "expected_visual_table_family_count"
            ),
            "publication_site_deployment_authorized": (
                reviewer_design_brief_summary.get(
                    "publication_site_deployment_authorized"
                )
            ),
            "neutral_no_method_promotion_guard_active": (
                reviewer_design_brief_summary.get(
                    "neutral_no_method_promotion_guard_active"
                )
            ),
            "manuscript_drafting_authorized": reviewer_design_brief_summary.get(
                "manuscript_drafting_authorized"
            ),
            "sterile_repository_creation_authorized": (
                reviewer_design_brief_summary.get(
                    "sterile_repository_creation_authorized"
                )
            ),
            "final_visual_table_retention_authorized": (
                reviewer_design_brief_summary.get(
                    "final_visual_table_retention_authorized"
                )
            ),
            "final_manuscript_prose_permission": reviewer_design_brief_summary.get(
                "final_manuscript_prose_permission"
            ),
            "final_retain_decision_authorized": reviewer_design_brief_summary.get(
                "final_retain_decision_authorized"
            ),
            "positive_claim_promotion_authorized": reviewer_design_brief_summary.get(
                "positive_claim_promotion_authorized"
            ),
            "failed_check_count": reviewer_design_brief_summary.get(
                "failed_check_count"
            ),
        },
        "publication_visual_audit_plan": {
            "overall_status": publication_visual_audit_plan_summary.get(
                "overall_status"
            ),
            "phase_state": publication_visual_audit_plan_summary.get("phase_state"),
            "candidate_artifact_count": publication_visual_audit_plan_summary.get(
                "candidate_artifact_count"
            ),
            "expected_candidate_artifact_count": (
                publication_visual_audit_plan_summary.get(
                    "expected_candidate_artifact_count"
                )
            ),
            "visual_table_quality_check_count": (
                publication_visual_audit_plan_summary.get(
                    "visual_table_quality_check_count"
                )
            ),
            "visual_table_scope_count": publication_visual_audit_plan_summary.get(
                "visual_table_scope_count"
            ),
            "visual_table_feedback_loop_step_count": (
                publication_visual_audit_plan_summary.get(
                    "visual_table_feedback_loop_step_count"
                )
            ),
            "visual_table_required_output_artifact_count": (
                publication_visual_audit_plan_summary.get(
                    "visual_table_required_output_artifact_count"
                )
            ),
            "triptych_component_count": publication_visual_audit_plan_summary.get(
                "triptych_component_count"
            ),
            "triptych_decision_status": publication_visual_audit_plan_summary.get(
                "triptych_decision_status"
            ),
            "kg_citable_component_authorized": (
                publication_visual_audit_plan_summary.get(
                    "kg_citable_component_authorized"
                )
            ),
            "publication_site_deployment_authorized": (
                publication_visual_audit_plan_summary.get(
                    "publication_site_deployment_authorized"
                )
            ),
            "visual_table_audit_plan_authorized": (
                publication_visual_audit_plan_summary.get(
                    "visual_table_audit_plan_authorized"
                )
            ),
            "visual_table_audit_execution_authorized": (
                publication_visual_audit_plan_summary.get(
                    "visual_table_audit_execution_authorized"
                )
            ),
            "final_visual_table_retention_authorized": (
                publication_visual_audit_plan_summary.get(
                    "final_visual_table_retention_authorized"
                )
            ),
            "final_triptych_release_authorized": (
                publication_visual_audit_plan_summary.get(
                    "final_triptych_release_authorized"
                )
            ),
            "final_manuscript_prose_permission": (
                publication_visual_audit_plan_summary.get(
                    "final_manuscript_prose_permission"
                )
            ),
            "positive_claim_promotion_authorized": (
                publication_visual_audit_plan_summary.get(
                    "positive_claim_promotion_authorized"
                )
            ),
            "neutral_no_method_promotion_guard_active": (
                publication_visual_audit_plan_summary.get(
                    "neutral_no_method_promotion_guard_active"
                )
            ),
            "failed_check_count": publication_visual_audit_plan_summary.get(
                "failed_check_count"
            ),
        },
        "visual_table_audit_report": {
            "overall_status": visual_table_audit_report_summary.get(
                "overall_status"
            ),
            "phase_state": visual_table_audit_report_summary.get("phase_state"),
            "inventory_row_count": visual_table_audit_report_summary.get(
                "inventory_row_count"
            ),
            "expected_candidate_artifact_count": (
                visual_table_audit_report_summary.get(
                    "expected_candidate_artifact_count"
                )
            ),
            "audit_row_count": visual_table_audit_report_summary.get(
                "audit_row_count"
            ),
            "pre_retention_audit_completed_count": (
                visual_table_audit_report_summary.get(
                    "pre_retention_audit_completed_count"
                )
            ),
            "source_traceable_candidate_count": (
                visual_table_audit_report_summary.get(
                    "source_traceable_candidate_count"
                )
            ),
            "pre_retention_decision_count": visual_table_audit_report_summary.get(
                "pre_retention_decision_count"
            ),
            "pre_retention_decision_counts": visual_table_audit_report_summary.get(
                "pre_retention_decision_counts"
            ),
            "actionable_feedback_count": visual_table_audit_report_summary.get(
                "actionable_feedback_count"
            ),
            "iteration_action_count": visual_table_audit_report_summary.get(
                "iteration_action_count"
            ),
            "rendered_artifact_count": visual_table_audit_report_summary.get(
                "rendered_artifact_count"
            ),
            "layout_check_deferred_count": visual_table_audit_report_summary.get(
                "layout_check_deferred_count"
            ),
            "final_retained_artifact_count": visual_table_audit_report_summary.get(
                "final_retained_artifact_count"
            ),
            "final_visual_table_retention_authorized": (
                visual_table_audit_report_summary.get(
                    "final_visual_table_retention_authorized"
                )
            ),
            "kg_citable_component_authorized": (
                visual_table_audit_report_summary.get(
                    "kg_citable_component_authorized"
                )
            ),
            "publication_site_deployment_authorized": (
                visual_table_audit_report_summary.get(
                    "publication_site_deployment_authorized"
                )
            ),
            "final_triptych_release_authorized": (
                visual_table_audit_report_summary.get(
                    "final_triptych_release_authorized"
                )
            ),
            "final_manuscript_prose_permission": (
                visual_table_audit_report_summary.get(
                    "final_manuscript_prose_permission"
                )
            ),
            "positive_claim_promotion_authorized": (
                visual_table_audit_report_summary.get(
                    "positive_claim_promotion_authorized"
                )
            ),
            "neutral_no_method_promotion_guard_active": (
                visual_table_audit_report_summary.get(
                    "neutral_no_method_promotion_guard_active"
                )
            ),
            "failed_check_count": visual_table_audit_report_summary.get(
                "failed_check_count"
            ),
        },
        "visual_table_render_candidate_audit": {
            "overall_status": visual_table_render_candidate_audit_summary.get(
                "overall_status"
            ),
            "phase_state": visual_table_render_candidate_audit_summary.get(
                "phase_state"
            ),
            "pre_retention_input_row_count": (
                visual_table_render_candidate_audit_summary.get(
                    "pre_retention_input_row_count"
                )
            ),
            "candidate_row_count": visual_table_render_candidate_audit_summary.get(
                "candidate_row_count"
            ),
            "rendered_draft_artifact_count": (
                visual_table_render_candidate_audit_summary.get(
                    "rendered_draft_artifact_count"
                )
            ),
            "primary_rendered_artifact_count": (
                visual_table_render_candidate_audit_summary.get(
                    "primary_rendered_artifact_count"
                )
            ),
            "supporting_artifact_count": (
                visual_table_render_candidate_audit_summary.get(
                    "supporting_artifact_count"
                )
            ),
            "layout_audit_row_count": visual_table_render_candidate_audit_summary.get(
                "layout_audit_row_count"
            ),
            "layout_pass_count": visual_table_render_candidate_audit_summary.get(
                "layout_pass_count"
            ),
            "layout_revise_count": visual_table_render_candidate_audit_summary.get(
                "layout_revise_count"
            ),
            "caption_pass_count": visual_table_render_candidate_audit_summary.get(
                "caption_pass_count"
            ),
            "source_traceability_pass_count": (
                visual_table_render_candidate_audit_summary.get(
                    "source_traceability_pass_count"
                )
            ),
            "svg_static_text_overlap_detected_count": (
                visual_table_render_candidate_audit_summary.get(
                    "svg_static_text_overlap_detected_count"
                )
            ),
            "final_retained_artifact_count": (
                visual_table_render_candidate_audit_summary.get(
                    "final_retained_artifact_count"
                )
            ),
            "final_visual_table_retention_authorized": (
                visual_table_render_candidate_audit_summary.get(
                    "final_visual_table_retention_authorized"
                )
            ),
            "kg_citable_component_authorized": (
                visual_table_render_candidate_audit_summary.get(
                    "kg_citable_component_authorized"
                )
            ),
            "publication_site_deployment_authorized": (
                visual_table_render_candidate_audit_summary.get(
                    "publication_site_deployment_authorized"
                )
            ),
            "final_triptych_release_authorized": (
                visual_table_render_candidate_audit_summary.get(
                    "final_triptych_release_authorized"
                )
            ),
            "final_manuscript_prose_permission": (
                visual_table_render_candidate_audit_summary.get(
                    "final_manuscript_prose_permission"
                )
            ),
            "positive_claim_promotion_authorized": (
                visual_table_render_candidate_audit_summary.get(
                    "positive_claim_promotion_authorized"
                )
            ),
            "neutral_no_method_promotion_guard_active": (
                visual_table_render_candidate_audit_summary.get(
                    "neutral_no_method_promotion_guard_active"
                )
            ),
            "failed_check_count": visual_table_render_candidate_audit_summary.get(
                "failed_check_count"
            ),
        },
        "publication_retention_readiness_audit": {
            "overall_status": publication_retention_readiness_audit_summary.get(
                "overall_status"
            ),
            "phase_state": publication_retention_readiness_audit_summary.get(
                "phase_state"
            ),
            "recommendation_row_count": (
                publication_retention_readiness_audit_summary.get(
                    "recommendation_row_count"
                )
            ),
            "render_candidate_count": (
                publication_retention_readiness_audit_summary.get(
                    "render_candidate_count"
                )
            ),
            "recommended_surface_counts": (
                publication_retention_readiness_audit_summary.get(
                    "recommended_surface_counts"
                )
            ),
            "main_article_candidate_count": (
                publication_retention_readiness_audit_summary.get(
                    "main_article_candidate_count"
                )
            ),
            "supplement_candidate_count": (
                publication_retention_readiness_audit_summary.get(
                    "supplement_candidate_count"
                )
            ),
            "kg_or_site_candidate_count": (
                publication_retention_readiness_audit_summary.get(
                    "kg_or_site_candidate_count"
                )
            ),
            "retention_recommendation_complete": (
                publication_retention_readiness_audit_summary.get(
                    "retention_recommendation_complete"
                )
            ),
            "reviewer_design_reconciled": (
                publication_retention_readiness_audit_summary.get(
                    "reviewer_design_reconciled"
                )
            ),
            "neutral_result_ledger_clean": (
                publication_retention_readiness_audit_summary.get(
                    "neutral_result_ledger_clean"
                )
            ),
            "neutral_language_unguarded_hit_count": (
                publication_retention_readiness_audit_summary.get(
                    "neutral_language_unguarded_hit_count"
                )
            ),
            "final_retained_artifact_count": (
                publication_retention_readiness_audit_summary.get(
                    "final_retained_artifact_count"
                )
            ),
            "final_visual_table_retention_authorized": (
                publication_retention_readiness_audit_summary.get(
                    "final_visual_table_retention_authorized"
                )
            ),
            "final_manuscript_prose_permission": (
                publication_retention_readiness_audit_summary.get(
                    "final_manuscript_prose_permission"
                )
            ),
            "publication_site_deployment_authorized": (
                publication_retention_readiness_audit_summary.get(
                    "publication_site_deployment_authorized"
                )
            ),
            "kg_citable_component_authorized": (
                publication_retention_readiness_audit_summary.get(
                    "kg_citable_component_authorized"
                )
            ),
            "positive_claim_promotion_authorized": (
                publication_retention_readiness_audit_summary.get(
                    "positive_claim_promotion_authorized"
                )
            ),
            "sterile_repository_creation_authorized": (
                publication_retention_readiness_audit_summary.get(
                    "sterile_repository_creation_authorized"
                )
            ),
            "failed_check_count": publication_retention_readiness_audit_summary.get(
                "failed_check_count"
            ),
        },
        "final_publication_visual_auditor_readiness": {
            "overall_status": (
                final_publication_visual_auditor_readiness_summary.get(
                    "overall_status"
                )
            ),
            "phase_state": final_publication_visual_auditor_readiness_summary.get(
                "phase_state"
            ),
            "final_publication_visual_auditor_status": (
                final_publication_visual_auditor_readiness_summary.get(
                    "final_publication_visual_auditor_status"
                )
            ),
            "feedback_loop_ready": (
                final_publication_visual_auditor_readiness_summary.get(
                    "feedback_loop_ready"
                )
            ),
            "feedback_row_count": (
                final_publication_visual_auditor_readiness_summary.get(
                    "feedback_row_count"
                )
            ),
            "feedback_ready_row_count": (
                final_publication_visual_auditor_readiness_summary.get(
                    "feedback_ready_row_count"
                )
            ),
            "feedback_blocked_row_count": (
                final_publication_visual_auditor_readiness_summary.get(
                    "feedback_blocked_row_count"
                )
            ),
            "feedback_item_count": (
                final_publication_visual_auditor_readiness_summary.get(
                    "feedback_item_count"
                )
            ),
            "recommended_surface_counts": (
                final_publication_visual_auditor_readiness_summary.get(
                    "recommended_surface_counts"
                )
            ),
            "missing_rendered_artifact_count": (
                final_publication_visual_auditor_readiness_summary.get(
                    "missing_rendered_artifact_count"
                )
            ),
            "authorization_violation_count": (
                final_publication_visual_auditor_readiness_summary.get(
                    "authorization_violation_count"
                )
            ),
            "final_retained_artifact_count": (
                final_publication_visual_auditor_readiness_summary.get(
                    "final_retained_artifact_count"
                )
            ),
            "final_visual_table_retention_authorized": (
                final_publication_visual_auditor_readiness_summary.get(
                    "final_visual_table_retention_authorized"
                )
            ),
            "final_manuscript_prose_permission": (
                final_publication_visual_auditor_readiness_summary.get(
                    "final_manuscript_prose_permission"
                )
            ),
            "publication_site_deployment_authorized": (
                final_publication_visual_auditor_readiness_summary.get(
                    "publication_site_deployment_authorized"
                )
            ),
            "kg_citable_component_authorized": (
                final_publication_visual_auditor_readiness_summary.get(
                    "kg_citable_component_authorized"
                )
            ),
            "positive_claim_promotion_authorized": (
                final_publication_visual_auditor_readiness_summary.get(
                    "positive_claim_promotion_authorized"
                )
            ),
            "failed_check_count": (
                final_publication_visual_auditor_readiness_summary.get(
                    "failed_check_count"
                )
            ),
        },
        "neutral_result_ledger": {
            "overall_status": neutral_result_ledger_summary.get("overall_status"),
            "row_count": neutral_result_ledger_summary.get("row_count"),
            "source_artifact_count": neutral_result_ledger_summary.get(
                "source_artifact_count"
            ),
            "missing_source_artifact_count": (
                neutral_result_ledger_summary.get("missing_source_artifact_count")
            ),
            "positive_claim_promotion_authorized_count": (
                neutral_result_ledger_summary.get(
                    "positive_claim_promotion_authorized_count"
                )
            ),
            "final_method_selection_authorized_count": (
                neutral_result_ledger_summary.get(
                    "final_method_selection_authorized_count"
                )
            ),
            "final_visual_table_retention_authorized_count": (
                neutral_result_ledger_summary.get(
                    "final_visual_table_retention_authorized_count"
                )
            ),
            "final_manuscript_prose_permission_count": (
                neutral_result_ledger_summary.get(
                    "final_manuscript_prose_permission_count"
                )
            ),
            "sterile_repository_creation_authorized_count": (
                neutral_result_ledger_summary.get(
                    "sterile_repository_creation_authorized_count"
                )
            ),
            "neutral_no_method_promotion_guard_active": (
                neutral_result_ledger_summary.get(
                    "neutral_no_method_promotion_guard_active"
                )
            ),
            "cqr_descriptive_candidate_recorded": (
                neutral_result_ledger_summary.get(
                    "cqr_descriptive_candidate_recorded"
                )
            ),
            "venn_abers_negative_result_recorded": (
                neutral_result_ledger_summary.get(
                    "venn_abers_negative_result_recorded"
                )
            ),
            "failed_check_count": neutral_result_ledger_summary.get(
                "failed_check_count"
            ),
        },
        "article_supplement_blueprint_alignment": {
            "overall_status": article_supplement_blueprint_alignment_summary.get(
                "overall_status"
            ),
            "phase_state": article_supplement_blueprint_alignment_summary.get(
                "phase_state"
            ),
            "alignment_row_count": article_supplement_blueprint_alignment_summary.get(
                "alignment_row_count"
            ),
            "surface_row_count": article_supplement_blueprint_alignment_summary.get(
                "surface_row_count"
            ),
            "direct_reviewer_advice_row_count": (
                article_supplement_blueprint_alignment_summary.get(
                    "direct_reviewer_advice_row_count"
                )
            ),
            "explicit_no_direct_advice_rationale_count": (
                article_supplement_blueprint_alignment_summary.get(
                    "explicit_no_direct_advice_rationale_count"
                )
            ),
            "reviewer_alignment_issue_count": (
                article_supplement_blueprint_alignment_summary.get(
                    "reviewer_alignment_issue_count"
                )
            ),
            "linked_neutral_result_issue_count": (
                article_supplement_blueprint_alignment_summary.get(
                    "linked_neutral_result_issue_count"
                )
            ),
            "source_traceable_row_count": (
                article_supplement_blueprint_alignment_summary.get(
                    "source_traceable_row_count"
                )
            ),
            "missing_source_artifact_count": (
                article_supplement_blueprint_alignment_summary.get(
                    "missing_source_artifact_count"
                )
            ),
            "recommended_surface_counts": (
                article_supplement_blueprint_alignment_summary.get(
                    "recommended_surface_counts"
                )
            ),
            "neutral_result_ledger_clean": (
                article_supplement_blueprint_alignment_summary.get(
                    "neutral_result_ledger_clean"
                )
            ),
            "neutral_language_unguarded_hit_count": (
                article_supplement_blueprint_alignment_summary.get(
                    "neutral_language_unguarded_hit_count"
                )
            ),
            "activation_pre_prose_only": (
                article_supplement_blueprint_alignment_summary.get(
                    "activation_pre_prose_only"
                )
            ),
            "venn_abers_negative_no_validated_claim": (
                article_supplement_blueprint_alignment_summary.get(
                    "venn_abers_negative_no_validated_claim"
                )
            ),
            "cqr_cvplus_reporting_role": (
                article_supplement_blueprint_alignment_summary.get(
                    "cqr_cvplus_reporting_role"
                )
            ),
            "final_retained_artifact_count": (
                article_supplement_blueprint_alignment_summary.get(
                    "final_retained_artifact_count"
                )
            ),
            "final_visual_table_retention_authorized": (
                article_supplement_blueprint_alignment_summary.get(
                    "final_visual_table_retention_authorized"
                )
            ),
            "final_manuscript_prose_permission": (
                article_supplement_blueprint_alignment_summary.get(
                    "final_manuscript_prose_permission"
                )
            ),
            "publication_site_deployment_authorized": (
                article_supplement_blueprint_alignment_summary.get(
                    "publication_site_deployment_authorized"
                )
            ),
            "kg_citable_component_authorized": (
                article_supplement_blueprint_alignment_summary.get(
                    "kg_citable_component_authorized"
                )
            ),
            "positive_claim_promotion_authorized": (
                article_supplement_blueprint_alignment_summary.get(
                    "positive_claim_promotion_authorized"
                )
            ),
            "sterile_repository_creation_authorized": (
                article_supplement_blueprint_alignment_summary.get(
                    "sterile_repository_creation_authorized"
                )
            ),
            "method_recommendation_authorized": (
                article_supplement_blueprint_alignment_summary.get(
                    "method_recommendation_authorized"
                )
            ),
            "scientific_no_method_promotion_guard_active": (
                article_supplement_blueprint_alignment_summary.get(
                    "scientific_no_method_promotion_guard_active"
                )
            ),
            "failed_check_count": article_supplement_blueprint_alignment_summary.get(
                "failed_check_count"
            ),
        },
        "publication_release_gap_register": {
            "overall_status": publication_release_gap_register_summary.get(
                "overall_status"
            ),
            "phase_state": publication_release_gap_register_summary.get(
                "phase_state"
            ),
            "deliverable_row_count": publication_release_gap_register_summary.get(
                "deliverable_row_count"
            ),
            "pre_prose_evidence_ready_row_count": (
                publication_release_gap_register_summary.get(
                    "pre_prose_evidence_ready_row_count"
                )
            ),
            "release_authorized_count": publication_release_gap_register_summary.get(
                "release_authorized_count"
            ),
            "blocked_release_row_count": publication_release_gap_register_summary.get(
                "blocked_release_row_count"
            ),
            "source_traceable_row_count": publication_release_gap_register_summary.get(
                "source_traceable_row_count"
            ),
            "missing_source_artifact_count": publication_release_gap_register_summary.get(
                "missing_source_artifact_count"
            ),
            "goal_can_mark_complete": publication_release_gap_register_summary.get(
                "goal_can_mark_complete"
            ),
            "noncomplete_requirement_count": publication_release_gap_register_summary.get(
                "noncomplete_requirement_count"
            ),
            "paper_blocked_gate_count": publication_release_gap_register_summary.get(
                "paper_blocked_gate_count"
            ),
            "positive_claim_ready_gate_count": (
                publication_release_gap_register_summary.get(
                    "positive_claim_ready_gate_count"
                )
            ),
            "final_manuscript_prose_permission": (
                publication_release_gap_register_summary.get(
                    "final_manuscript_prose_permission"
                )
            ),
            "publication_site_deployment_authorized": (
                publication_release_gap_register_summary.get(
                    "publication_site_deployment_authorized"
                )
            ),
            "kg_citable_component_authorized": (
                publication_release_gap_register_summary.get(
                    "kg_citable_component_authorized"
                )
            ),
            "sterile_repository_creation_authorized": (
                publication_release_gap_register_summary.get(
                    "sterile_repository_creation_authorized"
                )
            ),
            "method_recommendation_authorized": (
                publication_release_gap_register_summary.get(
                    "method_recommendation_authorized"
                )
            ),
            "positive_claim_promotion_authorized": (
                publication_release_gap_register_summary.get(
                    "positive_claim_promotion_authorized"
                )
            ),
            "working_repository_final_citable": (
                publication_release_gap_register_summary.get(
                    "working_repository_final_citable"
                )
            ),
            "sterile_repository_status": publication_release_gap_register_summary.get(
                "sterile_repository_status"
            ),
            "failed_check_count": publication_release_gap_register_summary.get(
                "failed_check_count"
            ),
        },
        "individual_experiment_report_blueprint": {
            "overall_status": individual_experiment_report_blueprint_summary.get(
                "overall_status"
            ),
            "phase_state": individual_experiment_report_blueprint_summary.get(
                "phase_state"
            ),
            "author_header": individual_experiment_report_blueprint_summary.get(
                "author_header"
            ),
            "author_email": individual_experiment_report_blueprint_summary.get(
                "author_email"
            ),
            "approved_author_header_present": (
                individual_experiment_report_blueprint_summary.get(
                    "approved_author_header_present"
                )
            ),
            "deliverable_registered": individual_experiment_report_blueprint_summary.get(
                "deliverable_registered"
            ),
            "deliverable_format": individual_experiment_report_blueprint_summary.get(
                "deliverable_format"
            ),
            "section_row_count": individual_experiment_report_blueprint_summary.get(
                "section_row_count"
            ),
            "source_traceable_row_count": (
                individual_experiment_report_blueprint_summary.get(
                    "source_traceable_row_count"
                )
            ),
            "missing_source_artifact_count": (
                individual_experiment_report_blueprint_summary.get(
                    "missing_source_artifact_count"
                )
            ),
            "linked_neutral_result_issue_count": (
                individual_experiment_report_blueprint_summary.get(
                    "linked_neutral_result_issue_count"
                )
            ),
            "final_report_prose_permission": (
                individual_experiment_report_blueprint_summary.get(
                    "final_report_prose_permission"
                )
            ),
            "latex_output_authorized": individual_experiment_report_blueprint_summary.get(
                "latex_output_authorized"
            ),
            "html_output_authorized": individual_experiment_report_blueprint_summary.get(
                "html_output_authorized"
            ),
            "markdown_output_authorized": (
                individual_experiment_report_blueprint_summary.get(
                    "markdown_output_authorized"
                )
            ),
            "release_authorized": individual_experiment_report_blueprint_summary.get(
                "release_authorized"
            ),
            "sterile_repository_creation_authorized": (
                individual_experiment_report_blueprint_summary.get(
                    "sterile_repository_creation_authorized"
                )
            ),
            "working_repository_final_citable": (
                individual_experiment_report_blueprint_summary.get(
                    "working_repository_final_citable"
                )
            ),
            "method_recommendation_authorized": (
                individual_experiment_report_blueprint_summary.get(
                    "method_recommendation_authorized"
                )
            ),
            "positive_claim_promotion_authorized": (
                individual_experiment_report_blueprint_summary.get(
                    "positive_claim_promotion_authorized"
                )
            ),
            "cqr_reporting_role": individual_experiment_report_blueprint_summary.get(
                "cqr_reporting_role"
            ),
            "venn_abers_reporting_role": (
                individual_experiment_report_blueprint_summary.get(
                    "venn_abers_reporting_role"
                )
            ),
            "scientific_no_method_promotion_guard_active": (
                individual_experiment_report_blueprint_summary.get(
                    "scientific_no_method_promotion_guard_active"
                )
            ),
            "failed_check_count": individual_experiment_report_blueprint_summary.get(
                "failed_check_count"
            ),
        },
        "claim_safe_result_extraction_matrix": {
            "overall_status": claim_safe_result_extraction_matrix_summary.get(
                "overall_status"
            ),
            "phase_state": claim_safe_result_extraction_matrix_summary.get(
                "phase_state"
            ),
            "surface_row_count": claim_safe_result_extraction_matrix_summary.get(
                "surface_row_count"
            ),
            "source_traceable_row_count": (
                claim_safe_result_extraction_matrix_summary.get(
                    "source_traceable_row_count"
                )
            ),
            "missing_source_artifact_count": (
                claim_safe_result_extraction_matrix_summary.get(
                    "missing_source_artifact_count"
                )
            ),
            "linked_neutral_result_issue_count": (
                claim_safe_result_extraction_matrix_summary.get(
                    "linked_neutral_result_issue_count"
                )
            ),
            "safe_pre_prose_extraction_candidate_count": (
                claim_safe_result_extraction_matrix_summary.get(
                    "safe_pre_prose_extraction_candidate_count"
                )
            ),
            "blocked_positive_surface_count": (
                claim_safe_result_extraction_matrix_summary.get(
                    "blocked_positive_surface_count"
                )
            ),
            "main_results_surface_status": (
                claim_safe_result_extraction_matrix_summary.get(
                    "main_results_surface_status"
                )
            ),
            "negative_results_surface_status": (
                claim_safe_result_extraction_matrix_summary.get(
                    "negative_results_surface_status"
                )
            ),
            "main_result_positive_claim_blocked": (
                claim_safe_result_extraction_matrix_summary.get(
                    "main_result_positive_claim_blocked"
                )
            ),
            "negative_result_reporting_ready": (
                claim_safe_result_extraction_matrix_summary.get(
                    "negative_result_reporting_ready"
                )
            ),
            "neutral_result_ledger_clean": (
                claim_safe_result_extraction_matrix_summary.get(
                    "neutral_result_ledger_clean"
                )
            ),
            "final_manuscript_prose_permission": (
                claim_safe_result_extraction_matrix_summary.get(
                    "final_manuscript_prose_permission"
                )
            ),
            "final_visual_table_retention_authorized": (
                claim_safe_result_extraction_matrix_summary.get(
                    "final_visual_table_retention_authorized"
                )
            ),
            "release_authorized": claim_safe_result_extraction_matrix_summary.get(
                "release_authorized"
            ),
            "sterile_repository_creation_authorized": (
                claim_safe_result_extraction_matrix_summary.get(
                    "sterile_repository_creation_authorized"
                )
            ),
            "working_repository_final_citable": (
                claim_safe_result_extraction_matrix_summary.get(
                    "working_repository_final_citable"
                )
            ),
            "method_recommendation_authorized": (
                claim_safe_result_extraction_matrix_summary.get(
                    "method_recommendation_authorized"
                )
            ),
            "positive_claim_promotion_authorized": (
                claim_safe_result_extraction_matrix_summary.get(
                    "positive_claim_promotion_authorized"
                )
            ),
            "scientific_no_method_promotion_guard_active": (
                claim_safe_result_extraction_matrix_summary.get(
                    "scientific_no_method_promotion_guard_active"
                )
            ),
            "failed_check_count": claim_safe_result_extraction_matrix_summary.get(
                "failed_check_count"
            ),
        },
        "manuscript_section_evidence_packet": {
            "overall_status": manuscript_section_evidence_packet_summary.get(
                "overall_status"
            ),
            "phase_state": manuscript_section_evidence_packet_summary.get(
                "phase_state"
            ),
            "section_packet_row_count": (
                manuscript_section_evidence_packet_summary.get(
                    "section_packet_row_count"
                )
            ),
            "source_traceable_row_count": (
                manuscript_section_evidence_packet_summary.get(
                    "source_traceable_row_count"
                )
            ),
            "missing_source_artifact_count": (
                manuscript_section_evidence_packet_summary.get(
                    "missing_source_artifact_count"
                )
            ),
            "claim_safe_surface_link_issue_count": (
                manuscript_section_evidence_packet_summary.get(
                    "claim_safe_surface_link_issue_count"
                )
            ),
            "linked_neutral_result_issue_count": (
                manuscript_section_evidence_packet_summary.get(
                    "linked_neutral_result_issue_count"
                )
            ),
            "safe_pre_prose_evidence_packet_count": (
                manuscript_section_evidence_packet_summary.get(
                    "safe_pre_prose_evidence_packet_count"
                )
            ),
            "blocked_positive_packet_count": (
                manuscript_section_evidence_packet_summary.get(
                    "blocked_positive_packet_count"
                )
            ),
            "main_results_packet_status": (
                manuscript_section_evidence_packet_summary.get(
                    "main_results_packet_status"
                )
            ),
            "negative_packet_status": (
                manuscript_section_evidence_packet_summary.get(
                    "negative_packet_status"
                )
            ),
            "main_results_packet_blocked": (
                manuscript_section_evidence_packet_summary.get(
                    "main_results_packet_blocked"
                )
            ),
            "negative_packet_ready": manuscript_section_evidence_packet_summary.get(
                "negative_packet_ready"
            ),
            "claim_safe_matrix_clean": (
                manuscript_section_evidence_packet_summary.get(
                    "claim_safe_matrix_clean"
                )
            ),
            "neutral_result_ledger_clean": (
                manuscript_section_evidence_packet_summary.get(
                    "neutral_result_ledger_clean"
                )
            ),
            "final_section_prose_authorized": (
                manuscript_section_evidence_packet_summary.get(
                    "final_section_prose_authorized"
                )
            ),
            "final_manuscript_prose_permission": (
                manuscript_section_evidence_packet_summary.get(
                    "final_manuscript_prose_permission"
                )
            ),
            "release_authorized": manuscript_section_evidence_packet_summary.get(
                "release_authorized"
            ),
            "method_recommendation_authorized": (
                manuscript_section_evidence_packet_summary.get(
                    "method_recommendation_authorized"
                )
            ),
            "positive_claim_promotion_authorized": (
                manuscript_section_evidence_packet_summary.get(
                    "positive_claim_promotion_authorized"
                )
            ),
            "scientific_no_method_promotion_guard_active": (
                manuscript_section_evidence_packet_summary.get(
                    "scientific_no_method_promotion_guard_active"
                )
            ),
            "failed_check_count": manuscript_section_evidence_packet_summary.get(
                "failed_check_count"
            ),
        },
        "section_claim_boundary_audit": {
            "overall_status": section_claim_boundary_audit_summary.get(
                "overall_status"
            ),
            "phase_state": section_claim_boundary_audit_summary.get("phase_state"),
            "boundary_row_count": section_claim_boundary_audit_summary.get(
                "boundary_row_count"
            ),
            "boundary_complete_row_count": section_claim_boundary_audit_summary.get(
                "boundary_complete_row_count"
            ),
            "allowed_use_complete_row_count": (
                section_claim_boundary_audit_summary.get(
                    "allowed_use_complete_row_count"
                )
            ),
            "blocked_use_complete_row_count": (
                section_claim_boundary_audit_summary.get(
                    "blocked_use_complete_row_count"
                )
            ),
            "claim_safe_surface_consistent_row_count": (
                section_claim_boundary_audit_summary.get(
                    "claim_safe_surface_consistent_row_count"
                )
            ),
            "neutral_result_linked_row_count": (
                section_claim_boundary_audit_summary.get(
                    "neutral_result_linked_row_count"
                )
            ),
            "release_target_linked_row_count": (
                section_claim_boundary_audit_summary.get(
                    "release_target_linked_row_count"
                )
            ),
            "release_authorized_target_count": (
                section_claim_boundary_audit_summary.get(
                    "release_authorized_target_count"
                )
            ),
            "neutral_ledger_prose_boundary_gap_unique_result_count": (
                section_claim_boundary_audit_summary.get(
                    "neutral_ledger_prose_boundary_gap_unique_result_count"
                )
            ),
            "section_boundary_backfill_row_count": (
                section_claim_boundary_audit_summary.get(
                    "section_boundary_backfill_row_count"
                )
            ),
            "main_results_positive_boundary_blocked": (
                section_claim_boundary_audit_summary.get(
                    "main_results_positive_boundary_blocked"
                )
            ),
            "venn_abers_negative_boundary_preserved": (
                section_claim_boundary_audit_summary.get(
                    "venn_abers_negative_boundary_preserved"
                )
            ),
            "section_packet_clean": section_claim_boundary_audit_summary.get(
                "section_packet_clean"
            ),
            "upstream_boundaries_clean": section_claim_boundary_audit_summary.get(
                "upstream_boundaries_clean"
            ),
            "post_program_controlled": section_claim_boundary_audit_summary.get(
                "post_program_controlled"
            ),
            "final_section_prose_authorized": (
                section_claim_boundary_audit_summary.get(
                    "final_section_prose_authorized"
                )
            ),
            "final_manuscript_prose_permission": (
                section_claim_boundary_audit_summary.get(
                    "final_manuscript_prose_permission"
                )
            ),
            "release_authorized": section_claim_boundary_audit_summary.get(
                "release_authorized"
            ),
            "method_recommendation_authorized": (
                section_claim_boundary_audit_summary.get(
                    "method_recommendation_authorized"
                )
            ),
            "positive_claim_promotion_authorized": (
                section_claim_boundary_audit_summary.get(
                    "positive_claim_promotion_authorized"
                )
            ),
            "scientific_no_method_promotion_guard_active": (
                section_claim_boundary_audit_summary.get(
                    "scientific_no_method_promotion_guard_active"
                )
            ),
            "failed_check_count": section_claim_boundary_audit_summary.get(
                "failed_check_count"
            ),
        },
        "article_supplement_kg_navigation_index": {
            "overall_status": article_supplement_kg_navigation_index_summary.get(
                "overall_status"
            ),
            "phase_state": article_supplement_kg_navigation_index_summary.get(
                "phase_state"
            ),
            "navigation_row_count": (
                article_supplement_kg_navigation_index_summary.get(
                    "navigation_row_count"
                )
            ),
            "section_navigation_row_count": (
                article_supplement_kg_navigation_index_summary.get(
                    "section_navigation_row_count"
                )
            ),
            "kg_site_navigation_row_count": (
                article_supplement_kg_navigation_index_summary.get(
                    "kg_site_navigation_row_count"
                )
            ),
            "source_traceable_row_count": (
                article_supplement_kg_navigation_index_summary.get(
                    "source_traceable_row_count"
                )
            ),
            "visual_table_candidate_index_row_count": (
                article_supplement_kg_navigation_index_summary.get(
                    "visual_table_candidate_index_row_count"
                )
            ),
            "visual_table_source_traceability_pass_count": (
                article_supplement_kg_navigation_index_summary.get(
                    "visual_table_source_traceability_pass_count"
                )
            ),
            "visual_table_final_authorized_count": (
                article_supplement_kg_navigation_index_summary.get(
                    "visual_table_final_authorized_count"
                )
            ),
            "release_authorized_target_count": (
                article_supplement_kg_navigation_index_summary.get(
                    "release_authorized_target_count"
                )
            ),
            "kg_node_reference_issue_count": (
                article_supplement_kg_navigation_index_summary.get(
                    "kg_node_reference_issue_count"
                )
            ),
            "missing_source_artifact_count": (
                article_supplement_kg_navigation_index_summary.get(
                    "missing_source_artifact_count"
                )
            ),
            "main_results_positive_boundary_blocked": (
                article_supplement_kg_navigation_index_summary.get(
                    "main_results_positive_boundary_blocked"
                )
            ),
            "venn_abers_negative_boundary_preserved": (
                article_supplement_kg_navigation_index_summary.get(
                    "venn_abers_negative_boundary_preserved"
                )
            ),
            "scientific_no_method_promotion_guard_active": (
                article_supplement_kg_navigation_index_summary.get(
                    "scientific_no_method_promotion_guard_active"
                )
            ),
            "neutral_language_unguarded_hit_count": (
                article_supplement_kg_navigation_index_summary.get(
                    "neutral_language_unguarded_hit_count"
                )
            ),
            "final_navigation_release_authorized": (
                article_supplement_kg_navigation_index_summary.get(
                    "final_navigation_release_authorized"
                )
            ),
            "publication_site_deployment_authorized": (
                article_supplement_kg_navigation_index_summary.get(
                    "publication_site_deployment_authorized"
                )
            ),
            "kg_citable_component_authorized": (
                article_supplement_kg_navigation_index_summary.get(
                    "kg_citable_component_authorized"
                )
            ),
            "sterile_repository_creation_authorized": (
                article_supplement_kg_navigation_index_summary.get(
                    "sterile_repository_creation_authorized"
                )
            ),
            "working_repository_final_citable": (
                article_supplement_kg_navigation_index_summary.get(
                    "working_repository_final_citable"
                )
            ),
            "method_recommendation_authorized": (
                article_supplement_kg_navigation_index_summary.get(
                    "method_recommendation_authorized"
                )
            ),
            "positive_claim_promotion_authorized": (
                article_supplement_kg_navigation_index_summary.get(
                    "positive_claim_promotion_authorized"
                )
            ),
            "failed_check_count": (
                article_supplement_kg_navigation_index_summary.get(
                    "failed_check_count"
                )
            ),
        },
        "publication_phase_progress_reconciliation": {
            "overall_status": publication_phase_progress_reconciliation_summary.get(
                "overall_status"
            ),
            "phase_state": publication_phase_progress_reconciliation_summary.get(
                "phase_state"
            ),
            "pre_prose_completed_control_count": (
                publication_phase_progress_reconciliation_summary.get(
                    "pre_prose_completed_control_count"
                )
            ),
            "pre_prose_control_count": (
                publication_phase_progress_reconciliation_summary.get(
                    "pre_prose_control_count"
                )
            ),
            "resolved_prior_blocker_count": (
                publication_phase_progress_reconciliation_summary.get(
                    "resolved_prior_blocker_count"
                )
            ),
            "active_final_blocker_count": (
                publication_phase_progress_reconciliation_summary.get(
                    "active_final_blocker_count"
                )
            ),
            "stale_goal_blocker_count": (
                publication_phase_progress_reconciliation_summary.get(
                    "stale_goal_blocker_count"
                )
            ),
            "final_publication_visual_auditor_status": (
                publication_phase_progress_reconciliation_summary.get(
                    "final_publication_visual_auditor_status"
                )
            ),
            "final_publication_visual_auditor_feedback_ready": (
                publication_phase_progress_reconciliation_summary.get(
                    "final_publication_visual_auditor_feedback_ready"
                )
            ),
            "reviewer_design_reconciled": (
                publication_phase_progress_reconciliation_summary.get(
                    "reviewer_design_reconciled"
                )
            ),
            "pre_retention_visual_audit_completed": (
                publication_phase_progress_reconciliation_summary.get(
                    "pre_retention_visual_audit_completed"
                )
            ),
            "claim_boundary_navigation_ready": (
                publication_phase_progress_reconciliation_summary.get(
                    "claim_boundary_navigation_ready"
                )
            ),
            "release_gap_ready": (
                publication_phase_progress_reconciliation_summary.get(
                    "release_gap_ready"
                )
            ),
            "neutral_guard_ready": (
                publication_phase_progress_reconciliation_summary.get(
                    "neutral_guard_ready"
                )
            ),
            "kg_publication_ready": (
                publication_phase_progress_reconciliation_summary.get(
                    "kg_publication_ready"
                )
            ),
            "goal_can_mark_complete": (
                publication_phase_progress_reconciliation_summary.get(
                    "goal_can_mark_complete"
                )
            ),
            "paper_blocked_gate_count": (
                publication_phase_progress_reconciliation_summary.get(
                    "paper_blocked_gate_count"
                )
            ),
            "positive_claim_ready_gate_count": (
                publication_phase_progress_reconciliation_summary.get(
                    "positive_claim_ready_gate_count"
                )
            ),
            "main_results_positive_boundary_blocked": (
                publication_phase_progress_reconciliation_summary.get(
                    "main_results_positive_boundary_blocked"
                )
            ),
            "venn_abers_negative_boundary_preserved": (
                publication_phase_progress_reconciliation_summary.get(
                    "venn_abers_negative_boundary_preserved"
                )
            ),
            "validated_venn_abers_regression_claim_ready": (
                publication_phase_progress_reconciliation_summary.get(
                    "validated_venn_abers_regression_claim_ready"
                )
            ),
            "method_recommendation_authorized": (
                publication_phase_progress_reconciliation_summary.get(
                    "method_recommendation_authorized"
                )
            ),
            "positive_claim_promotion_authorized": (
                publication_phase_progress_reconciliation_summary.get(
                    "positive_claim_promotion_authorized"
                )
            ),
            "failed_check_count": (
                publication_phase_progress_reconciliation_summary.get(
                    "failed_check_count"
                )
            ),
        },
        "neutral_reporting_language_audit": {
            "overall_status": neutral_reporting_language_summary.get(
                "overall_status"
            ),
            "scanned_file_count": neutral_reporting_language_summary.get(
                "scanned_file_count"
            ),
            "term_pattern_count": neutral_reporting_language_summary.get(
                "term_pattern_count"
            ),
            "term_hit_count": neutral_reporting_language_summary.get(
                "term_hit_count"
            ),
            "guarded_hit_count": neutral_reporting_language_summary.get(
                "guarded_hit_count"
            ),
            "unguarded_hit_count": neutral_reporting_language_summary.get(
                "unguarded_hit_count"
            ),
            "failed_check_count": neutral_reporting_language_summary.get(
                "failed_check_count"
            ),
            "positive_claim_ready_gate_count": (
                neutral_reporting_language_summary.get(
                    "positive_claim_ready_gate_count"
                )
            ),
            "final_result_disposition_gate_count": (
                neutral_reporting_language_summary.get(
                    "final_result_disposition_gate_count"
                )
            ),
            "publication_phase_start_authorized": (
                neutral_reporting_language_summary.get(
                    "publication_phase_start_authorized"
                )
            ),
        },
        "scientific_neutrality_interpretation_lock": {
            "overall_status": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "overall_status"
                )
            ),
            "phase_state": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "phase_state"
                )
            ),
            "interpretation_row_count": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "interpretation_row_count"
                )
            ),
            "neutral_language_unguarded_hit_count": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "neutral_language_unguarded_hit_count"
                )
            ),
            "cqr_cvplus_reporting_role": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "cqr_cvplus_reporting_role"
                )
            ),
            "venn_abers_reporting_role": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "venn_abers_reporting_role"
                )
            ),
            "main_results_positive_boundary_blocked": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "main_results_positive_boundary_blocked"
                )
            ),
            "venn_abers_negative_boundary_preserved": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "venn_abers_negative_boundary_preserved"
                )
            ),
            "validated_venn_abers_regression_claim_ready": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "validated_venn_abers_regression_claim_ready"
                )
            ),
            "method_recommendation_authorized": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "method_recommendation_authorized"
                )
            ),
            "positive_claim_promotion_authorized": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "positive_claim_promotion_authorized"
                )
            ),
            "final_manuscript_prose_permission": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "final_manuscript_prose_permission"
                )
            ),
            "sterile_repository_creation_authorized": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "sterile_repository_creation_authorized"
                )
            ),
            "working_repository_final_citable": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "working_repository_final_citable"
                )
            ),
            "scientific_test_not_method_promotion": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "scientific_test_not_method_promotion"
                )
            ),
            "analysis_only_no_champion_method": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "analysis_only_no_champion_method"
                )
            ),
            "method_champion_authorized": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "method_champion_authorized"
                )
            ),
            "method_advocacy_authorized": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "method_advocacy_authorized"
                )
            ),
            "result_reporting_policy": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "result_reporting_policy"
                )
            ),
            "authorization_violation_count": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "authorization_violation_count"
                )
            ),
            "promotional_phrase_hit_count": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "promotional_phrase_hit_count"
                )
            ),
            "missing_source_artifact_count": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "missing_source_artifact_count"
                )
            ),
            "failed_check_count": (
                scientific_neutrality_interpretation_lock_summary.get(
                    "failed_check_count"
                )
            ),
        },
        "final_publication_output_authorization_protocol": {
            "overall_status": (
                final_publication_output_authorization_protocol_summary.get(
                    "overall_status"
                )
            ),
            "phase_state": (
                final_publication_output_authorization_protocol_summary.get(
                    "phase_state"
                )
            ),
            "final_output_authorization_protocol_status": (
                final_publication_output_authorization_protocol_summary.get(
                    "final_output_authorization_protocol_status"
                )
            ),
            "authorization_row_count": (
                final_publication_output_authorization_protocol_summary.get(
                    "authorization_row_count"
                )
            ),
            "blocked_authorization_row_count": (
                final_publication_output_authorization_protocol_summary.get(
                    "blocked_authorization_row_count"
                )
            ),
            "missing_policy_row_count": (
                final_publication_output_authorization_protocol_summary.get(
                    "missing_policy_row_count"
                )
            ),
            "ready_to_authorize_output_count": (
                final_publication_output_authorization_protocol_summary.get(
                    "ready_to_authorize_output_count"
                )
            ),
            "active_final_blocker_count": (
                final_publication_output_authorization_protocol_summary.get(
                    "active_final_blocker_count"
                )
            ),
            "goal_can_mark_complete": (
                final_publication_output_authorization_protocol_summary.get(
                    "goal_can_mark_complete"
                )
            ),
            "scientific_test_not_method_promotion": (
                final_publication_output_authorization_protocol_summary.get(
                    "scientific_test_not_method_promotion"
                )
            ),
            "paper_blocked_gate_count": (
                final_publication_output_authorization_protocol_summary.get(
                    "paper_blocked_gate_count"
                )
            ),
            "positive_claim_ready_gate_count": (
                final_publication_output_authorization_protocol_summary.get(
                    "positive_claim_ready_gate_count"
                )
            ),
            "release_authorized_count": (
                final_publication_output_authorization_protocol_summary.get(
                    "release_authorized_count"
                )
            ),
            "final_manuscript_prose_permission": (
                final_publication_output_authorization_protocol_summary.get(
                    "final_manuscript_prose_permission"
                )
            ),
            "final_visual_table_retention_authorized": (
                final_publication_output_authorization_protocol_summary.get(
                    "final_visual_table_retention_authorized"
                )
            ),
            "latex_html_authoring_authorized": (
                final_publication_output_authorization_protocol_summary.get(
                    "latex_html_authoring_authorized"
                )
            ),
            "publication_site_deployment_authorized": (
                final_publication_output_authorization_protocol_summary.get(
                    "publication_site_deployment_authorized"
                )
            ),
            "kg_citable_component_authorized": (
                final_publication_output_authorization_protocol_summary.get(
                    "kg_citable_component_authorized"
                )
            ),
            "sterile_repository_creation_authorized": (
                final_publication_output_authorization_protocol_summary.get(
                    "sterile_repository_creation_authorized"
                )
            ),
            "working_repository_final_citable": (
                final_publication_output_authorization_protocol_summary.get(
                    "working_repository_final_citable"
                )
            ),
            "method_recommendation_authorized": (
                final_publication_output_authorization_protocol_summary.get(
                    "method_recommendation_authorized"
                )
            ),
            "positive_claim_promotion_authorized": (
                final_publication_output_authorization_protocol_summary.get(
                    "positive_claim_promotion_authorized"
                )
            ),
            "analysis_only_no_champion_method": (
                final_publication_output_authorization_protocol_summary.get(
                    "analysis_only_no_champion_method"
                )
            ),
            "method_champion_authorized": (
                final_publication_output_authorization_protocol_summary.get(
                    "method_champion_authorized"
                )
            ),
            "method_advocacy_authorized": (
                final_publication_output_authorization_protocol_summary.get(
                    "method_advocacy_authorized"
                )
            ),
            "result_reporting_policy": (
                final_publication_output_authorization_protocol_summary.get(
                    "result_reporting_policy"
                )
            ),
            "authorization_violation_count": (
                final_publication_output_authorization_protocol_summary.get(
                    "authorization_violation_count"
                )
            ),
            "missing_source_artifact_count": (
                final_publication_output_authorization_protocol_summary.get(
                    "missing_source_artifact_count"
                )
            ),
            "failed_check_count": (
                final_publication_output_authorization_protocol_summary.get(
                    "failed_check_count"
                )
            ),
        },
        "publication_claim_evidence_verification_matrix": {
            "overall_status": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "overall_status"
                )
            ),
            "phase_state": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "phase_state"
                )
            ),
            "verification_row_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "verification_row_count"
                )
            ),
            "verification_pass_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "verification_pass_count"
                )
            ),
            "source_traceable_row_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "source_traceable_row_count"
                )
            ),
            "boundary_aligned_row_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "boundary_aligned_row_count"
                )
            ),
            "navigation_aligned_row_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "navigation_aligned_row_count"
                )
            ),
            "kg_reference_issue_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "kg_reference_issue_count"
                )
            ),
            "safe_pre_prose_evidence_row_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "safe_pre_prose_evidence_row_count"
                )
            ),
            "blocked_positive_row_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "blocked_positive_row_count"
                )
            ),
            "main_results_blocked_row_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "main_results_blocked_row_count"
                )
            ),
            "venn_abers_negative_ready_row_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "venn_abers_negative_ready_row_count"
                )
            ),
            "source_authorization_violation_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "source_authorization_violation_count"
                )
            ),
            "row_authorization_violation_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "row_authorization_violation_count"
                )
            ),
            "final_manuscript_prose_permission": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "final_manuscript_prose_permission"
                )
            ),
            "final_visual_table_retention_authorized": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "final_visual_table_retention_authorized"
                )
            ),
            "latex_html_authoring_authorized": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "latex_html_authoring_authorized"
                )
            ),
            "release_authorized": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "release_authorized"
                )
            ),
            "method_recommendation_authorized": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "method_recommendation_authorized"
                )
            ),
            "method_champion_authorized": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "method_champion_authorized"
                )
            ),
            "method_advocacy_authorized": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "method_advocacy_authorized"
                )
            ),
            "positive_claim_promotion_authorized": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "positive_claim_promotion_authorized"
                )
            ),
            "analysis_only_no_champion_method": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "analysis_only_no_champion_method"
                )
            ),
            "result_reporting_policy": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "result_reporting_policy"
                )
            ),
            "missing_source_artifact_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "missing_source_artifact_count"
                )
            ),
            "current_publication_draft_artifact_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "current_publication_draft_artifact_count"
                )
            ),
            "current_publication_draft_artifact_pass_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "current_publication_draft_artifact_pass_count"
                )
            ),
            "current_publication_draft_artifact_traceable_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "current_publication_draft_artifact_traceable_count"
                )
            ),
            "current_publication_draft_missing_source_key_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "current_publication_draft_missing_source_key_count"
                )
            ),
            "current_publication_draft_missing_artifact_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "current_publication_draft_missing_artifact_count"
                )
            ),
            "current_publication_draft_authorization_violation_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "current_publication_draft_authorization_violation_count"
                )
            ),
            "current_publication_draft_failed_upstream_check_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "current_publication_draft_failed_upstream_check_count"
                )
            ),
            "failed_check_count": (
                publication_claim_evidence_verification_matrix_summary.get(
                    "failed_check_count"
                )
            ),
        },
        "sterile_repository_staging_manifest": {
            "overall_status": sterile_repository_staging_manifest_summary.get(
                "overall_status"
            ),
            "phase_state": sterile_repository_staging_manifest_summary.get(
                "phase_state"
            ),
            "staging_manifest_status": (
                sterile_repository_staging_manifest_summary.get(
                    "staging_manifest_status"
                )
            ),
            "repository_visibility_at_creation": (
                sterile_repository_staging_manifest_summary.get(
                    "repository_visibility_at_creation"
                )
            ),
            "eventual_visibility": sterile_repository_staging_manifest_summary.get(
                "eventual_visibility"
            ),
            "required_content_row_count": (
                sterile_repository_staging_manifest_summary.get(
                    "required_content_row_count"
                )
            ),
            "required_content_traceable_count": (
                sterile_repository_staging_manifest_summary.get(
                    "required_content_traceable_count"
                )
            ),
            "required_content_with_blocking_gate_count": (
                sterile_repository_staging_manifest_summary.get(
                    "required_content_with_blocking_gate_count"
                )
            ),
            "candidate_inclusion_risk_hit_count": (
                sterile_repository_staging_manifest_summary.get(
                    "candidate_inclusion_risk_hit_count"
                )
            ),
            "exclusion_policy_row_count": (
                sterile_repository_staging_manifest_summary.get(
                    "exclusion_policy_row_count"
                )
            ),
            "exclusion_source_traceable_count": (
                sterile_repository_staging_manifest_summary.get(
                    "exclusion_source_traceable_count"
                )
            ),
            "private_repository_created": (
                sterile_repository_staging_manifest_summary.get(
                    "private_repository_created"
                )
            ),
            "sterile_repository_creation_authorized": (
                sterile_repository_staging_manifest_summary.get(
                    "sterile_repository_creation_authorized"
                )
            ),
            "sterile_release_packaging_authorized": (
                sterile_repository_staging_manifest_summary.get(
                    "sterile_release_packaging_authorized"
                )
            ),
            "release_authorized": sterile_repository_staging_manifest_summary.get(
                "release_authorized"
            ),
            "working_repository_final_citable": (
                sterile_repository_staging_manifest_summary.get(
                    "working_repository_final_citable"
                )
            ),
            "method_recommendation_authorized": (
                sterile_repository_staging_manifest_summary.get(
                    "method_recommendation_authorized"
                )
            ),
            "positive_claim_promotion_authorized": (
                sterile_repository_staging_manifest_summary.get(
                    "positive_claim_promotion_authorized"
                )
            ),
            "analysis_only_no_champion_method": (
                sterile_repository_staging_manifest_summary.get(
                    "analysis_only_no_champion_method"
                )
            ),
            "method_champion_authorized": (
                sterile_repository_staging_manifest_summary.get(
                    "method_champion_authorized"
                )
            ),
            "method_advocacy_authorized": (
                sterile_repository_staging_manifest_summary.get(
                    "method_advocacy_authorized"
                )
            ),
            "result_reporting_policy": (
                sterile_repository_staging_manifest_summary.get(
                    "result_reporting_policy"
                )
            ),
            "authorization_violation_count": (
                sterile_repository_staging_manifest_summary.get(
                    "authorization_violation_count"
                )
            ),
            "missing_source_artifact_count": (
                sterile_repository_staging_manifest_summary.get(
                    "missing_source_artifact_count"
                )
            ),
            "failed_check_count": sterile_repository_staging_manifest_summary.get(
                "failed_check_count"
            ),
        },
        "neutral_experiment_closure_audit": {
            "overall_status": neutral_experiment_closure_summary.get(
                "overall_status"
            ),
            "neutral_closure_ready": neutral_experiment_closure_summary.get(
                "neutral_closure_ready"
            ),
            "goal_policy_update_required": neutral_experiment_closure_summary.get(
                "goal_policy_update_required"
            ),
            "publication_phase_deferred": neutral_experiment_closure_summary.get(
                "publication_phase_deferred"
            ),
            "publication_preparation_authorized": (
                neutral_experiment_closure_summary.get(
                    "publication_preparation_authorized"
                )
            ),
            "failed_check_count": neutral_experiment_closure_summary.get(
                "failed_check_count"
            ),
            "gate_count": neutral_experiment_closure_summary.get("gate_count"),
            "final_disposition_gate_count": neutral_experiment_closure_summary.get(
                "final_disposition_gate_count"
            ),
            "positive_claim_ready_gate_count": neutral_experiment_closure_summary.get(
                "positive_claim_ready_gate_count"
            ),
            "scoped_or_negative_path_ready_gate_count": (
                neutral_experiment_closure_summary.get(
                    "scoped_or_negative_path_ready_gate_count"
                )
            ),
            "ready_action_count": neutral_experiment_closure_summary.get(
                "ready_action_count"
            ),
            "local_execution_gap_gate_count": neutral_experiment_closure_summary.get(
                "local_execution_gap_gate_count"
            ),
            "publication_completed_rows": neutral_experiment_closure_summary.get(
                "publication_completed_rows"
            ),
            "neutral_language_unguarded_hit_count": (
                neutral_experiment_closure_summary.get(
                    "neutral_language_unguarded_hit_count"
                )
            ),
        },
        "goal_completion_audit": {
            "overall_status": goal_completion_summary.get("overall_status"),
            "requirement_count": goal_completion_summary.get("requirement_count"),
            "empirical_requirement_count": goal_completion_summary.get(
                "empirical_requirement_count"
            ),
            "strict_complete_requirement_count": goal_completion_summary.get(
                "strict_complete_requirement_count"
            ),
            "complete_or_scoped_requirement_count": goal_completion_summary.get(
                "complete_or_scoped_requirement_count"
            ),
            "noncomplete_requirement_count": goal_completion_summary.get(
                "noncomplete_requirement_count"
            ),
            "blocked_positive_claim_requirement_count": goal_completion_summary.get(
                "blocked_positive_claim_requirement_count"
            ),
            "planned_deferred_requirement_count": goal_completion_summary.get(
                "planned_deferred_requirement_count"
            ),
            "in_progress_requirement_count": goal_completion_summary.get(
                "in_progress_requirement_count"
            ),
            "neutral_empirical_phase_complete": goal_completion_summary.get(
                "neutral_empirical_phase_complete"
            ),
            "empirical_completion_policy": goal_completion_summary.get(
                "empirical_completion_policy"
            ),
            "positive_claim_blocking_gate_count": goal_completion_summary.get(
                "positive_claim_blocking_gate_count"
            ),
            "paper_blocked_gate_count": goal_completion_summary.get(
                "paper_blocked_gate_count"
            ),
            "paper_gate_closure_execution_plan_status": goal_completion_summary.get(
                "paper_gate_closure_execution_plan_status"
            ),
            "paper_gate_closure_action_count": goal_completion_summary.get(
                "paper_gate_closure_action_count"
            ),
            "paper_gate_closure_ready_action_count": goal_completion_summary.get(
                "paper_gate_closure_ready_action_count"
            ),
            "paper_gate_protocol_design_bundle_status": goal_completion_summary.get(
                "paper_gate_protocol_design_bundle_status"
            ),
            "paper_gate_protocol_design_complete_action_count": (
                goal_completion_summary.get(
                    "paper_gate_protocol_design_complete_action_count"
                )
            ),
            "paper_gate_protocol_design_downstream_action_count": (
                goal_completion_summary.get(
                    "paper_gate_protocol_design_downstream_action_count"
                )
            ),
            "positive_claim_ready_gate_count": goal_completion_summary.get(
                "positive_claim_ready_gate_count"
            ),
            "local_execution_gap_gate_count": goal_completion_summary.get(
                "local_execution_gap_gate_count"
            ),
            "publication_completed_rows": goal_completion_summary.get(
                "publication_completed_rows"
            ),
            "primary_diagnostic_method": goal_completion_summary.get(
                "primary_diagnostic_method"
            ),
            "validated_venn_abers_regression_claim_ready": goal_completion_summary.get(
                "validated_venn_abers_regression_claim_ready"
            ),
            "can_mark_goal_complete": goal_completion_summary.get(
                "can_mark_goal_complete"
            ),
            "can_start_post_experiment_publication": goal_completion_summary.get(
                "can_start_post_experiment_publication"
            ),
            "can_start_post_experiment_publication_preparation": (
                goal_completion_summary.get(
                    "can_start_post_experiment_publication_preparation"
                )
            ),
            "positive_claim_publication_ready": goal_completion_summary.get(
                "positive_claim_publication_ready"
            ),
            "neutral_publication_route_allowed": goal_completion_summary.get(
                "neutral_publication_route_allowed"
            ),
            "final_dispositions_complete": goal_completion_summary.get(
                "final_dispositions_complete"
            ),
            "status_counts": goal_completion_summary.get("status_counts", {}),
        },
        "knowledge_graph": {
            "status": kg_status,
            "issue_counts_by_severity": kg.get("issue_counts_by_severity", {}),
            "node_count": kg_graph.get("node_count"),
            "edge_count": kg_graph.get("edge_count"),
            "edge_node_ratio": kg_graph.get("edge_node_ratio"),
            "isolated_node_count": kg_graph.get("isolated_node_count"),
            "weak_component_count": kg_graph.get("weak_component_count"),
            "average_edge_confidence": kg_traceability.get("average_edge_confidence"),
            "distinct_edge_confidence_value_count": kg_traceability.get(
                "distinct_edge_confidence_value_count"
            ),
            "edge_provenance_coverage": kg_traceability.get(
                "explicit_edge_provenance_coverage"
            ),
            "specific_edge_provenance_coverage": kg_traceability.get(
                "specific_edge_provenance_coverage"
            ),
            "edge_selector_provenance_coverage": kg_traceability.get(
                "edge_selector_provenance_coverage"
            ),
            "claim_edge_selector_provenance_coverage": kg_claim_traceability.get(
                "claim_edge_selector_provenance_coverage"
            ),
            "claim_edge_missing_selector_count": kg_claim_traceability.get(
                "claim_edge_missing_selector_count"
            ),
            "claim_edge_count": kg_claim_traceability.get("claim_edge_count"),
            "claim_relation_selector_coverage": kg_claim_traceability.get(
                "claim_relation_selector_coverage"
            ),
            "edge_confidence_coverage": kg_traceability.get("edge_confidence_coverage"),
            "edge_confidence_reason_coverage": kg_traceability.get(
                "edge_confidence_reason_coverage"
            ),
            "weak_provenance_confidence_one_count": kg_traceability.get(
                "weak_provenance_confidence_one_count"
            ),
            "observation_node_ratio": kg_observations.get("observation_node_ratio"),
            "paper_evidence_observation_node_ratio": kg_observations.get(
                "paper_evidence_observation_node_ratio"
            ),
            "topology_observation_count": kg_observations.get(
                "topology_observation_count"
            ),
            "total_observation_count": kg_observations.get("total_observation_count"),
            "direct_summary_coverage": kg_summaries.get("direct_summary_coverage"),
            "semantic_summary_coverage": kg_summaries.get("semantic_summary_coverage"),
            "unknown_node_types": kg_ontology.get("unknown_node_types", []),
            "unknown_relation_types": kg_ontology.get("unknown_relation_types", []),
            "domain_range_violation_count": kg_ontology.get(
                "domain_range_violation_count"
            ),
            "critical_linkage": {
                key: {
                    "coverage": value.get("coverage"),
                    "covered_count": value.get("covered_count"),
                    "total_count": value.get("total_count"),
                }
                for key, value in kg_critical.items()
                if isinstance(value, dict) and "coverage" in value
            },
            "endpoint_result_relation_coverage": {
                key: {
                    "coverage": value.get("coverage"),
                    "covered_count": value.get("covered_count"),
                    "total_count": value.get("total_count"),
                }
                for key, value in (
                    kg_endpoint.get("endpoint_result_relation_coverage") or {}
                ).items()
                if isinstance(value, dict)
            },
            "endpoint_result_count": kg_endpoint.get("endpoint_result_count"),
            "endpoint_caveat_count": kg_endpoint.get("endpoint_caveat_count"),
            "uncaveated_endpoint_result_count": kg_endpoint.get(
                "uncaveated_endpoint_result_count"
            ),
        },
    }


def gate_payload(
    *,
    root: Path,
    step_results: list[dict[str, Any]],
    complete: bool,
    pre_run_dirty: dict[str, Any] | None = None,
    git_commit: str | None = None,
) -> dict[str, Any]:
    pre_run_dirty = pre_run_dirty or dirty_snapshot(root)
    post_run_dirty = dirty_snapshot(root)
    git_commit = git_commit or current_commit(root)
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(root),
        "git_commit": git_commit,
        "git_dirty": pre_run_dirty,
        "pre_run_git_dirty": pre_run_dirty,
        "post_run_git_dirty": post_run_dirty,
        "git_dirty_semantics": {
            "git_dirty": "backward_compatible_alias_for_pre_run_git_dirty",
            "pre_run_git_dirty": "repository state before the retrospective gate wrote or refreshed artifacts",
            "post_run_git_dirty": "repository state after currently materialized gate artifacts were refreshed",
        },
        "complete": complete,
        "claim_boundaries": CLAIM_BOUNDARIES,
        "summary": build_scientific_summary(root, step_results),
        "steps": step_results,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    kg = summary["knowledge_graph"]
    cross = summary["cross_run"]
    manuscript = summary["manuscript_manifest_completeness"]
    claim_register = summary["manuscript_claim_register_consistency"]
    final_selection = summary["final_selection_claim_boundary"]
    fairness_sampling_weight_policy = summary["fairness_sampling_weight_policy"]
    fairness_population = summary["fairness_population_readiness"]
    fairness_group_multiplicity_scope = summary["fairness_group_multiplicity_scope"]
    publication = summary["publication_methodology_readiness"]
    venn_abers_validation = summary["venn_abers_validation_readiness"]
    venn_abers_grid_ivapd = summary["venn_abers_grid_ivapd_validation_protocol"]
    venn_abers_grid_expansion = summary["venn_abers_grid_expansion_plan"]
    venn_abers_grid_failure_modes = summary[
        "venn_abers_grid_failure_mode_decomposition"
    ]
    venn_abers_claim_gate_matrix = summary["venn_abers_claim_gate_matrix"]
    venn_abers_grid_expansion_batch = summary["venn_abers_grid_expansion_batch"]
    selection_multiplicity = summary["selection_multiplicity_protocol"]
    bounded_support = summary["bounded_support_protocol"]
    target_domain_provenance = summary["target_domain_provenance"]
    external_source_discovery = summary["external_source_discovery_watchlist"]
    bounded_support_posthandling = summary["bounded_support_posthandling_validation"]
    bounded_support_dataset = summary["bounded_support_dataset_audit"]
    bounded_support_endpoint_closure = summary[
        "bounded_support_endpoint_closure_audit"
    ]
    bounded_support_positive_validation = summary[
        "bounded_support_positive_validation_protocol"
    ]
    experiment_accounting = summary["experiment_accounting"]
    method_performance = summary["method_performance_synthesis"]
    method_selection_candidate = summary["method_selection_candidate_audit"]
    method_selection_robustness = summary["method_selection_robustness_audit"]
    method_selection_alpha_expansion = summary["method_selection_alpha_expansion_plan"]
    method_selection_alpha_expansion_execution = summary[
        "method_selection_alpha_expansion_execution"
    ]
    method_selection_inferential = summary["method_selection_inferential_audit"]
    manuscript_readiness = summary["manuscript_readiness_map"]
    manuscript_bundle_eligibility = summary["manuscript_bundle_eligibility_matrix"]
    duplicate_content_quarantine = summary["duplicate_content_quarantine"]
    venn_abers_negative_disposition = summary[
        "venn_abers_negative_evidence_disposition"
    ]
    graph_artifact = summary["graph_artifact_readiness"]
    paper_gate_protocol_design = summary["paper_gate_protocol_design_bundle"]
    paper_gate_execution_plan = summary["paper_gate_closure_execution_plan"]
    fairness_group_diagnostic = summary["fairness_group_diagnostic_audit"]
    kg_publication = summary["kg_publication_quality"]
    scientific_review = summary["scientific_review_finding_register"]
    publication_activation = summary["post_experiment_publication_activation_audit"]
    publication_preparation = summary["publication_preparation_packets"]
    reviewer_design = summary["reviewer_design_brief"]
    visual_audit_plan = summary["publication_visual_audit_plan"]
    visual_table_audit_report = summary["visual_table_audit_report"]
    visual_table_render_candidate_audit = summary[
        "visual_table_render_candidate_audit"
    ]
    publication_retention_readiness = summary[
        "publication_retention_readiness_audit"
    ]
    final_visual_auditor = summary[
        "final_publication_visual_auditor_readiness"
    ]
    neutral_result_ledger = summary["neutral_result_ledger"]
    article_supplement_blueprint_alignment = summary[
        "article_supplement_blueprint_alignment"
    ]
    publication_release_gap = summary["publication_release_gap_register"]
    individual_experiment_report_blueprint = summary[
        "individual_experiment_report_blueprint"
    ]
    claim_safe_result_extraction_matrix = summary[
        "claim_safe_result_extraction_matrix"
    ]
    manuscript_section_evidence_packet = summary[
        "manuscript_section_evidence_packet"
    ]
    section_claim_boundary_audit = summary["section_claim_boundary_audit"]
    article_supplement_kg_navigation_index = summary[
        "article_supplement_kg_navigation_index"
    ]
    publication_phase_progress_reconciliation = summary[
        "publication_phase_progress_reconciliation"
    ]
    neutral_reporting_language = summary["neutral_reporting_language_audit"]
    scientific_neutrality_interpretation_lock = summary[
        "scientific_neutrality_interpretation_lock"
    ]
    final_output_authorization_protocol = summary[
        "final_publication_output_authorization_protocol"
    ]
    publication_claim_evidence_verification = summary[
        "publication_claim_evidence_verification_matrix"
    ]
    sterile_repository_staging_manifest = summary[
        "sterile_repository_staging_manifest"
    ]
    neutral_experiment_closure = summary["neutral_experiment_closure_audit"]
    goal_completion = summary["goal_completion_audit"]
    lines = [
        "# Retrospective Quality Gate",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Git commit: `{payload.get('git_commit')}`",
        f"- Pre-run Git dirty: `{(payload.get('pre_run_git_dirty') or {}).get('is_dirty')}` with {(payload.get('pre_run_git_dirty') or {}).get('dirty_path_count')} dirty paths",
        f"- Post-run Git dirty: `{(payload.get('post_run_git_dirty') or {}).get('is_dirty')}` with {(payload.get('post_run_git_dirty') or {}).get('dirty_path_count')} dirty paths",
        f"- Pre-run Git diff name-status hash: `{(payload.get('pre_run_git_dirty') or {}).get('diff_name_status_sha256')}`",
        f"- Pre-run Git full patch hash: `{(payload.get('pre_run_git_dirty') or {}).get('diff_patch_sha256')}`",
        f"- Pre-run Git relevant patch hash: `{(payload.get('pre_run_git_dirty') or {}).get('relevant_diff_patch_sha256')}`",
        f"- Complete: `{payload['complete']}`",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Step status counts: `{summary['step_status_counts']}`",
        f"- Reports scanned: {cross.get('reports_scanned')}",
        f"- Completed ledger rows represented: {cross.get('total_completed_rows')}",
        f"- Hard leakage clean in scanned artifacts: `{summary['hard_leakage_clean_in_scanned_artifacts']}`",
        f"- Blocking issue counts: `{cross.get('blocking_issue_counts')}`",
        f"- Caveat counts: `{cross.get('caveat_counts')}`",
        f"- Manuscript manifest audit: `{manuscript.get('overall_status')}` over {manuscript.get('manifest_count')} manifests",
        f"- Manuscript bundle-index status: `{manuscript.get('bundle_index_status')}`",
        f"- Manuscript claim-register consistency: `{claim_register.get('overall_status')}` over {claim_register.get('claim_count')} claims",
        f"- Final-selection claim boundary: `{final_selection.get('overall_status')}` with {final_selection.get('blocked_requirement_count')} blocked requirements and {final_selection.get('open_remediation_actions')} open remediation actions",
        f"- Fairness sampling/weight policy: `{fairness_sampling_weight_policy.get('overall_status')}` with {fairness_sampling_weight_policy.get('policy_declared_bundle_count')} policy-declared bundles, {fairness_sampling_weight_policy.get('weighted_estimand_applied_bundle_count')} weighted-estimand bundles, and {fairness_sampling_weight_policy.get('population_fairness_ready_bundle_count')} population-fairness-ready bundles",
        f"- Fairness group diagnostic audit: `{fairness_group_diagnostic.get('overall_status')}` with {fairness_group_diagnostic.get('group_counts_recorded_bundle_count')} group-count bundles, {fairness_group_diagnostic.get('missingness_by_group_audited_bundle_count')} missingness-audited bundles, and {fairness_group_diagnostic.get('group_gap_uncertainty_recorded_bundle_count')} gap-uncertainty bundles",
        f"- Fairness group multiplicity scope: `{fairness_group_multiplicity_scope.get('overall_status')}` with {fairness_group_multiplicity_scope.get('multiplicity_scope_declared_bundle_count')} scoped bundles, {fairness_group_multiplicity_scope.get('comparison_family_count')} comparison families, claim-register citation `{fairness_group_multiplicity_scope.get('claim_register_cites_multiplicity_record')}`, and fairness claim ready `{fairness_group_multiplicity_scope.get('current_manuscript_fairness_population_claim_ready')}`",
        f"- Fairness/population readiness: `{fairness_population.get('overall_status')}` with {fairness_population.get('diagnostic_group_bundle_count')} diagnostic-group bundles and {fairness_population.get('population_fairness_ready_bundle_count')} population-fairness-ready bundles",
        f"- Publication methodology readiness: `{publication.get('overall_status')}` with {publication.get('blocked_final_requirement_count')} blocked final requirements",
        f"- Venn-Abers validation readiness: `{venn_abers_validation.get('overall_status')}` with {venn_abers_validation.get('undercoverage_panel_count')} / {venn_abers_validation.get('diagnostic_panel_count')} undercoverage panels and {venn_abers_validation.get('undercoverage_run_count')} / {venn_abers_validation.get('diagnostic_run_count')} undercoverage runs",
        f"- Venn-Abers grid/IVAPD validation protocol: `{venn_abers_grid_ivapd.get('overall_status')}` with {venn_abers_grid_ivapd.get('validation_blocker_count')} blockers, {venn_abers_grid_ivapd.get('total_grid_reference_rows_scored')} grid rows ({venn_abers_grid_ivapd.get('source_grid_reference_rows_scored')} source + {venn_abers_grid_ivapd.get('worker_grid_reference_rows_scored')} worker), {venn_abers_grid_ivapd.get('worker_grid_hit_upper_count')} worker grid-upper hits, and {venn_abers_grid_ivapd.get('total_ivapd_rows_scored')} IVAPD rows",
        f"- Venn-Abers grid expansion plan: `{venn_abers_grid_expansion.get('overall_status')}` with {venn_abers_grid_expansion.get('total_grid_rows_completed')} completed rows, {venn_abers_grid_expansion.get('total_grid_rows_pending')} pending rows, and {venn_abers_grid_expansion.get('next_batch_total_rows')} next-batch rows",
        f"- Venn-Abers grid failure modes: `{venn_abers_grid_failure_modes.get('overall_status')}` with {venn_abers_grid_failure_modes.get('coverage_failure_run_count')} coverage-failure runs, {venn_abers_grid_failure_modes.get('upper_boundary_failure_run_count')} upper-boundary runs, and claim status `{venn_abers_grid_failure_modes.get('claim_status')}`",
        f"- Venn-Abers claim gate matrix: `{venn_abers_claim_gate_matrix.get('overall_status')}` with {venn_abers_claim_gate_matrix.get('positive_claim_pass_count')} / {venn_abers_claim_gate_matrix.get('positive_claim_requirement_count')} positive-claim requirements passing and blockers `{venn_abers_claim_gate_matrix.get('blocked_positive_requirement_ids')}`",
        f"- Venn-Abers grid expansion latest batch: {venn_abers_grid_expansion_batch.get('completed_new_row_tasks')} completed / {venn_abers_grid_expansion_batch.get('failed_new_row_tasks')} failed new row tasks; ledger has {venn_abers_grid_expansion_batch.get('after_unique_completed_row_count')} unique completed rows and {venn_abers_grid_expansion_batch.get('grid_hit_upper_completed_count')} grid-upper hits",
        f"- Selection/multiplicity protocol: `{selection_multiplicity.get('overall_status')}` covering {selection_multiplicity.get('covered_manifest_field_count')} / {selection_multiplicity.get('required_manifest_field_count')} manifest fields, {selection_multiplicity.get('ranking_scope_count')} ranking scopes, {selection_multiplicity.get('selection_record_count')} no-selection records, and {selection_multiplicity.get('completed_ledger_rows_scanned')} completed ledger rows scanned",
        f"- Bounded-support protocol: `{bounded_support.get('overall_status')}` with {bounded_support.get('target_domain_class_count')} target-domain classes and validity support `{bounded_support.get('can_support_bounded_support_validity')}`",
        f"- Target-domain provenance: `{target_domain_provenance.get('overall_status')}` over {target_domain_provenance.get('row_count')} dataset-target rows",
        f"- External source discovery watchlist: `{external_source_discovery.get('overall_status')}` over {external_source_discovery.get('source_family_count')} source families, OpenML discovery/ranked rows {external_source_discovery.get('openml_discovery_rows')} / {external_source_discovery.get('openml_ranked_rows')}",
        f"- Bounded-support post-handling validation: `{bounded_support_posthandling.get('overall_status')}` with {bounded_support_posthandling.get('validated_bundle_count')} / {bounded_support_posthandling.get('available_bundle_count')} bundles validated",
        f"- Bounded-support post-handling state resumed/written records: {bounded_support_posthandling.get('state_resumed_records')} / {bounded_support_posthandling.get('state_written_records')}",
        f"- Bounded-support dataset audit: `{bounded_support_dataset.get('overall_status')}` over {bounded_support_dataset.get('bundle_count')} bundles with {bounded_support_dataset.get('bounded_support_ready_bundle_count')} ready for bounded-support claims; endpoint support split {bounded_support_dataset.get('endpoint_support_clean_bundle_count')} clean / {bounded_support_dataset.get('endpoint_support_not_applicable_bundle_count')} not applicable / {bounded_support_dataset.get('endpoint_support_blocked_or_incomplete_bundle_count')} blocked-or-incomplete",
        f"- Bounded-support endpoint closure audit: `{bounded_support_endpoint_closure.get('overall_status')}` action `{bounded_support_endpoint_closure.get('action_status')}` with {bounded_support_endpoint_closure.get('closed_policy_bundle_count')} closed policy bundles, {bounded_support_endpoint_closure.get('open_endpoint_count_backfill_bundle_count')} open backfill bundles, and current validity claim ready `{bounded_support_endpoint_closure.get('current_manuscript_bounded_support_validity_claim_ready')}`",
        f"- Bounded-support positive validation protocol: `{bounded_support_positive_validation.get('overall_status')}` action `{bounded_support_positive_validation.get('action_status')}` with {bounded_support_positive_validation.get('positive_claim_ready_bundle_count')} claim-ready bundles, {bounded_support_positive_validation.get('endpoint_blocked_or_incomplete_bundle_count')} endpoint-blocked bundles, and {bounded_support_positive_validation.get('positive_acceptance_failed_count')} failed positive acceptance criteria",
        f"- Experiment accounting: `{experiment_accounting.get('overall_status')}` with raw/canonical/completed rows {experiment_accounting.get('raw_ledger_row_count')} / {experiment_accounting.get('canonical_ledger_row_count')} / {experiment_accounting.get('canonical_completed_row_count')}; publication scope {experiment_accounting.get('cross_run_completed_rows')} and manuscript bounded-support scope {experiment_accounting.get('bounded_support_selected_completed_rows')}",
        f"- Method performance synthesis: `{method_performance.get('overall_status')}` over {method_performance.get('completed_ledger_rows')} publication rows, {method_performance.get('method_count')} methods, {method_performance.get('broad_support_method_count')} broad-support methods, and {method_performance.get('frontier_cell_count')} dataset-alpha frontier cells; final selection remains `{method_performance.get('claim_status')}`",
        f"- Method selection candidate audit: `{method_selection_candidate.get('overall_status')}` with primary candidate `{method_selection_candidate.get('primary_candidate_method')}`, {method_selection_candidate.get('shortlist_method_count')} shortlist methods, {method_selection_candidate.get('paired_comparison_count')} paired comparisons, and claim status `{method_selection_candidate.get('claim_status')}`",
        f"- Method selection robustness audit: `{method_selection_robustness.get('overall_status')}` with common-cell selected method `{method_selection_robustness.get('common_cell_selected_method')}`, alpha-balanced selected method `{method_selection_robustness.get('alpha_balanced_selected_method')}`, alpha imbalance `{method_selection_robustness.get('common_alpha_imbalance_status')}`, winner counts `{method_selection_robustness.get('common_cell_winner_counts')}`, leave-one-dataset retention {method_selection_robustness.get('leave_one_dataset_primary_retention_rate')}, leave-one-alpha retention {method_selection_robustness.get('leave_one_alpha_primary_retention_rate')}, and bootstrap primary selection rate {method_selection_robustness.get('bootstrap_primary_selection_rate')}",
        f"- Method selection alpha expansion plan: `{method_selection_alpha_expansion.get('overall_status')}` needs {method_selection_alpha_expansion.get('additional_common_cells_needed_to_clear_threshold')} extra common alpha cells, queues {method_selection_alpha_expansion.get('next_batch_dataset_alpha_task_count')} dataset-alpha tasks / {method_selection_alpha_expansion.get('next_batch_method_run_task_count')} method-run tasks, and projects max alpha share {method_selection_alpha_expansion.get('projected_common_alpha_max_cell_share_after_next_batch')}",
        f"- Method selection alpha expansion execution: `{method_selection_alpha_expansion_execution.get('overall_status')}` active `{method_selection_alpha_expansion_execution.get('active_execution_status')}` reconciled `{method_selection_alpha_expansion_execution.get('reconciled_execution_status')}` with {method_selection_alpha_expansion_execution.get('completed_atomic_run_count')} / {method_selection_alpha_expansion_execution.get('expected_atomic_run_count')} completed rows; batch-label reconciliation `{method_selection_alpha_expansion_execution.get('batch_generation_label_reconciliation_status')}` historical `{method_selection_alpha_expansion_execution.get('batch_generation_label_historical_only')}` requires action `{method_selection_alpha_expansion_execution.get('batch_generation_label_requires_action')}` metadata `{method_selection_alpha_expansion_execution.get('execution_metadata_consistency_status')}`",
        f"- Method selection inferential audit: `{method_selection_inferential.get('overall_status')}` with primary `{method_selection_inferential.get('primary_candidate_method')}`, bootstrap selection rate {method_selection_inferential.get('bootstrap_primary_selection_rate')}, fresh-seed validation win rate {method_selection_inferential.get('post_selection_validation_primary_win_rate')}, main-result candidate win rate {method_selection_inferential.get('main_result_candidate_primary_win_rate')}, and claim status `{method_selection_inferential.get('claim_status')}`",
        f"- Manuscript readiness map: `{manuscript_readiness.get('overall_status')}` with {manuscript_readiness.get('blocked_gate_count')} / {manuscript_readiness.get('gate_count')} blocked gates and {manuscript_readiness.get('main_surface_blocked_count')} blocked main surfaces",
        f"- Bundle eligibility matrix: `{manuscript_bundle_eligibility.get('overall_status')}` with {manuscript_bundle_eligibility.get('robustness_candidate_count')} robustness candidates and {manuscript_bundle_eligibility.get('main_results_eligible_count')} main-result eligible rows",
        f"- Duplicate/content quarantine: `{duplicate_content_quarantine.get('overall_status')}` with {duplicate_content_quarantine.get('quarantined_action_count')} quarantined actions and {duplicate_content_quarantine.get('unquarantined_action_count')} unquarantined actions",
        f"- Venn-Abers negative-evidence disposition: `{venn_abers_negative_disposition.get('overall_status')}` with {venn_abers_negative_disposition.get('excluded_venn_abers_method_count')} excluded Venn-Abers methods, {venn_abers_negative_disposition.get('shortlist_venn_abers_method_count')} shortlist Venn-Abers methods, {venn_abers_negative_disposition.get('venn_bundle_row_count')} Venn-Abers bundle rows, and {venn_abers_negative_disposition.get('venn_bundle_main_eligible_count')} main-eligible Venn-Abers bundle rows",
        f"- Graph artifact readiness: `{graph_artifact.get('overall_status')}` over {graph_artifact.get('graph_count')} graph artifacts and {graph_artifact.get('total_edge_count_estimate')} estimated graph edges",
        f"- Paper gate protocol design bundle: `{paper_gate_protocol_design.get('overall_status')}` with {paper_gate_protocol_design.get('completed_protocol_design_action_count')} completed protocol-design actions and {paper_gate_protocol_design.get('downstream_action_count')} downstream actions exposed",
        f"- Paper gate closure execution plan: `{paper_gate_execution_plan.get('overall_status')}` with {paper_gate_execution_plan.get('action_count')} actions, {paper_gate_execution_plan.get('protocol_design_complete_action_count')} protocol-design complete actions, {paper_gate_execution_plan.get('empirical_execution_complete_action_count')} empirical-execution complete actions, {paper_gate_execution_plan.get('endpoint_natural_domain_audit_complete_action_count')} endpoint audit complete actions, {paper_gate_execution_plan.get('ready_action_count')} ready actions, {paper_gate_execution_plan.get('blocked_action_count')} blocked actions, bounded-support validity claim ready `{paper_gate_execution_plan.get('current_manuscript_bounded_support_validity_claim_ready')}`, and can close any positive gate now `{paper_gate_execution_plan.get('can_close_any_positive_gate_now')}`",
        f"- KG publication quality: `{kg_publication.get('overall_status')}` with {kg_publication.get('hard_failed_check_count')} hard failures and {kg_publication.get('polish_caveat_count')} polish caveats",
        f"- Scientific review findings: `{scientific_review.get('overall_status')}` with {scientific_review.get('open_blocker_count')} open blockers and {scientific_review.get('tracked_caveat_count')} tracked caveats",
        f"- Post-experiment publication activation: `{publication_activation.get('overall_status')}` with preparation authorized `{publication_activation.get('publication_preparation_authorized')}`, final drafting authorized `{publication_activation.get('manuscript_drafting_authorized')}`, blocked checks {publication_activation.get('blocked_check_count')}, and caveat checks {publication_activation.get('caveat_check_count')}",
        f"- Publication preparation packets: `{publication_preparation.get('overall_status')}` with reviewer packets {publication_preparation.get('reviewer_packet_count')} / {publication_preparation.get('required_reviewer_pass_count')}, visual/table candidate families {publication_preparation.get('visual_table_candidate_family_count')}, final drafting authorized `{publication_preparation.get('manuscript_drafting_authorized')}`, positive-claim publication ready `{publication_preparation.get('positive_claim_publication_ready')}`, and neutral no-method-promotion guard `{publication_preparation.get('neutral_no_method_promotion_guard_active')}`",
        f"- Reviewer design brief: `{reviewer_design.get('overall_status')}` phase `{reviewer_design.get('phase_state')}` with reviewer advice {reviewer_design.get('advice_record_count')} rows, reviewer coverage {reviewer_design.get('reviewer_count')} / {reviewer_design.get('required_reviewer_count')}, content matrix rows {reviewer_design.get('content_matrix_row_count')} / {reviewer_design.get('expected_visual_table_family_count')}, site deployment authorized `{reviewer_design.get('publication_site_deployment_authorized')}`, and positive-claim promotion authorized `{reviewer_design.get('positive_claim_promotion_authorized')}`",
        f"- Publication visual/table audit plan: `{visual_audit_plan.get('overall_status')}` phase `{visual_audit_plan.get('phase_state')}` with candidate artifacts {visual_audit_plan.get('candidate_artifact_count')} / {visual_audit_plan.get('expected_candidate_artifact_count')}, quality checks {visual_audit_plan.get('visual_table_quality_check_count')}, triptych components {visual_audit_plan.get('triptych_component_count')}, audit execution authorized `{visual_audit_plan.get('visual_table_audit_execution_authorized')}`, final retention authorized `{visual_audit_plan.get('final_visual_table_retention_authorized')}`, KG citable authorized `{visual_audit_plan.get('kg_citable_component_authorized')}`, and positive-claim promotion authorized `{visual_audit_plan.get('positive_claim_promotion_authorized')}`",
        f"- Visual/table pre-retention audit report: `{visual_table_audit_report.get('overall_status')}` phase `{visual_table_audit_report.get('phase_state')}` with audit rows {visual_table_audit_report.get('audit_row_count')} / {visual_table_audit_report.get('expected_candidate_artifact_count')}, source-traceable rows {visual_table_audit_report.get('source_traceable_candidate_count')}, iteration actions {visual_table_audit_report.get('iteration_action_count')}, rendered artifacts {visual_table_audit_report.get('rendered_artifact_count')}, final retained artifacts {visual_table_audit_report.get('final_retained_artifact_count')}, final retention authorized `{visual_table_audit_report.get('final_visual_table_retention_authorized')}`, KG citable authorized `{visual_table_audit_report.get('kg_citable_component_authorized')}`, and positive-claim promotion authorized `{visual_table_audit_report.get('positive_claim_promotion_authorized')}`",
        f"- Visual/table draft render candidate audit: `{visual_table_render_candidate_audit.get('overall_status')}` phase `{visual_table_render_candidate_audit.get('phase_state')}` with draft candidates {visual_table_render_candidate_audit.get('candidate_row_count')}, rendered draft artifacts {visual_table_render_candidate_audit.get('rendered_draft_artifact_count')}, layout pass/revise {visual_table_render_candidate_audit.get('layout_pass_count')} / {visual_table_render_candidate_audit.get('layout_revise_count')}, SVG text-overlap detections {visual_table_render_candidate_audit.get('svg_static_text_overlap_detected_count')}, final retained artifacts {visual_table_render_candidate_audit.get('final_retained_artifact_count')}, final retention authorized `{visual_table_render_candidate_audit.get('final_visual_table_retention_authorized')}`, and positive-claim promotion authorized `{visual_table_render_candidate_audit.get('positive_claim_promotion_authorized')}`",
        f"- Publication retention-readiness audit: `{publication_retention_readiness.get('overall_status')}` phase `{publication_retention_readiness.get('phase_state')}` with recommendations {publication_retention_readiness.get('recommendation_row_count')} / {publication_retention_readiness.get('render_candidate_count')}, surface counts `{publication_retention_readiness.get('recommended_surface_counts')}`, retention complete `{publication_retention_readiness.get('retention_recommendation_complete')}`, final retention authorized `{publication_retention_readiness.get('final_visual_table_retention_authorized')}`, final prose permission `{publication_retention_readiness.get('final_manuscript_prose_permission')}`, and positive-claim promotion authorized `{publication_retention_readiness.get('positive_claim_promotion_authorized')}`",
        f"- Final publication visual auditor readiness: `{final_visual_auditor.get('overall_status')}` phase `{final_visual_auditor.get('phase_state')}` with feedback rows {final_visual_auditor.get('feedback_ready_row_count')} / {final_visual_auditor.get('feedback_row_count')}, feedback items {final_visual_auditor.get('feedback_item_count')}, missing rendered artifacts {final_visual_auditor.get('missing_rendered_artifact_count')}, final retention authorized `{final_visual_auditor.get('final_visual_table_retention_authorized')}`, final prose permission `{final_visual_auditor.get('final_manuscript_prose_permission')}`, and positive-claim promotion authorized `{final_visual_auditor.get('positive_claim_promotion_authorized')}`",
        f"- Neutral result ledger: `{neutral_result_ledger.get('overall_status')}` with {neutral_result_ledger.get('row_count')} source-traceable result rows, missing sources {neutral_result_ledger.get('missing_source_artifact_count')}, positive-claim promotions {neutral_result_ledger.get('positive_claim_promotion_authorized_count')}, final method-selection authorizations {neutral_result_ledger.get('final_method_selection_authorized_count')}, final prose permissions {neutral_result_ledger.get('final_manuscript_prose_permission_count')}, CQR descriptive candidate recorded `{neutral_result_ledger.get('cqr_descriptive_candidate_recorded')}`, and Venn-Abers negative result recorded `{neutral_result_ledger.get('venn_abers_negative_result_recorded')}`",
        f"- Article/supplement blueprint alignment: `{article_supplement_blueprint_alignment.get('overall_status')}` phase `{article_supplement_blueprint_alignment.get('phase_state')}` with alignment rows {article_supplement_blueprint_alignment.get('alignment_row_count')}, surface rows {article_supplement_blueprint_alignment.get('surface_row_count')}, reviewer-alignment issues {article_supplement_blueprint_alignment.get('reviewer_alignment_issue_count')}, missing sources {article_supplement_blueprint_alignment.get('missing_source_artifact_count')}, Venn-Abers negative/no validated claim `{article_supplement_blueprint_alignment.get('venn_abers_negative_no_validated_claim')}`, CQR/CV+ reporting role `{article_supplement_blueprint_alignment.get('cqr_cvplus_reporting_role')}`, final prose permission `{article_supplement_blueprint_alignment.get('final_manuscript_prose_permission')}`, method recommendation authorized `{article_supplement_blueprint_alignment.get('method_recommendation_authorized')}`, and positive-claim promotion authorized `{article_supplement_blueprint_alignment.get('positive_claim_promotion_authorized')}`",
        f"- Publication release-gap register: `{publication_release_gap.get('overall_status')}` phase `{publication_release_gap.get('phase_state')}` with deliverable rows {publication_release_gap.get('deliverable_row_count')}, pre-prose evidence-ready rows {publication_release_gap.get('pre_prose_evidence_ready_row_count')}, release-authorized rows {publication_release_gap.get('release_authorized_count')}, blocked release rows {publication_release_gap.get('blocked_release_row_count')}, source-traceable rows {publication_release_gap.get('source_traceable_row_count')}, goal complete `{publication_release_gap.get('goal_can_mark_complete')}`, paper blocked gates {publication_release_gap.get('paper_blocked_gate_count')}, final prose permission `{publication_release_gap.get('final_manuscript_prose_permission')}`, sterile repository creation authorized `{publication_release_gap.get('sterile_repository_creation_authorized')}`, method recommendation authorized `{publication_release_gap.get('method_recommendation_authorized')}`, positive-claim promotion authorized `{publication_release_gap.get('positive_claim_promotion_authorized')}`, and working repository final-citable `{publication_release_gap.get('working_repository_final_citable')}`",
        f"- Individual experiment report blueprint: `{individual_experiment_report_blueprint.get('overall_status')}` phase `{individual_experiment_report_blueprint.get('phase_state')}` with author `{individual_experiment_report_blueprint.get('author_header')}`, section rows {individual_experiment_report_blueprint.get('section_row_count')}, source-traceable rows {individual_experiment_report_blueprint.get('source_traceable_row_count')}, final prose permission `{individual_experiment_report_blueprint.get('final_report_prose_permission')}`, release authorized `{individual_experiment_report_blueprint.get('release_authorized')}`, CQR reporting role `{individual_experiment_report_blueprint.get('cqr_reporting_role')}`, Venn-Abers reporting role `{individual_experiment_report_blueprint.get('venn_abers_reporting_role')}`, method recommendation authorized `{individual_experiment_report_blueprint.get('method_recommendation_authorized')}`, and positive-claim promotion authorized `{individual_experiment_report_blueprint.get('positive_claim_promotion_authorized')}`",
        f"- Claim-safe result extraction matrix: `{claim_safe_result_extraction_matrix.get('overall_status')}` phase `{claim_safe_result_extraction_matrix.get('phase_state')}` with surface rows {claim_safe_result_extraction_matrix.get('surface_row_count')}, safe pre-prose candidates {claim_safe_result_extraction_matrix.get('safe_pre_prose_extraction_candidate_count')}, blocked positive surfaces {claim_safe_result_extraction_matrix.get('blocked_positive_surface_count')}, main-results status `{claim_safe_result_extraction_matrix.get('main_results_surface_status')}`, negative-results status `{claim_safe_result_extraction_matrix.get('negative_results_surface_status')}`, final prose permission `{claim_safe_result_extraction_matrix.get('final_manuscript_prose_permission')}`, method recommendation authorized `{claim_safe_result_extraction_matrix.get('method_recommendation_authorized')}`, and positive-claim promotion authorized `{claim_safe_result_extraction_matrix.get('positive_claim_promotion_authorized')}`",
        f"- Manuscript section evidence packet: `{manuscript_section_evidence_packet.get('overall_status')}` phase `{manuscript_section_evidence_packet.get('phase_state')}` with section packets {manuscript_section_evidence_packet.get('section_packet_row_count')}, safe pre-prose packets {manuscript_section_evidence_packet.get('safe_pre_prose_evidence_packet_count')}, blocked positive packets {manuscript_section_evidence_packet.get('blocked_positive_packet_count')}, main-results packet `{manuscript_section_evidence_packet.get('main_results_packet_status')}`, negative packet `{manuscript_section_evidence_packet.get('negative_packet_status')}`, final section prose authorized `{manuscript_section_evidence_packet.get('final_section_prose_authorized')}`, method recommendation authorized `{manuscript_section_evidence_packet.get('method_recommendation_authorized')}`, and positive-claim promotion authorized `{manuscript_section_evidence_packet.get('positive_claim_promotion_authorized')}`",
        f"- Section claim-boundary audit: `{section_claim_boundary_audit.get('overall_status')}` phase `{section_claim_boundary_audit.get('phase_state')}` with boundary rows {section_claim_boundary_audit.get('boundary_row_count')}, complete boundaries {section_claim_boundary_audit.get('boundary_complete_row_count')}, section boundary backfill rows {section_claim_boundary_audit.get('section_boundary_backfill_row_count')}, release-authorized targets {section_claim_boundary_audit.get('release_authorized_target_count')}, main positive boundary blocked `{section_claim_boundary_audit.get('main_results_positive_boundary_blocked')}`, Venn-Abers negative boundary preserved `{section_claim_boundary_audit.get('venn_abers_negative_boundary_preserved')}`, method recommendation authorized `{section_claim_boundary_audit.get('method_recommendation_authorized')}`, and positive-claim promotion authorized `{section_claim_boundary_audit.get('positive_claim_promotion_authorized')}`",
        f"- Article/supplement/KG navigation index: `{article_supplement_kg_navigation_index.get('overall_status')}` phase `{article_supplement_kg_navigation_index.get('phase_state')}` with navigation rows {article_supplement_kg_navigation_index.get('navigation_row_count')}, section rows {article_supplement_kg_navigation_index.get('section_navigation_row_count')}, KG/site rows {article_supplement_kg_navigation_index.get('kg_site_navigation_row_count')}, visual/table candidates {article_supplement_kg_navigation_index.get('visual_table_candidate_index_row_count')}, KG reference issues {article_supplement_kg_navigation_index.get('kg_node_reference_issue_count')}, release-authorized targets {article_supplement_kg_navigation_index.get('release_authorized_target_count')}, main positive boundary blocked `{article_supplement_kg_navigation_index.get('main_results_positive_boundary_blocked')}`, Venn-Abers negative boundary preserved `{article_supplement_kg_navigation_index.get('venn_abers_negative_boundary_preserved')}`, method recommendation authorized `{article_supplement_kg_navigation_index.get('method_recommendation_authorized')}`, and positive-claim promotion authorized `{article_supplement_kg_navigation_index.get('positive_claim_promotion_authorized')}`",
        f"- Publication phase progress reconciliation: `{publication_phase_progress_reconciliation.get('overall_status')}` phase `{publication_phase_progress_reconciliation.get('phase_state')}` with pre-prose controls {publication_phase_progress_reconciliation.get('pre_prose_completed_control_count')} / {publication_phase_progress_reconciliation.get('pre_prose_control_count')}, resolved prior blockers {publication_phase_progress_reconciliation.get('resolved_prior_blocker_count')}, active final blockers {publication_phase_progress_reconciliation.get('active_final_blocker_count')}, stale goal blockers {publication_phase_progress_reconciliation.get('stale_goal_blocker_count')}, final visual auditor `{publication_phase_progress_reconciliation.get('final_publication_visual_auditor_status')}`, main positive boundary blocked `{publication_phase_progress_reconciliation.get('main_results_positive_boundary_blocked')}`, Venn-Abers negative boundary preserved `{publication_phase_progress_reconciliation.get('venn_abers_negative_boundary_preserved')}`, method recommendation authorized `{publication_phase_progress_reconciliation.get('method_recommendation_authorized')}`, and positive-claim promotion authorized `{publication_phase_progress_reconciliation.get('positive_claim_promotion_authorized')}`",
        f"- Neutral reporting language audit: `{neutral_reporting_language.get('overall_status')}` with {neutral_reporting_language.get('term_hit_count')} promotional/positive-claim term hits, {neutral_reporting_language.get('guarded_hit_count')} guarded hits, {neutral_reporting_language.get('unguarded_hit_count')} unguarded hits, and {neutral_reporting_language.get('failed_check_count')} failed checks",
        f"- Scientific neutrality interpretation lock: `{scientific_neutrality_interpretation_lock.get('overall_status')}` phase `{scientific_neutrality_interpretation_lock.get('phase_state')}` with {scientific_neutrality_interpretation_lock.get('interpretation_row_count')} interpretation rows, CQR/CV+ role `{scientific_neutrality_interpretation_lock.get('cqr_cvplus_reporting_role')}`, Venn-Abers role `{scientific_neutrality_interpretation_lock.get('venn_abers_reporting_role')}`, result reporting policy `{scientific_neutrality_interpretation_lock.get('result_reporting_policy')}`, champion method authorized `{scientific_neutrality_interpretation_lock.get('method_champion_authorized')}`, method recommendation authorized `{scientific_neutrality_interpretation_lock.get('method_recommendation_authorized')}`, positive-claim promotion authorized `{scientific_neutrality_interpretation_lock.get('positive_claim_promotion_authorized')}`, and final prose permission `{scientific_neutrality_interpretation_lock.get('final_manuscript_prose_permission')}`",
        f"- Final publication output authorization protocol: `{final_output_authorization_protocol.get('overall_status')}` phase `{final_output_authorization_protocol.get('phase_state')}` with authorization rows {final_output_authorization_protocol.get('blocked_authorization_row_count')} / {final_output_authorization_protocol.get('authorization_row_count')} blocked, ready-to-authorize outputs {final_output_authorization_protocol.get('ready_to_authorize_output_count')}, active final blockers {final_output_authorization_protocol.get('active_final_blocker_count')}, paper blocked gates {final_output_authorization_protocol.get('paper_blocked_gate_count')}, result reporting policy `{final_output_authorization_protocol.get('result_reporting_policy')}`, champion method authorized `{final_output_authorization_protocol.get('method_champion_authorized')}`, method recommendation authorized `{final_output_authorization_protocol.get('method_recommendation_authorized')}`, positive-claim promotion authorized `{final_output_authorization_protocol.get('positive_claim_promotion_authorized')}`, final prose permission `{final_output_authorization_protocol.get('final_manuscript_prose_permission')}`, and failed checks {final_output_authorization_protocol.get('failed_check_count')}",
        f"- Publication claim/evidence verification matrix: `{publication_claim_evidence_verification.get('overall_status')}` phase `{publication_claim_evidence_verification.get('phase_state')}` with verification rows {publication_claim_evidence_verification.get('verification_pass_count')} / {publication_claim_evidence_verification.get('verification_row_count')} passing, boundary/navigation aligned rows {publication_claim_evidence_verification.get('boundary_aligned_row_count')} / {publication_claim_evidence_verification.get('navigation_aligned_row_count')}, KG reference issues {publication_claim_evidence_verification.get('kg_reference_issue_count')}, safe pre-prose rows {publication_claim_evidence_verification.get('safe_pre_prose_evidence_row_count')}, blocked positive rows {publication_claim_evidence_verification.get('blocked_positive_row_count')}, Venn-Abers negative-ready rows {publication_claim_evidence_verification.get('venn_abers_negative_ready_row_count')}, result reporting policy `{publication_claim_evidence_verification.get('result_reporting_policy')}`, champion method authorized `{publication_claim_evidence_verification.get('method_champion_authorized')}`, method recommendation authorized `{publication_claim_evidence_verification.get('method_recommendation_authorized')}`, positive-claim promotion authorized `{publication_claim_evidence_verification.get('positive_claim_promotion_authorized')}`, and failed checks {publication_claim_evidence_verification.get('failed_check_count')}",
        f"- Sterile repository staging manifest: `{sterile_repository_staging_manifest.get('overall_status')}` phase `{sterile_repository_staging_manifest.get('phase_state')}` with required content rows {sterile_repository_staging_manifest.get('required_content_traceable_count')} / {sterile_repository_staging_manifest.get('required_content_row_count')} traceable, exclusion policy rows {sterile_repository_staging_manifest.get('exclusion_source_traceable_count')} / {sterile_repository_staging_manifest.get('exclusion_policy_row_count')} traceable, candidate inclusion risk hits {sterile_repository_staging_manifest.get('candidate_inclusion_risk_hit_count')}, result reporting policy `{sterile_repository_staging_manifest.get('result_reporting_policy')}`, champion method authorized `{sterile_repository_staging_manifest.get('method_champion_authorized')}`, private repository created `{sterile_repository_staging_manifest.get('private_repository_created')}`, sterile creation authorized `{sterile_repository_staging_manifest.get('sterile_repository_creation_authorized')}`, release authorized `{sterile_repository_staging_manifest.get('release_authorized')}`, working repository final-citable `{sterile_repository_staging_manifest.get('working_repository_final_citable')}`, and failed checks {sterile_repository_staging_manifest.get('failed_check_count')}",
        f"- Neutral experiment closure audit: `{neutral_experiment_closure.get('overall_status')}` with neutral closure ready `{neutral_experiment_closure.get('neutral_closure_ready')}`, goal-policy update required `{neutral_experiment_closure.get('goal_policy_update_required')}`, final dispositions {neutral_experiment_closure.get('final_disposition_gate_count')} / {neutral_experiment_closure.get('gate_count')}, and publication preparation authorized `{neutral_experiment_closure.get('publication_preparation_authorized')}`",
        f"- Goal completion audit: `{goal_completion.get('overall_status')}` with neutral empirical phase complete `{goal_completion.get('neutral_empirical_phase_complete')}`, empirical policy `{goal_completion.get('empirical_completion_policy')}`, {goal_completion.get('complete_or_scoped_requirement_count')} / {goal_completion.get('requirement_count')} requirements complete-or-scoped, {goal_completion.get('blocked_positive_claim_requirement_count')} blocked positive-claim requirements, {goal_completion.get('positive_claim_blocking_gate_count')} positive-claim blocking gates, {goal_completion.get('planned_deferred_requirement_count')} planned-deferred requirements, {goal_completion.get('in_progress_requirement_count')} in-progress requirements, can mark full goal complete `{goal_completion.get('can_mark_goal_complete')}`, and publication preparation `{goal_completion.get('can_start_post_experiment_publication_preparation')}`",
        f"- KG nodes/edges: {kg.get('node_count')} / {kg.get('edge_count')}",
        f"- KG edge/node ratio: {kg.get('edge_node_ratio')}",
        f"- KG provenance/confidence coverage: {kg.get('edge_provenance_coverage')} / {kg.get('edge_confidence_coverage')}",
        f"- KG specific provenance/confidence-reason coverage: {kg.get('specific_edge_provenance_coverage')} / {kg.get('edge_confidence_reason_coverage')}",
        f"- KG selector provenance/calibrated confidence levels: {kg.get('edge_selector_provenance_coverage')} / {kg.get('distinct_edge_confidence_value_count')}",
        f"- KG claim-edge selector provenance: {kg.get('claim_edge_selector_provenance_coverage')} with {kg.get('claim_edge_missing_selector_count')} missing selectors over {kg.get('claim_edge_count')} claim edges",
        f"- KG weak-provenance confidence=1 edges: {kg.get('weak_provenance_confidence_one_count')}",
        f"- KG isolated nodes: {kg.get('isolated_node_count')}",
        f"- KG observation/node ratio: {kg.get('observation_node_ratio')} total, {kg.get('paper_evidence_observation_node_ratio')} paper-evidence",
        f"- KG endpoint result/caveat nodes: {kg.get('endpoint_result_count')} / {kg.get('endpoint_caveat_count')}",
        f"- KG endpoint config linkage: `{(kg.get('endpoint_result_relation_coverage') or {}).get('SUMMARIZES_CONFIG')}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Steps",
            "",
            "| Step | Family | Status | Seconds | Outputs present |",
            "| --- | --- | --- | ---: | --- |",
        ]
    )
    for step in payload["steps"]:
        lines.append(
            "| "
            f"`{step['step_id']}` | "
            f"{step['family']} | "
            f"`{step['status']}` | "
            f"{step['duration_seconds']} | "
            f"`{step['outputs']['all_present']}` |"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_gate(out_path: Path, payload: dict[str, Any]) -> None:
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = resolve(root, args.out)
    pre_run_dirty = dirty_snapshot(root)
    git_commit = current_commit(root)

    if args.summary_only:
        step_results, complete = existing_step_results_for_summary(out_path)
        payload = gate_payload(
            root=root,
            step_results=step_results,
            complete=complete,
            pre_run_dirty=pre_run_dirty,
            git_commit=git_commit,
        )
        write_gate(out_path, payload)
        print(
            json.dumps(
                {
                    "mode": "summary_only",
                    "status": (
                        "ok"
                        if payload["summary"]["overall_status"] != "fail"
                        else "fail"
                    ),
                    "out": rel(out_path, root),
                    **payload["summary"],
                },
                sort_keys=True,
            )
        )
        return 1 if payload["summary"]["overall_status"] == "fail" else 0

    step_results: list[dict[str, Any]] = []
    write_gate(
        out_path,
        gate_payload(
            root=root,
            step_results=step_results,
            complete=False,
            pre_run_dirty=pre_run_dirty,
            git_commit=git_commit,
        ),
    )
    for step in STEPS:
        result = run_step(step, root)
        step_results.append(result)
        write_gate(
            out_path,
            gate_payload(
                root=root,
                step_results=step_results,
                complete=False,
                pre_run_dirty=pre_run_dirty,
                git_commit=git_commit,
            ),
        )
        if result["status"] != "pass" and step.required and args.stop_on_failure:
            break
    payload = gate_payload(
        root=root,
        step_results=step_results,
        complete=len(step_results) == len(STEPS),
        pre_run_dirty=pre_run_dirty,
        git_commit=git_commit,
    )
    write_gate(out_path, payload)
    print(
        json.dumps(
            {
                "status": (
                    "ok" if payload["summary"]["overall_status"] != "fail" else "fail"
                ),
                "out": rel(out_path, root),
                **payload["summary"],
            },
            sort_keys=True,
        )
    )
    return 1 if payload["summary"]["overall_status"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
