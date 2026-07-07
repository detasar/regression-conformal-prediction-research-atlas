"""Build an executable register for external scientific-review findings.

The register records which parallel KG/methodology-audit findings are closed,
which remain tracked caveats, and which would block paper extraction. It is
not a result table and does not promote final empirical claims.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts import audit_methodology_sanity as sanity
from experiments.regression.scripts import audit_venn_abers_validation_readiness as va_audit
from experiments.regression.scripts import run_regression_pilot as pilot
from experiments.regression.scripts import run_retrospective_quality_gate as gate


SCHEMA = "cpfi_regression_scientific_review_finding_register_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = REPORT_DIR / "scientific_review_finding_register.json"
KG_QUALITY = Path("experiments/regression/reports/knowledge_graph_quality/quality_summary.json")
RETROSPECTIVE_GATE = REPORT_DIR / "retrospective_quality_gate.json"


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


def retrospective_dirty_snapshot_for_review(root: Path) -> dict[str, Any]:
    """Use the gate's pre-run dirty snapshot when the register runs inside it."""
    gate_payload = read_json(root / RETROSPECTIVE_GATE)
    pre_run_dirty = gate_payload.get("pre_run_git_dirty")
    if isinstance(pre_run_dirty, dict) and pre_run_dirty.get("schema"):
        snapshot = dict(pre_run_dirty)
        snapshot["snapshot_source"] = "retrospective_quality_gate_pre_run_git_dirty"
        return snapshot
    snapshot = gate.dirty_snapshot(root)
    snapshot["snapshot_source"] = "live_scientific_review_register_git_dirty"
    return snapshot


def safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def count_by_field(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "missing")
        counts[key] = counts.get(key, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def venn_abers_run_undercoverage(root: Path, readiness: dict[str, Any]) -> dict[str, Any]:
    recorded = readiness.get("run_undercoverage")
    if isinstance(recorded, dict) and recorded.get("run_count") is not None:
        return recorded
    runs = [
        row
        for panel in readiness.get("validation_panels") or []
        for row in va_audit.diagnostic_run_rows(
            str(panel.get("report_id")),
            str(panel.get("role") or "diagnostic"),
            Path(str(panel.get("path") or "")),
            read_json(resolve(root, panel["path"])) if panel.get("path") else {},
        )
    ]
    return va_audit.run_undercoverage_summary(runs)


def add_finding(
    rows: list[dict[str, Any]],
    *,
    finding_id: str,
    source_audit: str,
    severity: str,
    status: str,
    title: str,
    evidence: list[str],
    observed: dict[str, Any],
    closure_standard: str,
    next_action: str,
    claim_boundary: str,
) -> None:
    rows.append(
        {
            "finding_id": finding_id,
            "source_audit": source_audit,
            "severity": severity,
            "status": status,
            "title": title,
            "evidence": evidence,
            "observed": observed,
            "closure_standard": closure_standard,
            "next_action": next_action,
            "claim_boundary": claim_boundary,
        }
    )


def status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status"))
        counts[status] = counts.get(status, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def validate_runner_cache_contract() -> dict[str, Any]:
    default_resume = pilot.allows_legacy_run_id_resume(
        {"splits": {"train": 0.6, "calibration": 0.2}}
    )
    explicit_resume = pilot.allows_legacy_run_id_resume(
        {
            "splits": {"train": 0.6, "calibration": 0.2},
            "resume": {"allow_legacy_run_id_v1": True},
        }
    )
    frame = pd.DataFrame(
        {"x": [0.0, 1.0, 2.0], "group": ["a", "b", "a"], "target": [1.0, 2.0, 3.0]}
    )
    changed = frame.copy()
    changed.loc[2, "x"] = 20.0
    code_provenance = {"schema": "test_runtime", "git_commit": "abc", "git_dirty": False}
    config = {"splits": {"train": 0.6, "calibration": 0.2}}
    base_payload = pilot.prediction_artifact_payload(
        "synthetic_regression",
        "target",
        "group",
        "ridge",
        "linear",
        {"alpha": 1.0},
        17,
        config,
        data_provenance={
            "schema": "cpfi_regression_data_provenance_v1",
            "frame_fingerprint": pilot.dataframe_fingerprint(frame),
        },
        code_provenance=code_provenance,
    )
    changed_payload = pilot.prediction_artifact_payload(
        "synthetic_regression",
        "target",
        "group",
        "ridge",
        "linear",
        {"alpha": 1.0},
        17,
        config,
        data_provenance={
            "schema": "cpfi_regression_data_provenance_v1",
            "frame_fingerprint": pilot.dataframe_fingerprint(changed),
        },
        code_provenance=code_provenance,
    )
    return {
        "legacy_resume_default": default_resume,
        "legacy_resume_explicit_migration": explicit_resume,
        "cache_payload_has_data_provenance": isinstance(
            base_payload.get("data_provenance"), dict
        ),
        "cache_payload_has_code_provenance": isinstance(
            base_payload.get("code_provenance"), dict
        ),
        "frame_fingerprint_changes_cache_key": (
            pilot.stable_run_id(base_payload) != pilot.stable_run_id(changed_payload)
        ),
    }


def build_payload(root: Path) -> dict[str, Any]:
    kg = read_json(root / KG_QUALITY)
    kg_publication = read_json(root / REPORT_DIR / "kg_publication_quality_audit.json")
    cross_run = read_json(root / REPORT_DIR / "cross_run_integrity_audit.json")
    publication = read_json(root / REPORT_DIR / "publication_methodology_audit.json")
    final_selection = read_json(root / REPORT_DIR / "final_selection_claim_boundary_audit.json")
    duplicate = read_json(root / REPORT_DIR / "duplicate_sensitivity_closure_audit.json")
    duplicate_quarantine = read_json(
        root / REPORT_DIR / "duplicate_content_quarantine_audit.json"
    )
    feature_triage = read_json(
        root / REPORT_DIR / "feature_leakage_metadata_completeness_triage.json"
    )
    venn_abers = read_json(root / REPORT_DIR / "venn_abers_validation_readiness_audit.json")
    venn_abers_grid_ivapd = read_json(
        root / REPORT_DIR / "venn_abers_grid_ivapd_validation_protocol.json"
    )
    venn_abers_negative_disposition = read_json(
        root / REPORT_DIR / "venn_abers_negative_evidence_disposition_audit.json"
    )
    venn_abers_grid_expansion = read_json(
        root / REPORT_DIR / "venn_abers_grid_expansion_plan.json"
    )
    bounded_protocol = read_json(root / "experiments/regression/manuscript/bounded_support_protocol.json")
    bounded_posthandling = read_json(root / "experiments/regression/manuscript/bounded_support_posthandling_validation.json")
    bounded_dataset = read_json(root / "experiments/regression/manuscript/bounded_support_dataset_audit.json")

    kg_trace = kg.get("traceability") or {}
    kg_obs = kg.get("observations") or {}
    kg_pub_summary = kg_publication.get("summary") or {}
    cross_summary = cross_run.get("summary") or {}
    publication_summary = publication.get("summary") or {}
    final_summary = final_selection.get("summary") or {}
    duplicate_summary = duplicate.get("summary") or {}
    duplicate_quarantine_summary = duplicate_quarantine.get("summary") or {}
    duplicate_covered_action_status_counts = count_by_field(
        duplicate.get("covered_actions") or [], "status"
    )
    duplicate_tracked_caveat_status_counts = count_by_field(
        duplicate.get("tracked_caveat_actions") or [], "status"
    )
    feature_summary = feature_triage.get("summary") or {}
    venn_summary = venn_abers.get("summary") or {}
    venn_grid_ivapd_summary = venn_abers_grid_ivapd.get("summary") or {}
    venn_negative_disposition_summary = (
        venn_abers_negative_disposition.get("summary") or {}
    )
    venn_grid_expansion_summary = venn_abers_grid_expansion.get("summary") or {}
    venn_run_summary = venn_abers_run_undercoverage(root, venn_abers)
    bounded_summary = bounded_protocol.get("summary") or {}
    posthandling_summary = bounded_posthandling.get("summary") or {}
    bounded_dataset_summary = bounded_dataset.get("summary") or {}
    runner_contract = validate_runner_cache_contract()
    dirty_snapshot = retrospective_dirty_snapshot_for_review(root)
    dirty_snapshot_has_hash = (
        "diff_name_status_sha256" in dirty_snapshot and "dirty_path_count" in dirty_snapshot
    )
    dirty_snapshot_status = (
        "tracked_caveat"
        if dirty_snapshot_has_hash and dirty_snapshot.get("is_dirty")
        else "closed"
        if dirty_snapshot_has_hash
        else "open_blocker"
    )
    claim_flags = {
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
    }
    final_claims_blocked = all(value is False for value in claim_flags.values()) and (
        final_summary.get("claim_status") == "blocked"
    )
    feature_selection_counts = cross_summary.get("feature_metadata_selection_counts") or {}
    feature_policy_counts = cross_summary.get("feature_policy_inference_counts") or {}
    feature_not_recorded = safe_int(feature_selection_counts.get("not_recorded"))
    feature_policy_not_recorded = safe_int(feature_policy_counts.get("not_recorded"))
    feature_hard_violations = safe_int(
        feature_summary.get("hard_feature_leakage_violation_row_count")
    )
    feature_guard_ok = feature_summary.get("runner_feature_drop_guard_ok") is True
    manuscript_scan_in_scope = (
        "experiments/regression/manuscript" in sanity.UNSUPPORTED_CLAIM_SCAN_ROOTS
    )
    duplicate_quarantine_closed = (
        safe_int(duplicate_summary.get("open_action_count")) == 0
        and safe_int(duplicate_summary.get("hard_failed_check_count")) == 0
        and duplicate_quarantine_summary.get("overall_status")
        == "duplicate_content_quarantine_pass"
        and safe_int(duplicate_quarantine_summary.get("failed_check_count")) == 0
        and safe_int(
            duplicate_quarantine_summary.get("unquarantined_action_count")
        )
        == 0
        and safe_int(
            duplicate_quarantine_summary.get("main_results_eligible_action_count")
        )
        == 0
        and safe_int(
            duplicate_quarantine_summary.get("caveat_label_missing_action_count")
        )
        == 0
        and safe_int(
            duplicate_quarantine_summary.get("linked_final_claim_action_count")
        )
        == 0
    )

    rows: list[dict[str, Any]] = []
    selector_coverage = float(kg_trace.get("edge_selector_provenance_coverage") or 0.0)
    selector_threshold = float(
        (kg.get("metadata") or {})
        .get("thresholds", {})
        .get("min_edge_selector_provenance_coverage", 0.80)
    )
    selector_status = (
        "closed"
        if selector_coverage == 1.0
        else "tracked_caveat"
        if selector_coverage >= selector_threshold
        else "open_blocker"
    )

    add_finding(
        rows,
        finding_id="kg_edge_confidence_calibration",
        source_audit="parallel_kg_audit",
        severity="high",
        status=(
            "closed"
            if int(kg_trace.get("distinct_edge_confidence_value_count") or 0) >= 3
            and int(kg_trace.get("weak_provenance_confidence_one_count") or 0) == 0
            else "open_blocker"
        ),
        title="KG edge confidence must be calibrated, not universal.",
        evidence=[rel(root / KG_QUALITY, root)],
        observed={
            "distinct_edge_confidence_value_count": kg_trace.get(
                "distinct_edge_confidence_value_count"
            ),
            "average_edge_confidence": kg_trace.get("average_edge_confidence"),
            "weak_provenance_confidence_one_count": kg_trace.get(
                "weak_provenance_confidence_one_count"
            ),
        },
        closure_standard="At least three confidence levels and zero weak-provenance confidence=1 edges.",
        next_action="Keep confidence as a traceability score, not empirical certainty.",
        claim_boundary="KG confidence is evidence-traceability confidence only.",
    )
    add_finding(
        rows,
        finding_id="kg_fact_level_selector_provenance",
        source_audit="parallel_kg_audit",
        severity="high",
        status=selector_status,
        title="KG needs selector provenance, not only path-level provenance.",
        evidence=[rel(root / KG_QUALITY, root)],
        observed={
            "edge_selector_provenance_coverage": selector_coverage,
            "threshold": selector_threshold,
            "specific_edge_provenance_coverage": kg_trace.get(
                "specific_edge_provenance_coverage"
            ),
            "provenance_granularity_counts": kg_trace.get(
                "provenance_granularity_counts"
            ),
        },
        closure_standard=(
            "Selector provenance reaches the current quality threshold; full "
            "closure requires 1.0 selector coverage from fact selectors or "
            "explicit artifact-root selectors for whole-artifact relations."
        ),
        next_action=(
            "Prefer fact selectors in manuscript-cited edges; use artifact-root "
            "selectors only when the relation is supported by the whole artifact."
        ),
        claim_boundary=(
            "Artifact-root selectors prove artifact-level traceability; they are "
            "not interchangeable with quoted paper facts."
        ),
    )
    add_finding(
        rows,
        finding_id="kg_multiplicity_provenance",
        source_audit="parallel_kg_audit",
        severity="high",
        status=(
            "closed"
            if int(kg_trace.get("high_multiplicity_edges_without_evidence_samples_count") or 0)
            == 0
            else "open_blocker"
        ),
        title="Collapsed KG edge multiplicity must preserve contributing evidence samples.",
        evidence=[rel(root / KG_QUALITY, root), rel(root / "experiments/regression/catalogs/knowledge_graph.json", root)],
        observed={
            "multiplicity_edge_count": kg_trace.get("multiplicity_edge_count"),
            "missing_evidence_samples": kg_trace.get(
                "high_multiplicity_edges_without_evidence_samples_count"
            ),
        },
        closure_standard="Zero high-multiplicity edges without bounded evidence samples.",
        next_action="Use multiplicity samples to drill into repeated relations rather than treating multiplicity as proof.",
        claim_boundary="Multiplicity counts repetition, not independent statistical evidence.",
    )
    add_finding(
        rows,
        finding_id="kg_topology_vs_paper_observations",
        source_audit="parallel_kg_audit",
        severity="medium",
        status=(
            "closed"
            if float(kg_obs.get("paper_evidence_observation_node_ratio") or 0.0) >= 1.0
            and int(kg_obs.get("topology_observation_count") or 0) > 0
            else "open_blocker"
        ),
        title="Topology observations must not inflate paper evidence counts.",
        evidence=[rel(root / KG_QUALITY, root)],
        observed={
            "total_observation_count": kg_obs.get("total_observation_count"),
            "topology_observation_count": kg_obs.get("topology_observation_count"),
            "paper_evidence_observation_node_ratio": kg_obs.get(
                "paper_evidence_observation_node_ratio"
            ),
        },
        closure_standard="Topology observations are counted separately and paper-evidence observation/node ratio is at least 1.0.",
        next_action="When writing the paper, prefer non-topology observations and source artifacts.",
        claim_boundary="Navigation observations do not support scientific claims.",
    )
    add_finding(
        rows,
        finding_id="kg_publication_freeze",
        source_audit="parallel_kg_audit",
        severity="medium",
        status=(
            "closed"
            if kg_pub_summary.get("overall_status") == "kg_publication_ready"
            else "tracked_caveat"
            if kg_pub_summary.get("overall_status") == "kg_publication_ready_with_polish_caveats"
            else "open_blocker"
        ),
        title="KG publication readiness must distinguish regenerated artifacts from frozen evidence.",
        evidence=[rel(root / REPORT_DIR / "kg_publication_quality_audit.json", root)],
        observed={
            "overall_status": kg_pub_summary.get("overall_status"),
            "polish_caveat_count": kg_pub_summary.get("polish_caveat_count"),
            "audit_time_relevant_modified_source_count": kg_pub_summary.get(
                "relevant_modified_source_count"
            ),
            "publication_freeze_snapshot_source": kg_pub_summary.get(
                "publication_freeze_snapshot_source"
            ),
            "publication_freeze_relevant_dirty_source_count": kg_pub_summary.get(
                "publication_freeze_relevant_dirty_source_count"
            ),
        },
        closure_standard="No hard failures; publication freeze is closed only when the audit has a clean live or retrospective pre-run freeze snapshot.",
        next_action="Keep regenerated artifacts committed before using KG as a frozen manuscript source.",
        claim_boundary="Ready-with-caveats is not a frozen manuscript snapshot.",
    )
    add_finding(
        rows,
        finding_id="legacy_resume_default_disabled",
        source_audit="parallel_methodology_audit",
        severity="high",
        status=(
            "closed"
            if runner_contract["legacy_resume_default"] is False
            and runner_contract["legacy_resume_explicit_migration"] is True
            else "open_blocker"
        ),
        title="Legacy v1 resume must not silently skip modern scientific reruns.",
        evidence=[
            "experiments/regression/scripts/run_regression_pilot.py",
            "tests/test_regression_pilot_cache.py",
        ],
        observed=runner_contract,
        closure_standard="Default legacy resume is false; explicit migration flag still works.",
        next_action="Use legacy resume only for documented migration-equivalence checks.",
        claim_boundary="Legacy checkpoint reuse is not paper evidence unless explicitly justified.",
    )
    add_finding(
        rows,
        finding_id="prediction_cache_data_code_provenance",
        source_audit="parallel_methodology_audit",
        severity="high",
        status=(
            "closed"
            if runner_contract["cache_payload_has_data_provenance"]
            and runner_contract["cache_payload_has_code_provenance"]
            and runner_contract["frame_fingerprint_changes_cache_key"]
            else "open_blocker"
        ),
        title="Prediction cache must be keyed by loaded data and runtime provenance.",
        evidence=[
            "experiments/regression/scripts/run_regression_pilot.py",
            "tests/test_regression_pilot_cache.py",
        ],
        observed=runner_contract,
        closure_standard="Payload has data/code provenance and frame fingerprint changes the cache key.",
        next_action="Extend provenance if future loaders add external raw-file hash manifests.",
        claim_boundary="Cache hits are reusable only within their recorded provenance contract.",
    )
    add_finding(
        rows,
        finding_id="retrospective_gate_dirty_snapshot",
        source_audit="parallel_methodology_audit",
        severity="medium",
        status=dirty_snapshot_status,
        title="Retrospective gate must record dirty state and a diff hash.",
        evidence=["experiments/regression/scripts/run_retrospective_quality_gate.py"],
        observed=dirty_snapshot,
        closure_standard="Gate-level dirty snapshot includes dirty count, samples, and diff name-status hash; publication freeze requires a clean worktree.",
        next_action="Treat dirty snapshots as audit-time telemetry, and rerun after commit before citing frozen manuscript evidence.",
        claim_boundary="Dirty worktree artifacts cannot be cited as frozen manuscript evidence.",
    )
    add_finding(
        rows,
        finding_id="final_empirical_claims_blocked",
        source_audit="parallel_methodology_audit",
        severity="medium",
        status="closed" if final_claims_blocked else "open_blocker",
        title="Current artifacts must not support final empirical or fairness claims.",
        evidence=[
            rel(root / REPORT_DIR / "publication_methodology_audit.json", root),
            rel(root / REPORT_DIR / "final_selection_claim_boundary_audit.json", root),
        ],
        observed={
            **claim_flags,
            "claim_status": final_summary.get("claim_status"),
            "requirement_statuses": publication.get("requirement_statuses") or {},
        },
        closure_standard="Final selection and broad claims remain blocked until dedicated gates pass.",
        next_action="Keep manuscript language limited to workbench, reproducibility, caveated robustness, and negative diagnostics.",
        claim_boundary="No best-method, fairness, production, bounded-support-validity, or validated Venn-Abers claim.",
    )
    add_finding(
        rows,
        finding_id="manuscript_unsupported_claim_scan_scope",
        source_audit="parallel_methodology_audit",
        severity="high",
        status=(
            "closed"
            if manuscript_scan_in_scope
            and safe_int(cross_summary.get("unsupported_claim_hits")) == 0
            else "open_blocker"
        ),
        title="Unsupported-claim scan must include manuscript artifacts.",
        evidence=[
            "experiments/regression/scripts/audit_methodology_sanity.py",
            rel(root / REPORT_DIR / "cross_run_integrity_audit.json", root),
        ],
        observed={
            "scan_roots": list(sanity.UNSUPPORTED_CLAIM_SCAN_ROOTS),
            "manuscript_scan_in_scope": manuscript_scan_in_scope,
            "unsupported_claim_hits": cross_summary.get("unsupported_claim_hits"),
        },
        closure_standard="Manuscript artifacts are scanned and unsupported final/production/fairness/Venn-Abers claims remain absent.",
        next_action="Keep manuscript drafts under experiments/regression/manuscript so the claim linter covers them.",
        claim_boundary="Zero unsupported hits is meaningful only for scanned authoring surfaces.",
    )
    add_finding(
        rows,
        finding_id="feature_leakage_metadata_completeness_scoped",
        source_audit="parallel_methodology_audit",
        severity="medium",
        status=(
            "open_blocker"
            if feature_hard_violations > 0 or not feature_guard_ok
            else "tracked_caveat"
            if feature_not_recorded > 0 or feature_policy_not_recorded > 0
            else "closed"
        ),
        title="Feature-leakage closure must stay scoped when metadata is incomplete.",
        evidence=[
            rel(root / REPORT_DIR / "cross_run_integrity_audit.json", root),
            rel(root / REPORT_DIR / "feature_leakage_metadata_completeness_triage.json", root),
        ],
        observed={
            "feature_metadata_selection_counts": feature_selection_counts,
            "feature_policy_inference_counts": feature_policy_counts,
            "triaged_report_count": feature_summary.get("triaged_report_count"),
            "legacy_provenance_gap_row_count": feature_summary.get(
                "legacy_provenance_gap_row_count"
            ),
            "field_metadata_incomplete_row_count": feature_summary.get(
                "field_metadata_incomplete_row_count"
            ),
            "full_preprocessing_lineage_claim_supported": feature_summary.get(
                "full_preprocessing_lineage_claim_supported"
            ),
            "provenance_limitation_class_counts": feature_summary.get(
                "provenance_limitation_class_counts"
            ),
            "hard_feature_leakage_violation_row_count": feature_hard_violations,
            "runner_feature_drop_guard_ok": feature_guard_ok,
            "triage_scientific_status": feature_summary.get("scientific_status"),
        },
        closure_standard="Hard leakage is absent, runner guard is active, and no feature metadata/policy rows are unrecorded.",
        next_action="Do not claim full preprocessing-output leakage closure until all legacy prediction bundles expose the metadata.",
        claim_boundary="Current evidence supports hard-leakage-not-detected-in-scanned-artifacts, not complete feature-lineage closure.",
    )
    add_finding(
        rows,
        finding_id="duplicate_sensitivity_caveat_status_explicit",
        source_audit="parallel_methodology_audit",
        severity="medium",
        status=(
            "open_blocker"
            if safe_int(duplicate_summary.get("hard_failed_check_count")) > 0
            or any(
                status != "covered_by_sensitivity"
                for status in duplicate_covered_action_status_counts
            )
            else "closed"
        ),
        title="Duplicate sensitivity covered-actions must separate closure from tracked caveats.",
        evidence=[rel(root / REPORT_DIR / "duplicate_sensitivity_closure_audit.json", root)],
        observed={
            "covered_action_status_counts": duplicate_covered_action_status_counts,
            "tracked_caveat_action_status_counts": (
                duplicate_tracked_caveat_status_counts
            ),
            "backlog_covered_action_count_total": duplicate_summary.get(
                "backlog_covered_action_count_total"
            ),
            "tracked_caveat_action_count": duplicate_summary.get(
                "tracked_caveat_action_count"
            ),
            "duplicate_caveat_count": duplicate_summary.get("duplicate_caveat_count"),
            "open_action_count": duplicate_summary.get("open_action_count"),
            "hard_failed_check_count": duplicate_summary.get("hard_failed_check_count"),
        },
        closure_standard="Covered actions that remain tracked methodology caveats are counted separately from sensitivity-closed actions.",
        next_action="Preserve this distinction in manuscript tables and KG summaries.",
        claim_boundary="Tracked duplicate caveats are robustness limitations, not closed evidence.",
    )
    add_finding(
        rows,
        finding_id="venn_abers_bridge_undercoverage_run_level",
        source_audit="parallel_methodology_audit",
        severity="high",
        status=(
            "tracked_caveat"
            if venn_summary.get("can_support_venn_abers_regression_validation") is False
            and safe_int(venn_run_summary.get("undercoverage_run_count")) > 0
            else "closed"
            if venn_summary.get("can_support_venn_abers_regression_validation") is False
            and safe_int(venn_run_summary.get("undercoverage_run_count")) == 0
            and safe_int(venn_run_summary.get("run_count")) > 0
            else "open_blocker"
        ),
        title="Fast Venn-Abers bridge undercoverage must be tracked at run level.",
        evidence=[rel(root / REPORT_DIR / "venn_abers_validation_readiness_audit.json", root)],
        observed={
            **venn_run_summary,
            "panel_mean_coverage": venn_summary.get("mean_venn_abers_coverage_by_panel"),
            "undercoverage_panel_count": venn_summary.get("undercoverage_panel_count"),
            "validation_requirement_status": venn_summary.get(
                "validation_requirement_status"
            ),
            "can_support_venn_abers_regression_validation": venn_summary.get(
                "can_support_venn_abers_regression_validation"
            ),
        },
        closure_standard="Run-level fast-bridge coverage is available and validation stays blocked while undercoverage exists.",
        next_action="Use fast bridge as failure-mode diagnostics unless an exact validated regression Venn-Abers procedure passes dedicated gates.",
        claim_boundary="Fast bridge undercoverage is negative diagnostic evidence, not validated Venn-Abers regression evidence.",
    )
    add_finding(
        rows,
        finding_id="venn_abers_grid_ivapd_validation_protocol_blocked",
        source_audit="parallel_methodology_audit",
        severity="high",
        status=(
            "tracked_caveat"
            if venn_grid_ivapd_summary.get(
                "can_support_validated_venn_abers_regression"
            )
            is False
            and safe_int(venn_grid_ivapd_summary.get("validation_blocker_count")) > 0
            else "closed"
            if venn_grid_ivapd_summary.get(
                "can_support_validated_venn_abers_regression"
            )
            is False
            and safe_int(venn_grid_ivapd_summary.get("validation_blocker_count")) == 0
            else "open_blocker"
        ),
        title="Grid-reference and IVAPD diagnostics must not be promoted to validated Venn-Abers regression.",
        evidence=[
            rel(
                root
                / REPORT_DIR
                / "venn_abers_grid_ivapd_validation_protocol.json",
                root,
            )
        ],
        observed={
            "overall_status": venn_grid_ivapd_summary.get("overall_status"),
            "can_support_validated_venn_abers_regression": venn_grid_ivapd_summary.get(
                "can_support_validated_venn_abers_regression"
            ),
            "can_support_exact_grid_venn_abers_validation": venn_grid_ivapd_summary.get(
                "can_support_exact_grid_venn_abers_validation"
            ),
            "can_support_ivapd_interval_cp_validation": venn_grid_ivapd_summary.get(
                "can_support_ivapd_interval_cp_validation"
            ),
            "validation_blocker_count": venn_grid_ivapd_summary.get(
                "validation_blocker_count"
            ),
            "validation_blocker_ids": venn_grid_ivapd_summary.get(
                "validation_blocker_ids"
            ),
            "total_grid_reference_rows_scored": venn_grid_ivapd_summary.get(
                "total_grid_reference_rows_scored"
            ),
            "total_grid_reference_rows_available": venn_grid_ivapd_summary.get(
                "total_grid_reference_rows_available"
            ),
            "grid_reference_scored_fraction": venn_grid_ivapd_summary.get(
                "grid_reference_scored_fraction"
            ),
            "min_panel_grid_reference_coverage": venn_grid_ivapd_summary.get(
                "min_panel_grid_reference_coverage"
            ),
            "max_panel_grid_hit_upper_rate": venn_grid_ivapd_summary.get(
                "max_panel_grid_hit_upper_rate"
            ),
            "total_ivapd_rows_scored": venn_grid_ivapd_summary.get(
                "total_ivapd_rows_scored"
            ),
        },
        closure_standard="Exact-grid validation requires enough full-test score-grid rows, no candidate-grid boundary hits, nominal panel coverage, and a separate IVAPD interval-CP validity protocol.",
        next_action="Use the grid reference to design the next validation experiment; do not cite IVAPD interval extractions as interval-CP validity.",
        claim_boundary="Grid-reference and IVAPD rows are validation-design diagnostics until this dedicated gate supports a claim.",
    )
    add_finding(
        rows,
        finding_id="venn_abers_negative_evidence_disposition_control",
        source_audit="parallel_methodology_audit",
        severity="high",
        status=(
            "closed"
            if venn_negative_disposition_summary.get("overall_status")
            == "venn_abers_negative_evidence_disposition_pass"
            and safe_int(
                venn_negative_disposition_summary.get("failed_check_count")
            )
            == 0
            and safe_int(
                venn_negative_disposition_summary.get(
                    "shortlist_venn_abers_method_count"
                )
            )
            == 0
            and safe_int(
                venn_negative_disposition_summary.get(
                    "excluded_with_validation_gate_count"
                )
            )
            >= 2
            and safe_int(
                venn_negative_disposition_summary.get(
                    "venn_bundle_main_eligible_count"
                )
            )
            == 0
            and safe_int(
                venn_negative_disposition_summary.get(
                    "venn_bundle_main_unblocked_count"
                )
            )
            == 0
            else "open_blocker"
        ),
        title="Venn-Abers negative evidence must not leak into final-selection or main-result surfaces.",
        evidence=[
            rel(
                root
                / REPORT_DIR
                / "venn_abers_negative_evidence_disposition_audit.json",
                root,
            )
        ],
        observed={
            "overall_status": venn_negative_disposition_summary.get(
                "overall_status"
            ),
            "failed_check_count": venn_negative_disposition_summary.get(
                "failed_check_count"
            ),
            "negative_claim_present": venn_negative_disposition_summary.get(
                "negative_claim_present"
            ),
            "shortlist_venn_abers_method_count": (
                venn_negative_disposition_summary.get(
                    "shortlist_venn_abers_method_count"
                )
            ),
            "excluded_venn_abers_method_count": (
                venn_negative_disposition_summary.get(
                    "excluded_venn_abers_method_count"
                )
            ),
            "excluded_with_validation_gate_count": (
                venn_negative_disposition_summary.get(
                    "excluded_with_validation_gate_count"
                )
            ),
            "venn_bundle_row_count": venn_negative_disposition_summary.get(
                "venn_bundle_row_count"
            ),
            "venn_bundle_main_eligible_count": (
                venn_negative_disposition_summary.get(
                    "venn_bundle_main_eligible_count"
                )
            ),
            "final_selection_venn_abers_gate_status": (
                venn_negative_disposition_summary.get(
                    "final_selection_venn_abers_gate_status"
                )
            ),
        },
        closure_standard="Venn-Abers methods are absent from the shortlist, both blocked variants are excluded by the validation gate, and every Venn-Abers-mentioned bundle is blocked from main-result surfaces.",
        next_action="Use the negative result in discussion or a negative-results table only with its claim boundary.",
        claim_boundary="Disposition closure prevents overclaiming; it does not validate Venn-Abers regression.",
    )
    add_finding(
        rows,
        finding_id="venn_abers_grid_expansion_queue_resumable",
        source_audit="parallel_methodology_audit",
        severity="medium",
        status=(
            "tracked_caveat"
            if venn_grid_expansion_summary.get("overall_status")
            == "venn_abers_grid_expansion_plan_ready"
            and safe_int(venn_grid_expansion_summary.get("failed_check_count")) == 0
            and safe_int(venn_grid_expansion_summary.get("total_grid_rows_pending")) > 0
            and safe_int(
                venn_grid_expansion_summary.get(
                    "duplicate_next_batch_task_key_count"
                )
            )
            == 0
            else "closed"
            if venn_grid_expansion_summary.get("overall_status")
            in {
                "venn_abers_grid_expansion_plan_ready",
                "venn_abers_grid_expansion_plan_complete",
            }
            and safe_int(venn_grid_expansion_summary.get("failed_check_count")) == 0
            and safe_int(venn_grid_expansion_summary.get("total_grid_rows_pending")) == 0
            and safe_int(venn_grid_expansion_summary.get("next_batch_total_rows")) == 0
            and safe_int(
                venn_grid_expansion_summary.get(
                    "duplicate_next_batch_task_key_count"
                )
            )
            == 0
            else "open_blocker"
        ),
        title="Score-grid expansion must be row-level resumable before validation claims.",
        evidence=[
            rel(root / REPORT_DIR / "venn_abers_grid_expansion_plan.json", root),
            rel(
                root
                / REPORT_DIR
                / "venn_abers_grid_ivapd_validation_protocol.json",
                root,
            ),
        ],
        observed={
            "overall_status": venn_grid_expansion_summary.get("overall_status"),
            "failed_check_count": venn_grid_expansion_summary.get(
                "failed_check_count"
            ),
            "run_task_count": venn_grid_expansion_summary.get("run_task_count"),
            "total_test_rows_available": venn_grid_expansion_summary.get(
                "total_test_rows_available"
            ),
            "total_grid_rows_completed": venn_grid_expansion_summary.get(
                "total_grid_rows_completed"
            ),
            "total_grid_rows_pending": venn_grid_expansion_summary.get(
                "total_grid_rows_pending"
            ),
            "grid_completion_fraction": venn_grid_expansion_summary.get(
                "grid_completion_fraction"
            ),
            "next_batch_total_rows": venn_grid_expansion_summary.get(
                "next_batch_total_rows"
            ),
            "duplicate_next_batch_task_key_count": venn_grid_expansion_summary.get(
                "duplicate_next_batch_task_key_count"
            ),
            "largest_pending_tasks": venn_grid_expansion_summary.get(
                "largest_pending_tasks"
            ),
        },
        closure_standard="Every diagnostic run has a unique row-level resume queue and no pending score-grid rows remain before exact-grid validation is claimed.",
        next_action="Execute expansion batches from the queued report/run/test-index units, then rerun the grid/IVAPD validation gate.",
        claim_boundary="The queue is operational provenance only; pending-row counts do not validate Venn-Abers regression coverage.",
    )
    add_finding(
        rows,
        finding_id="duplicate_content_caveats_quarantined",
        source_audit="parallel_methodology_audit",
        severity="medium",
        status=(
            "closed"
            if duplicate_quarantine_closed
            else "tracked_caveat"
            if safe_int(duplicate_summary.get("open_action_count")) == 0
            and safe_int(duplicate_summary.get("hard_failed_check_count")) == 0
            and safe_int(duplicate_quarantine_summary.get("failed_check_count")) == 0
            else "open_blocker"
        ),
        title="Duplicate/content caveats remain material and must be quarantined from final claims.",
        evidence=[
            rel(root / REPORT_DIR / "duplicate_sensitivity_closure_audit.json", root),
            rel(root / REPORT_DIR / "duplicate_content_quarantine_audit.json", root),
        ],
        observed={
            "overall_status": duplicate_summary.get("overall_status"),
            "duplicate_caveat_count": duplicate_summary.get("duplicate_caveat_count"),
            "open_action_count": duplicate_summary.get("open_action_count"),
            "hard_failed_check_count": duplicate_summary.get("hard_failed_check_count"),
            "quarantine_overall_status": duplicate_quarantine_summary.get(
                "overall_status"
            ),
            "quarantine_failed_check_count": duplicate_quarantine_summary.get(
                "failed_check_count"
            ),
            "quarantined_action_count": duplicate_quarantine_summary.get(
                "quarantined_action_count"
            ),
            "unquarantined_action_count": duplicate_quarantine_summary.get(
                "unquarantined_action_count"
            ),
            "main_results_eligible_action_count": duplicate_quarantine_summary.get(
                "main_results_eligible_action_count"
            ),
            "caveat_label_missing_action_count": duplicate_quarantine_summary.get(
                "caveat_label_missing_action_count"
            ),
            "linked_final_claim_action_count": duplicate_quarantine_summary.get(
                "linked_final_claim_action_count"
            ),
        },
        closure_standard="No open remediation actions or hard failures; all duplicate-sensitive manuscript candidates are caveated and blocked from final-claim surfaces.",
        next_action="Keep duplicate scope and caveat status in every candidate manuscript row.",
        claim_boundary="Duplicate-sensitive runs are caveated robustness evidence only.",
    )
    add_finding(
        rows,
        finding_id="bounded_support_posthandling_wording_scoped",
        source_audit="parallel_methodology_audit",
        severity="medium",
        status=(
            "tracked_caveat"
            if posthandling_summary.get("can_support_all_current_bounded_support_claims")
            and bounded_summary.get("can_support_bounded_support_validity") is False
            and bounded_dataset_summary.get("can_support_bounded_support_validity") is False
            else "closed"
            if bounded_summary.get("can_support_bounded_support_validity") is False
            and bounded_dataset_summary.get("can_support_bounded_support_validity") is False
            else "open_blocker"
        ),
        title="Bounded-support post-handling wording must not imply bounded-support validity.",
        evidence=[
            rel(root / "experiments/regression/manuscript/bounded_support_posthandling_validation.json", root),
            rel(root / "experiments/regression/manuscript/bounded_support_protocol.json", root),
            rel(root / "experiments/regression/manuscript/bounded_support_dataset_audit.json", root),
        ],
        observed={
            "posthandling_metric_claim_flag": posthandling_summary.get(
                "can_support_all_current_bounded_support_claims"
            ),
            "protocol_can_support_bounded_support_validity": bounded_summary.get(
                "can_support_bounded_support_validity"
            ),
            "dataset_can_support_bounded_support_validity": bounded_dataset_summary.get(
                "can_support_bounded_support_validity"
            ),
            "bounded_support_ready_bundle_count": bounded_dataset_summary.get(
                "bounded_support_ready_bundle_count"
            ),
        },
        closure_standard="Post-handling metric support is explicitly separated from bounded-support validity.",
        next_action="Prefer the phrase post-handling metric support in manuscript notes.",
        claim_boundary="Do not convert clip/abstention metrics into bounded-support validity.",
    )

    counts = status_counts(rows)
    open_blocker_count = int(counts.get("open_blocker") or 0)
    hard_open_blocker_count = sum(
        1
        for row in rows
        if row["status"] == "open_blocker" and row["severity"] in {"high", "critical"}
    )
    tracked_caveat_count = int(counts.get("tracked_caveat") or 0)
    if open_blocker_count:
        overall_status = "scientific_review_findings_fail"
    elif tracked_caveat_count:
        overall_status = "scientific_review_findings_tracked_with_open_caveats"
    else:
        overall_status = "scientific_review_findings_closed"

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": overall_status,
            "finding_count": len(rows),
            "status_counts": counts,
            "open_blocker_count": open_blocker_count,
            "hard_open_blocker_count": hard_open_blocker_count,
            "tracked_caveat_count": tracked_caveat_count,
            "closed_count": int(counts.get("closed") or 0),
        },
        "claim_boundaries": [
            "This register tracks review-finding closure and caveats; it is not empirical model evidence.",
            "Tracked caveats may be manuscript discussion material but cannot support final superiority, fairness, bounded-support-validity, production, or validated Venn-Abers claims.",
            "A closed methodology finding means the repo has an executable control, not that all future experiments are scientifically final.",
        ],
        "findings": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Scientific Review Finding Register",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Findings: {summary['finding_count']}",
        f"- Status counts: `{json.dumps(summary['status_counts'], sort_keys=True)}`",
        f"- Open blockers: {summary['open_blocker_count']}",
        f"- Hard open blockers: {summary['hard_open_blocker_count']}",
        f"- Tracked caveats: {summary['tracked_caveat_count']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Findings",
            "",
            "| Finding | Source | Severity | Status | Evidence | Claim boundary |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["findings"]:
        evidence = "<br>".join(f"`{item}`" for item in row.get("evidence", []))
        lines.append(
            "| "
            f"`{row['finding_id']}` | "
            f"`{row['source_audit']}` | "
            f"`{row['severity']}` | "
            f"`{row['status']}` | "
            f"{evidence} | "
            f"{row['claim_boundary']} |"
        )
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
                "status": payload["summary"]["overall_status"],
                "out": rel(out_path, root),
                "open_blocker_count": payload["summary"]["open_blocker_count"],
                "tracked_caveat_count": payload["summary"]["tracked_caveat_count"],
            },
            sort_keys=True,
        )
    )
    return 0 if payload["summary"]["open_blocker_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
