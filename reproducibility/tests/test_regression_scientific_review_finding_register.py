import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "experiments/regression/scripts/build_scientific_review_finding_register.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "build_scientific_review_finding_register", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_checked_in_scientific_review_register_has_no_open_blockers():
    register = load_module()

    payload = register.build_payload(ROOT)
    markdown = register.render_markdown(payload)
    findings = {row["finding_id"]: row for row in payload["findings"]}

    assert payload["summary"]["overall_status"] in {
        "scientific_review_findings_closed",
        "scientific_review_findings_tracked_with_open_caveats",
    }
    assert payload["summary"]["finding_count"] >= 10
    assert payload["summary"]["open_blocker_count"] == 0
    assert payload["summary"]["hard_open_blocker_count"] == 0
    assert findings["legacy_resume_default_disabled"]["status"] == "closed"
    assert findings["prediction_cache_data_code_provenance"]["status"] == "closed"
    assert findings["kg_fact_level_selector_provenance"]["status"] == "closed"
    assert (
        findings["kg_fact_level_selector_provenance"]["observed"][
            "edge_selector_provenance_coverage"
        ]
        == 1.0
    )
    assert findings["manuscript_unsupported_claim_scan_scope"]["status"] == "closed"
    assert findings["feature_leakage_metadata_completeness_scoped"]["status"] in {
        "closed",
        "tracked_caveat",
    }
    assert findings["duplicate_content_caveats_quarantined"]["status"] == "closed"
    assert (
        findings["venn_abers_negative_evidence_disposition_control"]["status"]
        == "closed"
    )
    assert findings["venn_abers_bridge_undercoverage_run_level"]["status"] in {
        "closed",
        "tracked_caveat",
    }
    assert findings["venn_abers_grid_ivapd_validation_protocol_blocked"]["status"] in {
        "closed",
        "tracked_caveat",
    }
    assert findings["venn_abers_grid_expansion_queue_resumable"]["status"] in {
        "closed",
        "tracked_caveat",
    }
    assert "Scientific Review Finding Register" in markdown
    assert "validated Venn-Abers claims" in markdown


def test_scientific_review_prefers_retrospective_pre_run_dirty_snapshot(
    monkeypatch, tmp_path
):
    register = load_module()
    pre_run_dirty = {
        "schema": register.gate.DIRTY_SNAPSHOT_SCHEMA,
        "is_dirty": False,
        "dirty_path_count": 0,
        "diff_name_status_sha256": "pre_names",
        "diff_patch_sha256": "pre_patch",
        "relevant_diff_patch_sha256": "pre_relevant",
    }
    live_dirty = {
        "schema": register.gate.DIRTY_SNAPSHOT_SCHEMA,
        "is_dirty": True,
        "dirty_path_count": 5,
        "diff_name_status_sha256": "live_names",
        "diff_patch_sha256": "live_patch",
        "relevant_diff_patch_sha256": "live_relevant",
    }
    write_json(
        tmp_path / register.RETROSPECTIVE_GATE,
        {"pre_run_git_dirty": pre_run_dirty},
    )
    monkeypatch.setattr(register.gate, "dirty_snapshot", lambda root: live_dirty)

    snapshot = register.retrospective_dirty_snapshot_for_review(tmp_path)

    assert snapshot["is_dirty"] is False
    assert snapshot["dirty_path_count"] == 0
    assert snapshot["diff_patch_sha256"] == "pre_patch"
    assert snapshot["snapshot_source"] == (
        "retrospective_quality_gate_pre_run_git_dirty"
    )


