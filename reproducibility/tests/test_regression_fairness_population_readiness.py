import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments/regression/scripts/audit_fairness_population_readiness.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "audit_fairness_population_readiness", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_minimal_sources(root: Path) -> None:
    report_dir = (
        root / "experiments/regression/reports/methodology_sanity_audit_20260627"
    )
    catalog_dir = root / "experiments/regression/catalogs"
    manuscript_dir = root / "experiments/regression/manuscript"
    claim = {
        "claim_id": "final_selection_and_fairness_claims_blocked",
        "status": "blocked",
        "claim_text": "Final method/model selection and fairness claims are blocked.",
        "not_claiming": [
            "No population fairness conclusion is supported.",
            "No protected-class fairness conclusion is supported.",
        ],
        "requirements": [
            {
                "requirement_id": "fairness_population_inference_gate",
                "status": "blocked",
            }
        ],
    }
    write_json(catalog_dir / "manuscript_claim_register.json", {"claims": [claim]})
    (catalog_dir / "manuscript_claim_register.md").write_text(
        "# Claim Register\n\nFairness and population claims remain blocked.\n",
        encoding="utf-8",
    )
    write_json(
        catalog_dir / "manuscript_bundle_index.json",
        {
            "bundles": [
                {
                    "bundle_id": "bundle_a",
                    "dataset_id": "dataset_a",
                    "target": "Y",
                    "target_transform": "identity",
                    "diagnostic_group": "sex",
                    "evidence_role": "robustness",
                    "status": "completed_with_caveats",
                    "paper_table_candidate": "robustness_results_table",
                    "claim_scope": "Diagnostic group coverage only.",
                    "promotion_blockers": [
                        "no population-weighted, fairness, policy, causal, or final-selection claim"
                    ],
                }
            ]
        },
    )
    write_json(
        manuscript_dir / "evidence_view.json",
        {
            "summary": {"claim_count": 1},
            "rows": [{"claim_id": "diagnostic_a", "status": "diagnostic"}],
        },
    )
    write_json(
        report_dir / "final_selection_claim_boundary_audit.json",
        {"summary": {"overall_status": "pass", "claim_status": "blocked"}},
    )
    protocol = root / "experiments/regression/PUBLICATION_READINESS_PROTOCOL.md"
    protocol.parent.mkdir(parents=True, exist_ok=True)
    protocol.write_text(
        "Fairness or population claims require a declared estimand and weighting policy.\n",
        encoding="utf-8",
    )


def test_checked_in_fairness_population_readiness_is_current():
    audit = load_module()

    payload = audit.build_payload(ROOT)

    assert (
        payload["summary"]["overall_status"]
        == "fairness_population_readiness_audit_completed_no_fairness_claim"
    )
    assert payload["summary"]["failed_check_count"] == 0
    assert payload["summary"]["can_support_publication_ready_fairness"] is False
    assert payload["summary"]["fairness_requirement_status"] == "blocked"
    assert payload["summary"]["population_fairness_ready_bundle_count"] == 0
    assert payload["summary"]["sampling_weight_policy_declared_bundle_count"] == 15
    assert payload["summary"]["weighted_estimand_applied_bundle_count"] == 0
    assert (
        payload["summary"]["fairness_group_diagnostic_audit_status"]
        == "fairness_group_diagnostic_audit_completed_no_fairness_claim"
    )
    assert payload["summary"]["group_counts_recorded_bundle_count"] == 15
    assert payload["summary"]["missingness_by_group_audited_bundle_count"] == 15
    assert payload["summary"]["group_gap_uncertainty_recorded_bundle_count"] == 15
    assert (
        payload["summary"]["sampling_weight_policy_artifact_status"]
        == "fairness_sampling_weight_policy_defined_no_fairness_claim"
    )
    assert (
        payload["summary"]["fairness_group_multiplicity_scope_status"]
        == "fairness_group_multiplicity_scope_declared_no_fairness_claim"
    )
    assert payload["summary"]["multiplicity_scope_declared_bundle_count"] == 15
    assert payload["summary"]["claim_register_cites_multiplicity_record"] is True
    assert payload["checks"]["diagnostic_group_not_promoted_to_fairness"] is True
    assert payload["checks"]["claim_register_alignment"] is True


def test_minimal_sources_record_diagnostic_only_boundary(tmp_path):
    audit = load_module()
    write_minimal_sources(tmp_path)

    payload = audit.build_payload(tmp_path)
    row = payload["rows"][0]

    assert (
        payload["summary"]["overall_status"]
        == "fairness_population_readiness_audit_completed_no_fairness_claim"
    )
    assert payload["failed_checks"] == []
    assert row["group_role"] == "diagnostic_coverage_stratification"
    assert row["protected_attribute_status"] == "not_approved_for_fairness_claim"
    assert row["fairness_population_claim_status"] == (
        "blocked_diagnostic_only_no_population_claim"
    )
    assert "population fairness" in row["prohibited_claim_language"]


def test_checked_in_fairness_population_readiness_consumes_group_diagnostic_audit():
    audit = load_module()

    payload = audit.build_payload(ROOT)
    row = payload["rows"][0]

    assert row["group_counts_recorded"] is True
    assert row["missingness_by_group_audited"] is True
    assert row["group_gap_uncertainty_recorded"] is True
    assert row["multiplicity_scope_declared_for_group_comparisons"] is True
    assert "group_gap_uncertainty_not_recorded" not in row["missing_evidence"]
    assert "missingness_by_group_not_audited" not in row["missing_evidence"]
    assert (
        "multiplicity_scope_for_group_comparisons_not_declared"
        not in row["missing_evidence"]
    )
