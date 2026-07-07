import json
from pathlib import Path

from experiments.regression.scripts import audit_duplicate_content_quarantine as audit


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_sources(root: Path, *, main_eligible: bool = False, caveat_label: bool = True) -> None:
    report_dir = root / audit.REPORT_DIR
    write_json(
        report_dir / "duplicate_sensitivity_closure_audit.json",
        {
            "summary": {
                "duplicate_caveat_count": 2,
                "open_action_count": 0,
                "hard_failed_check_count": 0,
            },
            "covered_actions": [
                {
                    "action_id": "bundle_a:caveat:duplicate_signature_cross_split_caveat",
                    "report_id": "report:bundle_a",
                    "report_name": "bundle_a",
                    "issue_type": "duplicate_signature_cross_split_caveat",
                    "status": "covered_by_sensitivity",
                }
            ],
            "tracked_caveat_actions": [
                {
                    "action_id": "not_paper:caveat:duplicate_cluster_plus_family_internal_fold_caveat",
                    "report_id": "report:not_paper",
                    "report_name": "not_paper",
                    "issue_type": "duplicate_cluster_plus_family_internal_fold_caveat",
                    "status": "tracked_methodology_caveat",
                }
            ],
        },
    )
    write_json(
        root / "experiments/regression/manuscript/bundle_eligibility_matrix.json",
        {
            "rows": [
                {
                    "bundle_id": "bundle_a",
                    "status": "completed_with_caveats" if caveat_label else "completed",
                    "paper_table_candidate": "robustness_results_table",
                    "claim_scope": "Duplicate robustness only.",
                    "requires_caveat_label": caveat_label,
                    "promotion_blockers": ["no final claim"] if caveat_label else [],
                    "linked_claim_statuses": {
                        "claim_a": "robustness_evidence_gate_passed_with_caveats"
                    },
                    "eligible_surface_ids": [
                        "dataset_table",
                        "robustness_results_table",
                        "methodology_appendix",
                    ],
                    "blocked_surface_ids": [] if main_eligible else ["main_results_table"],
                    "surface_eligibility": {
                        "main_results_table": {
                            "eligible": main_eligible,
                            "status": "eligible" if main_eligible else "blocked",
                        },
                        "robustness_results_table": {
                            "eligible": True,
                            "status": (
                                "eligible_with_caveats" if caveat_label else "eligible"
                            ),
                        },
                    },
                }
            ]
        },
    )


def test_duplicate_content_quarantine_passes_for_caveated_nonfinal_candidate(tmp_path):
    write_sources(tmp_path)

    payload = audit.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "duplicate_content_quarantine_pass"
    assert payload["summary"]["duplicate_action_count"] == 2
    assert payload["summary"]["manuscript_candidate_action_count"] == 1
    assert payload["summary"]["non_manuscript_action_count"] == 1
    assert payload["summary"]["unquarantined_action_count"] == 0
    assert payload["summary"]["main_results_eligible_action_count"] == 0
    assert payload["summary"]["caveat_label_missing_action_count"] == 0


def test_duplicate_content_quarantine_fails_for_main_results_candidate(tmp_path):
    write_sources(tmp_path, main_eligible=True)

    payload = audit.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "duplicate_content_quarantine_fail"
    assert payload["summary"]["main_results_eligible_action_count"] == 1
    assert payload["summary"]["unquarantined_action_count"] == 1


def test_duplicate_content_quarantine_fails_without_required_caveat_label(tmp_path):
    write_sources(tmp_path, caveat_label=False)

    payload = audit.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "duplicate_content_quarantine_fail"
    assert payload["summary"]["caveat_label_missing_action_count"] == 1
    assert payload["summary"]["unquarantined_action_count"] == 1
