import json
from pathlib import Path

from experiments.regression.scripts import build_fairness_sampling_weight_policy as policy


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_minimal_sources(root: Path):
    write_json(
        root / policy.BUNDLE_INDEX,
        {
            "bundles": [
                {
                    "bundle_id": "nhanes_bundle",
                    "dataset_id": "nhanes_2017_2018_bmi",
                    "target": "BMXBMI",
                    "target_transform": "identity",
                    "diagnostic_group": "RIDRETH3",
                },
                {
                    "bundle_id": "wine_bundle",
                    "dataset_id": "uci_wine_quality",
                    "target": "quality",
                    "target_transform": "identity",
                    "diagnostic_group": "wine_color",
                },
            ]
        },
    )
    write_json(
        root / policy.PAPER_GATE_PROTOCOL_DESIGN_BUNDLE,
        {
            "protocol_design_rows": [
                {
                    "action_id": (
                        "fairness_population_inference_gate."
                        "define_population_and_protected_scope"
                    ),
                    "status": "protocol_design_complete",
                }
            ]
        },
    )
    write_json(
        root / policy.AUDIT_ROOT / "nhanes_2017_2018_bmi" / "audit.json",
        {"survey_design_columns": ["WTMEC2YR", "SDMVSTRA", "SDMVPSU"]},
    )
    write_json(root / policy.AUDIT_ROOT / "uci_wine_quality" / "audit.json", {})


def test_minimal_sampling_weight_policy_declares_diagnostic_only_rows(tmp_path):
    write_minimal_sources(tmp_path)

    payload = policy.build_payload(tmp_path)

    assert (
        payload["summary"]["overall_status"]
        == "fairness_sampling_weight_policy_defined_no_fairness_claim"
    )
    assert payload["failed_checks"] == []
    assert payload["summary"]["policy_declared_bundle_count"] == 2
    assert payload["summary"]["weighted_estimand_applied_bundle_count"] == 0
    assert payload["summary"]["population_fairness_ready_bundle_count"] == 0
    assert (
        payload["summary"]["dataset_policy_counts"][
            "complex_survey_design_available_not_applied"
        ]
        == 1
    )
    assert (
        payload["summary"]["dataset_policy_counts"][
            "nonhuman_product_benchmark_no_protected_class"
        ]
        == 1
    )
    nhanes = {
        row["bundle_id"]: row for row in payload["bundle_policy_rows"]
    }["nhanes_bundle"]
    assert nhanes["required_weight_columns_for_population_claim"] == [
        "WTMEC2YR",
        "SDMVSTRA",
        "SDMVPSU",
    ]
    assert nhanes["claim_effect"] == "policy_declared_no_population_fairness_claim"


def test_checked_in_sampling_weight_policy_is_current():
    payload = policy.build_payload(Path("."))

    assert (
        payload["summary"]["overall_status"]
        == "fairness_sampling_weight_policy_defined_no_fairness_claim"
    )
    assert payload["summary"]["candidate_bundle_count"] == 15
    assert payload["summary"]["policy_declared_bundle_count"] == 15
    assert payload["summary"]["weighted_estimand_applied_bundle_count"] == 0
    assert payload["summary"]["population_fairness_ready_bundle_count"] == 0
    assert payload["summary"]["survey_design_required_before_population_claim_bundle_count"] == 8
