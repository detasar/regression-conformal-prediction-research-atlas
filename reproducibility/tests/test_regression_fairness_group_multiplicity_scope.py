import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "experiments/regression/scripts/build_fairness_group_multiplicity_scope.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "build_fairness_group_multiplicity_scope", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_minimal_sources(root: Path, *, cite_record: bool) -> None:
    module = load_module()
    report_dir = (
        root / "experiments/regression/reports/methodology_sanity_audit_20260627"
    )
    manuscript_dir = root / "experiments/regression/manuscript"
    catalog_dir = root / "experiments/regression/catalogs"
    write_json(
        report_dir / "fairness_group_diagnostic_audit.json",
        {
            "summary": {
                "overall_status": (
                    "fairness_group_diagnostic_audit_completed_no_fairness_claim"
                ),
                "action_status": "empirical_execution_complete",
            },
            "rows": [
                {
                    "bundle_id": "bundle_a",
                    "dataset_id": "dataset_a",
                    "target": "Y",
                    "target_transform": "identity",
                    "diagnostic_group": "sex",
                    "group_count": 2,
                    "group_counts": {"0": 10, "1": 12},
                    "min_group_count": 10,
                    "group_gap_uncertainty_recorded": True,
                }
            ],
        },
    )
    write_json(
        manuscript_dir / "fairness_sampling_weight_policy.json",
        {"summary": {"overall_status": "fairness_sampling_weight_policy_defined_no_fairness_claim"}},
    )
    artifact_paths = []
    supporting_node_ids = []
    if cite_record:
        artifact_paths = [module.DEFAULT_OUT.as_posix()]
        supporting_node_ids = ["report:fairness_group_multiplicity_scope"]
    write_json(
        catalog_dir / "manuscript_claim_register.json",
        {
            "claims": [
                {
                    "claim_id": "final_selection_and_fairness_claims_blocked",
                    "status": "blocked",
                    "requirements": [
                        {
                            "requirement_id": "fairness_population_inference_gate",
                            "status": "blocked",
                            "artifact_paths": artifact_paths,
                            "supporting_node_ids": supporting_node_ids,
                        }
                    ],
                }
            ]
        },
    )
    md_text = "# Claim Register\n"
    if cite_record:
        md_text += "\n- `report:fairness_group_multiplicity_scope`\n"
    (catalog_dir / "manuscript_claim_register.md").write_text(
        md_text,
        encoding="utf-8",
    )


def test_checked_in_fairness_group_multiplicity_scope_is_current():
    module = load_module()

    payload = module.build_payload(ROOT, out_path=module.DEFAULT_OUT)

    assert (
        payload["summary"]["overall_status"]
        == "fairness_group_multiplicity_scope_declared_no_fairness_claim"
    )
    assert payload["summary"]["failed_check_count"] == 0
    assert payload["summary"]["bundle_count"] == 15
    assert payload["summary"]["multiplicity_scope_declared_bundle_count"] == 15
    assert payload["summary"]["claim_register_cites_multiplicity_record"] is True
    assert payload["summary"]["current_manuscript_fairness_population_claim_ready"] is False
    assert payload["summary"]["population_fairness_ready_bundle_count"] == 0
    assert all(
        row["claim_effect"] == "multiplicity_scope_declared_no_fairness_claim"
        for row in payload["rows"]
    )


def test_minimal_sources_require_claim_register_citation(tmp_path):
    module = load_module()
    write_minimal_sources(tmp_path, cite_record=False)

    payload = module.build_payload(tmp_path, out_path=module.DEFAULT_OUT)

    assert payload["summary"]["overall_status"] == "fairness_group_multiplicity_scope_failed"
    assert "claim_register_cites_multiplicity_record" in {
        row["check_id"] for row in payload["failed_checks"]
    }


def test_minimal_sources_declare_diagnostic_scope_with_citation(tmp_path):
    module = load_module()
    write_minimal_sources(tmp_path, cite_record=True)

    payload = module.build_payload(tmp_path, out_path=module.DEFAULT_OUT)

    assert (
        payload["summary"]["overall_status"]
        == "fairness_group_multiplicity_scope_declared_no_fairness_claim"
    )
    assert payload["failed_checks"] == []
    row = payload["rows"][0]
    assert row["pairwise_group_comparison_count"] == 1
    assert row["multiplicity_scope_declared_for_group_comparisons"] is True
    assert "population fairness" in row["prohibited_claim_language"]
