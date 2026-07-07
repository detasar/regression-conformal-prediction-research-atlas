import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT / "experiments/regression/scripts/audit_publication_methodology_readiness.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "audit_publication_methodology_readiness", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_minimal_sources(root: Path, *, stale_markdown: bool = False) -> None:
    report_dir = (
        root / "experiments/regression/reports/methodology_sanity_audit_20260627"
    )
    catalog_dir = root / "experiments/regression/catalogs"
    claim = {
        "claim_id": "final_selection_and_fairness_claims_blocked",
        "status": "blocked",
        "claim_text": "Final method/model selection and fairness claims are blocked.",
        "requirements": [
            {
                "requirement_id": "remediation_backlog_closed_or_scoped",
                "status": "pass",
            },
            {
                "requirement_id": "final_method_model_selection_gate",
                "status": "blocked",
            },
            {"requirement_id": "multiplicity_selection_record", "status": "blocked"},
            {"requirement_id": "dataset_specific_final_gates", "status": "blocked"},
            {"requirement_id": "endpoint_bounded_support_gate", "status": "blocked"},
            {
                "requirement_id": "fairness_population_inference_gate",
                "status": "blocked",
            },
            {
                "requirement_id": "venn_abers_regression_validation_gate",
                "status": "blocked",
            },
        ],
    }
    write_json(catalog_dir / "manuscript_claim_register.json", {"claims": [claim]})
    markdown = "# Claim Register\n\nAll final gates remain blocked.\n"
    if stale_markdown:
        markdown += "The remediation backlog still has 8 open actions.\n"
    (catalog_dir / "manuscript_claim_register.md").write_text(
        markdown,
        encoding="utf-8",
    )
    write_json(
        catalog_dir / "manuscript_bundle_index.json",
        {
            "bundles": [
                {"bundle_id": "one", "status": "completed_with_caveats"},
                {"bundle_id": "two", "status": "completed_with_endpoint_caveats"},
            ]
        },
    )
    protocol = root / "experiments/regression/PUBLICATION_READINESS_PROTOCOL.md"
    protocol.parent.mkdir(parents=True, exist_ok=True)
    protocol.write_text(
        """
## Model Selection And Multiplicity

The record must state the predeclared operating criterion, multiplicity scope,
and post-selection claim boundary.
""",
        encoding="utf-8",
    )
    write_json(
        report_dir / "cross_run_integrity_audit.json",
        {
            "summary": {
                "reports_scanned": 2,
                "configs_scanned": 3,
                "total_completed_rows": 5,
                "blocking_issue_counts": {},
                "caveat_counts": {"duplicate_signature_cross_split_caveat": 1},
                "unsupported_claim_hits": 0,
                "leakage_status": "hard_leakage_not_detected_in_scanned_artifacts",
            }
        },
    )
    write_json(
        report_dir / "retrospective_methodology_controls.json",
        {
            "summary": {
                "control_status_counts": {"pass": 9, "caveat": 1},
                "hard_leakage_status": "no_hard_leakage_detected_in_scanned_artifacts",
            }
        },
    )
    write_json(
        report_dir / "integrity_remediation_backlog.json",
        {
            "summary": {
                "action_count": 1,
                "covered_action_count": 1,
                "open_action_count": 0,
            }
        },
    )
    write_json(
        report_dir / "manuscript_manifest_completeness_audit.json",
        {
            "summary": {
                "overall_status": "pass",
                "manifest_count": 2,
                "bundle_index_manifest_count": 2,
            }
        },
    )
    write_json(
        report_dir / "manuscript_claim_register_consistency_audit.json",
        {"summary": {"overall_status": "pass", "claim_count": 1}},
    )
    write_json(
        report_dir / "final_selection_claim_boundary_audit.json",
        {
            "summary": {
                "overall_status": "pass",
                "claim_status": "blocked",
                "blocked_requirement_count": 6,
                "open_remediation_actions": 0,
            }
        },
    )
    write_json(
        report_dir / "fairness_population_readiness_audit.json",
        {
            "summary": {
                "overall_status": "fairness_population_readiness_audit_completed_no_fairness_claim",
                "failed_check_count": 0,
                "can_support_publication_ready_fairness": False,
                "fairness_requirement_status": "blocked",
                "fairness_population_claim_status": "blocked_diagnostic_only",
                "diagnostic_group_bundle_count": 2,
                "population_fairness_ready_bundle_count": 0,
            }
        },
    )
    write_json(
        report_dir / "venn_abers_negative_evidence_disposition_audit.json",
        {
            "summary": {
                "overall_status": "venn_abers_negative_evidence_disposition_pass",
                "negative_result_reporting_ready": True,
                "current_manuscript_positive_validation_required": False,
            }
        },
    )


def test_checked_in_publication_methodology_readiness_is_current():
    audit = load_module()

    payload = audit.build_payload(ROOT)
    markdown = audit.render_markdown(payload)

    assert (
        payload["summary"]["overall_status"]
        == "publication_workbench_ready_with_caveats"
    )
    assert payload["summary"]["open_remediation_actions"] == 0
    assert payload["summary"]["unsupported_claim_hits"] == 0
    assert payload["summary"]["blocked_final_requirement_count"] == 6
    assert payload["summary"]["current_paper_mandatory_blocked_requirement_count"] == 5
    assert payload["summary"]["venn_abers_negative_result_reporting_ready"] is True
    assert (
        payload["summary"]["fairness_population_readiness_status"]
        == "fairness_population_readiness_audit_completed_no_fairness_claim"
    )
    assert payload["summary"]["population_fairness_ready_bundle_count"] == 0
    assert payload["summary"]["can_support_final_method_selection"] is False
    assert payload["summary"]["can_support_venn_abers_regression_validation"] is False
    assert payload["failed_checks"] == []
    assert "8 open" not in markdown
    assert "17:05" not in markdown


def test_stale_snapshot_language_fails(tmp_path):
    audit = load_module()
    write_minimal_sources(tmp_path, stale_markdown=True)

    payload = audit.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "fail"
    assert (
        "source_claims_do_not_contain_stale_snapshot_tokens" in payload["failed_checks"]
    )


def test_minimal_publication_methodology_sources_pass_with_caveats(tmp_path):
    audit = load_module()
    write_minimal_sources(tmp_path)

    payload = audit.build_payload(tmp_path)

    assert (
        payload["summary"]["overall_status"]
        == "publication_workbench_ready_with_caveats"
    )
    assert payload["summary"]["open_remediation_actions"] == 0
    assert payload["summary"]["blocked_final_requirement_count"] == 6
    assert payload["summary"]["current_paper_mandatory_blocked_requirement_count"] == 5
    assert payload["summary"]["venn_abers_negative_result_reporting_ready"] is True
    assert (
        payload["summary"]["fairness_population_claim_status"]
        == "blocked_diagnostic_only"
    )
    assert payload["failed_checks"] == []