def test_scientific_review_register_flags_broken_kg_traceability(tmp_path):
    register = load_module()
    report_dir = tmp_path / "experiments/regression/reports/methodology_sanity_audit_20260627"
    write_json(
        tmp_path / "experiments/regression/reports/knowledge_graph_quality/quality_summary.json",
        {
            "metadata": {
                "thresholds": {
                    "min_edge_selector_provenance_coverage": 0.80,
                }
            },
            "traceability": {
                "distinct_edge_confidence_value_count": 1,
                "weak_provenance_confidence_one_count": 5,
                "edge_selector_provenance_coverage": 0.0,
                "specific_edge_provenance_coverage": 1.0,
                "high_multiplicity_edges_without_evidence_samples_count": 2,
                "multiplicity_edge_count": 3,
            },
            "observations": {
                "total_observation_count": 1,
                "topology_observation_count": 1,
                "paper_evidence_observation_node_ratio": 0.0,
            },
        },
    )
    write_json(
        report_dir / "kg_publication_quality_audit.json",
        {
            "summary": {
                "overall_status": "kg_publication_ready_with_polish_caveats",
                "polish_caveat_count": 1,
                "relevant_modified_source_count": 1,
            }
        },
    )
    write_json(
        report_dir / "cross_run_integrity_audit.json",
        {
            "summary": {
                "unsupported_claim_hits": 0,
                "feature_metadata_selection_counts": {"not_recorded": 0},
                "feature_policy_inference_counts": {"not_recorded": 0},
            }
        },
    )
    write_json(
        report_dir / "publication_methodology_audit.json",
        {
            "summary": {
                "can_support_final_method_selection": False,
                "can_support_publication_ready_fairness": False,
                "can_support_bounded_support_validity": False,
                "can_support_venn_abers_regression_validation": False,
            }
        },
    )
    write_json(
        report_dir / "final_selection_claim_boundary_audit.json",
        {"summary": {"claim_status": "blocked"}},
    )
    write_json(
        report_dir / "duplicate_sensitivity_closure_audit.json",
        {
            "summary": {
                "duplicate_caveat_count": 0,
                "open_action_count": 0,
                "hard_failed_check_count": 0,
            }
        },
    )
    write_json(
        report_dir / "duplicate_content_quarantine_audit.json",
        {
            "summary": {
                "overall_status": "duplicate_content_quarantine_pass",
                "failed_check_count": 0,
                "duplicate_action_count": 0,
                "manuscript_candidate_action_count": 0,
                "non_manuscript_action_count": 0,
                "quarantined_action_count": 0,
                "unquarantined_action_count": 0,
                "main_results_eligible_action_count": 0,
                "caveat_label_missing_action_count": 0,
                "linked_final_claim_action_count": 0,
            }
        },
    )
    write_json(
        report_dir / "venn_abers_negative_evidence_disposition_audit.json",
        {
            "summary": {
                "overall_status": "venn_abers_negative_evidence_disposition_pass",
                "failed_check_count": 0,
                "shortlist_venn_abers_method_count": 0,
                "excluded_with_validation_gate_count": 2,
                "venn_bundle_main_eligible_count": 0,
                "venn_bundle_main_unblocked_count": 0,
                "excluded_venn_abers_method_count": 2,
                "venn_bundle_row_count": 1,
                "final_selection_venn_abers_gate_status": "blocked",
            }
        },
    )
    write_json(
        report_dir / "feature_leakage_metadata_completeness_triage.json",
        {
            "summary": {
                "hard_feature_leakage_violation_row_count": 0,
                "runner_feature_drop_guard_ok": True,
            }
        },
    )
    write_json(
        tmp_path / "experiments/regression/reports/venn_panel/diagnostic.json",
        {
            "results": [
                {
                    "run_id": "toy_run",
                    "dataset_id": "toy",
                    "interval_method_comparison": [
                        {"method": "venn_abers_quantile", "coverage": 0.7}
                    ],
                }
            ]
        },
    )
    write_json(
        report_dir / "venn_abers_validation_readiness_audit.json",
        {
            "nominal_coverage": 0.9,
            "validation_panels": [
                {
                    "report_id": "report:venn_panel",
                    "path": "experiments/regression/reports/venn_panel/diagnostic.json",
                }
            ],
            "summary": {
                "can_support_venn_abers_regression_validation": False,
                "validation_requirement_status": "blocked",
                "undercoverage_panel_count": 1,
                "mean_venn_abers_coverage_by_panel": {
                    "report:venn_panel": 0.7,
                },
            },
        },
    )
    write_json(
        tmp_path / "experiments/regression/manuscript/bounded_support_protocol.json",
        {"summary": {"can_support_bounded_support_validity": False}},
    )
    write_json(
        tmp_path
        / "experiments/regression/manuscript/bounded_support_posthandling_validation.json",
        {"summary": {"can_support_all_current_bounded_support_claims": False}},
    )
    write_json(
        tmp_path / "experiments/regression/manuscript/bounded_support_dataset_audit.json",
        {
            "summary": {
                "can_support_bounded_support_validity": False,
                "bounded_support_ready_bundle_count": 0,
            }
        },
    )

    payload = register.build_payload(tmp_path)
    findings = {row["finding_id"]: row for row in payload["findings"]}

    assert payload["summary"]["overall_status"] == "scientific_review_findings_fail"
    assert payload["summary"]["open_blocker_count"] >= 3
    assert findings["kg_edge_confidence_calibration"]["status"] == "open_blocker"
    assert findings["kg_fact_level_selector_provenance"]["status"] == "open_blocker"
    assert findings["kg_multiplicity_provenance"]["status"] == "open_blocker"
