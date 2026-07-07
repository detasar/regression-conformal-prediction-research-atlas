import json
from pathlib import Path

from experiments.regression.scripts import (
    audit_post_experiment_publication_activation as activation,
)


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_minimal_sources(root: Path):
    write_json(
        root / activation.POST_EXPERIMENT_PUBLICATION_PROGRAM,
        {
            "status": "deferred_until_experimental_gates_complete",
            "activation_rule": {
                "requires_zero_blocked_paper_gates": True,
                "requires_experiment_closure_verification": True,
            },
            "publication_author": {
                "author_name": "Emre Tasar",
                "author_role": "Data Scientist",
                "author_email": "detasar@gmail.com",
            },
            "sterile_publication_repository_plan": {
                "status": "planned_after_full_experiment_closure",
                "citation_target": "sterile_publication_repository",
                "required_contents": ["README", "citation metadata"],
                "exclusion_rules": ["no scratch artifacts"],
            },
            "reviewer_design_gate": {
                "required_reviewer_pass_count": 5,
                "minimum_structured_recommendations_per_reviewer": 5,
                "required_advice_topics": ["main article", "supplement"],
            },
            "visual_table_audit_agent": {
                "quality_checks": ["readability"],
                "required_output_artifacts": ["visual_table_audit_report.json"],
            },
            "deliverables": [{"deliverable_id": "main_article_latex"}],
            "experiment_completion_definition": {
                "closure_checks": ["all ledgers complete", "zero blocked gates"]
            },
        },
    )
    write_json(
        root / activation.GOAL_COMPLETION_AUDIT,
        {
            "summary": {
                "overall_status": "goal_completion_audit_incomplete_with_evidence",
                "can_mark_goal_complete": False,
                "noncomplete_requirement_count": 7,
            }
        },
    )
    write_json(
        root / activation.PAPER_READINESS_MAP,
        {
            "summary": {
                "overall_status": "paper_readiness_blocked_with_evidence_map",
                "blocked_gate_count": 6,
            },
            "blocked_gates": [
                {"gate_id": "final_method_model_selection_gate"},
                {"gate_id": "endpoint_bounded_support_gate"},
            ],
        },
    )
    write_json(
        root / activation.PAPER_GATE_CLOSURE_MAP,
        {
            "summary": {
                "gate_count": 6,
                "positive_claim_ready_gate_count": 0,
                "scoped_or_negative_path_ready_gate_count": 6,
            }
        },
    )
    write_json(
        root / activation.PAPER_GATE_CLOSURE_EXECUTION_PLAN,
        {"summary": {"ready_action_count": 0, "action_count": 23, "blocked_action_count": 7}},
    )
    write_json(
        root / activation.PUBLICATION_METHODOLOGY_AUDIT,
        {
            "summary": {
                "overall_status": "publication_workbench_ready_with_caveats",
                "failed_check_count": 0,
                "unsupported_claim_hits": 0,
                "blocked_final_requirement_count": 6,
            }
        },
    )
    write_json(
        root / activation.EXPERIMENT_ACCOUNTING_AUDIT,
        {
            "summary": {
                "overall_status": "experiment_accounting_pass",
                "failed_check_count": 0,
                "publication_completed_rows": 145839,
                "canonical_completed_row_count": 156233,
                "venn_grid_rows_pending": 0,
            }
        },
    )
    write_json(
        root / activation.KG_QUALITY_SUMMARY,
        {
            "issue_counts_by_severity": {},
            "graph": {"node_count": 3123, "edge_count": 18431, "isolated_node_count": 0},
            "traceability": {"explicit_edge_provenance_coverage": 1.0},
        },
    )
    write_json(
        root / activation.KG_PUBLICATION_QUALITY_AUDIT,
        {
            "summary": {
                "overall_status": "kg_publication_ready_with_polish_caveats",
                "hard_failed_check_count": 0,
                "polish_caveat_count": 1,
            }
        },
    )
    write_json(
        root / activation.SCIENTIFIC_REVIEW_FINDING_REGISTER,
        {
            "summary": {
                "overall_status": "scientific_review_findings_tracked_with_open_caveats",
                "open_blocker_count": 0,
                "hard_open_blocker_count": 0,
                "tracked_caveat_count": 4,
            }
        },
    )
    write_json(
        root / activation.MANUSCRIPT_BUNDLE_ELIGIBILITY,
        {"summary": {"main_results_eligible_count": 0}},
    )


