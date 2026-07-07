import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments/regression/scripts/audit_neutral_experiment_closure.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "audit_neutral_experiment_closure", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_minimal_sources(root: Path, *, missing_disposition: bool = False) -> None:
    report_dir = (
        root / "experiments/regression/reports/methodology_sanity_audit_20260627"
    )
    manuscript_dir = root / "experiments/regression/manuscript"
    write_json(
        manuscript_dir / "paper_gate_closure_map.json",
        {
            "summary": {
                "overall_status": "paper_gate_closure_map_ready_no_promotions",
                "gate_count": 2,
                "positive_claim_ready_gate_count": 0,
                "scoped_or_negative_path_ready_gate_count": (
                    1 if missing_disposition else 2
                ),
                "disallowed_language_item_count": 4,
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "paper_gate_closure_execution_plan.json",
        {
            "summary": {
                "overall_status": "paper_gate_closure_execution_plan_ready",
                "ready_action_count": 0,
                "next_executable_action_ids": [],
            }
        },
    )
    write_json(
        manuscript_dir / "goal_completion_audit.json",
        {
            "summary": {
                "overall_status": (
                    "goal_completion_audit_neutral_empirical_complete_"
                    "publication_deferred"
                ),
                "can_mark_goal_complete": False,
                "neutral_empirical_phase_complete": True,
                "empirical_completion_policy": "neutral_no_promotion_route_accepted",
                "noncomplete_requirement_count": 2,
                "local_execution_gap_gate_count": 0,
            }
        },
    )
    write_json(
        manuscript_dir / "post_experiment_publication_activation_audit.json",
        {
            "summary": {
                "overall_status": (
                    "post_experiment_publication_preparation_active_with_caveats"
                ),
                "publication_phase_start_authorized": True,
                "publication_preparation_authorized": True,
                "visual_table_audit_authorized": True,
                "manuscript_drafting_authorized": False,
                "sterile_repository_creation_authorized": False,
            }
        },
    )
    write_json(
        report_dir / "experiment_accounting_audit.json",
        {
            "summary": {
                "overall_status": "experiment_accounting_pass",
                "publication_completed_rows": 10,
            }
        },
    )
    write_json(
        report_dir / "method_literature_coverage_audit.json",
        {
            "summary": {
                "overall_status": "method_literature_coverage_pass",
                "failed_check_count": 0,
            }
        },
    )
    write_json(
        report_dir / "method_performance_synthesis.json",
        {
            "summary": {
                "overall_status": "method_performance_synthesis_descriptive_no_final_selection",
                "claim_status": "descriptive_no_final_selection",
            }
        },
    )
    write_json(
        report_dir / "publication_methodology_audit.json",
        {
            "summary": {
                "overall_status": "publication_workbench_ready_with_caveats",
                "unsupported_claim_hits": 0,
            }
        },
    )
    write_json(
        report_dir / "neutral_reporting_language_audit.json",
        {
            "summary": {
                "overall_status": "neutral_reporting_language_audit_pass",
                "unguarded_hit_count": 0,
            }
        },
    )
    write_json(
        report_dir / "scientific_review_finding_register.json",
        {
            "summary": {
                "overall_status": "scientific_review_findings_tracked_with_open_caveats",
                "open_blocker_count": 0,
                "hard_open_blocker_count": 0,
            }
        },
    )
    write_json(
        root / "experiments/regression/reports/knowledge_graph_quality/quality_summary.json",
        {
            "issue_counts_by_severity": {},
            "graph": {"node_count": 10, "edge_count": 25, "isolated_node_count": 0},
            "traceability": {"explicit_edge_provenance_coverage": 1.0},
        },
    )
    write_json(
        report_dir / "kg_publication_quality_audit.json",
        {
            "summary": {
                "overall_status": "kg_publication_ready_with_polish_caveats",
                "hard_failed_check_count": 0,
            }
        },
    )


def test_minimal_neutral_experiment_closure_sources_pass_with_policy_caveat(tmp_path):
    audit = load_module()
    write_minimal_sources(tmp_path)

    payload = audit.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "neutral_experiment_closure_ready"
    assert payload["summary"]["neutral_closure_ready"] is True
    assert payload["summary"]["goal_policy_update_required"] is False
    assert payload["summary"]["goal_neutral_empirical_phase_complete"] is True
    assert payload["summary"]["publication_phase_deferred"] is False
    assert payload["summary"]["publication_preparation_authorized"] is True
    assert payload["failed_checks"] == []


def test_missing_gate_disposition_blocks_neutral_closure(tmp_path):
    audit = load_module()
    write_minimal_sources(tmp_path, missing_disposition=True)

    payload = audit.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "neutral_experiment_closure_blocked"
    assert "all_paper_gates_have_final_dispositions" in payload["failed_checks"]


def test_checked_in_neutral_experiment_closure_audit_passes():
    audit = load_module()

    payload = audit.build_payload(ROOT)

    assert (
        payload["summary"]["overall_status"]
        == "neutral_experiment_closure_ready"
    )
    assert payload["summary"]["neutral_closure_ready"] is True
    assert payload["summary"]["goal_policy_update_required"] is False
    assert payload["summary"]["failed_check_count"] == 0
    assert payload["summary"]["publication_preparation_authorized"] is True