def test_publication_activation_audit_blocks_before_experiment_closure(tmp_path):
    write_minimal_sources(tmp_path)

    payload = activation.build_payload(tmp_path)
    summary = payload["summary"]
    checks = {row["check_id"]: row for row in payload["activation_checks"]}

    assert summary["overall_status"] == "post_experiment_publication_activation_blocked"
    assert summary["publication_phase_start_authorized"] is False
    assert summary["private_manuscript_drafting_authorized"] is False
    assert summary["manuscript_drafting_authorized"] is False
    assert summary["sterile_repository_creation_authorized"] is False
    assert summary["paper_blocked_gate_count"] == 6
    assert summary["paper_gate_closure_ready_action_count"] == 0
    assert summary["blocked_check_count"] == 2
    assert summary["caveat_check_count"] == 1
    assert checks["neutral_empirical_completion_verified"]["status"] == "blocked"
    assert (
        checks["positive_claim_blockers_guarded_for_neutral_route"]["status"]
        == "blocked"
    )
    assert checks["paper_gate_execution_queue_empty"]["status"] == "pass"
    assert checks["final_result_dispositions_available"]["status"] == "pass"
    assert checks["kg_quality_publication_clean"]["status"] == "caveat"
    assert checks["author_metadata_present"]["status"] == "pass"
    assert payload["activation_decision"]["decision"] == "do_not_start_publication_phase"


def test_checked_in_publication_activation_audit_current_status_after_generation():
    payload = activation.build_payload(Path("."))
    summary = payload["summary"]

    assert (
        summary["overall_status"]
        == "post_experiment_publication_preparation_active_with_caveats"
    )
    assert summary["publication_phase_start_authorized"] is True
    assert summary["publication_preparation_authorized"] is True
    assert summary["neutral_empirical_phase_complete"] is True
    assert summary["neutral_publication_route_allowed"] is True
    assert summary["positive_claim_language_blocked"] is True
    assert summary["private_manuscript_drafting_authorized"] is True
    assert summary["manuscript_drafting_authorized"] is False
    assert summary["visual_table_audit_authorized"] is True
    assert summary["sterile_repository_creation_authorized"] is False
    assert summary["paper_blocked_gate_count"] == 6
    assert summary["paper_gate_closure_ready_action_count"] == 0
    assert summary["goal_can_mark_complete"] is False
    assert summary["blocked_check_count"] == 0
    expected_caveat_count = (
        2
        if summary["kg_publication_status"]
        == "kg_publication_ready_with_polish_caveats"
        else 1
    )
    assert summary["caveat_check_count"] == expected_caveat_count
    assert summary["deferred_check_count"] == 0
    assert summary["kg_publication_status"] in {
        "kg_publication_ready",
        "kg_publication_ready_with_polish_caveats",
    }
    assert summary["reviewer_design_reconciled"] is True
    assert summary["retention_recommendations_ready"] is True
    assert summary["retention_recommendation_row_count"] == 10
    assert summary["author_metadata_present"] is True
    assert summary["sterile_repository_plan_present"] is True
    checks = {row["check_id"]: row for row in payload["activation_checks"]}
    expected_kg_check_status = (
        "caveat"
        if summary["kg_publication_status"]
        == "kg_publication_ready_with_polish_caveats"
        else "pass"
    )
    assert checks["kg_quality_publication_clean"]["status"] == expected_kg_check_status
    assert checks["final_public_release_gate_closed"]["status"] == "caveat"
    assert checks["final_public_release_gate_closed"]["blocks_activation"] is False
