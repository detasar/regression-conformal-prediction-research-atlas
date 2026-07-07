import json
from pathlib import Path

import pandas as pd

from experiments.regression.scripts import build_fairness_group_diagnostic_audit as audit


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_minimal_group_diagnostic_records_counts_missingness_and_gaps(
    tmp_path, monkeypatch
):
    write_json(
        tmp_path / audit.BUNDLE_INDEX,
        {
            "bundles": [
                {
                    "bundle_id": "bundle_a",
                    "dataset_id": "dataset_a",
                    "target": "y",
                    "target_transform": "identity",
                    "diagnostic_group": "group",
                }
            ]
        },
    )
    write_json(
        tmp_path / audit.SAMPLING_WEIGHT_POLICY,
        {
            "bundle_policy_rows": [
                {
                    "bundle_id": "bundle_a",
                    "policy_id": "sampling_weight_policy:bundle_a",
                    "policy_status": "declared_diagnostic_only",
                    "current_estimand_policy": "unweighted_diagnostic_only",
                }
            ]
        },
    )
    report_dir = tmp_path / audit.REPORTS_ROOT / "bundle_a"
    result_dir = tmp_path / audit.RESULTS_ROOT / "bundle_a"
    write_json(
        report_dir / "pilot_summary.json",
        {
            "ledger": str((result_dir / "ledger.jsonl").relative_to(tmp_path)),
            "rows": [
                {
                    "cp_method": "cqr",
                    "alpha": 0.1,
                    "model_id": "ridge",
                    "model_params_key": "{}",
                    "coverage_gap_mean": 0.05,
                    "coverage_gap_std": 0.01,
                    "coverage_gap_count": 3,
                    "width_gap_mean": 2.0,
                    "width_gap_std": 0.5,
                    "width_gap_count": 3,
                }
            ],
        },
    )
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "ledger.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "status": "completed",
                        "cp_method": "cqr",
                        "alpha": 0.1,
                        "coverage_by_group": {"A": 0.9, "B": 0.95},
                        "width_by_group": {"A": 2.0, "B": 3.0},
                        "coverage_gap": 0.05,
                        "width_gap": 1.0,
                    }
                ),
                json.dumps(
                    {
                        "status": "completed",
                        "cp_method": "cqr",
                        "alpha": 0.1,
                        "coverage_by_group": {"A": 0.92, "B": 0.96},
                        "width_by_group": {"A": 2.2, "B": 3.2},
                        "coverage_gap": 0.04,
                        "width_gap": 1.0,
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    def fake_loader(dataset_id: str):
        assert dataset_id == "dataset_a"
        return (
            pd.DataFrame(
                {
                    "y": [1.0, 2.0, 3.0, 4.0, 5.0],
                    "group": ["A", "A", "B", "B", "B"],
                    "feature": [1.0, None, 3.0, 4.0, 5.0],
                }
            ),
            "y",
            "group",
        )

    monkeypatch.setattr(audit, "load_model_frame", fake_loader)

    payload = audit.build_payload(tmp_path, bootstrap_replicates=25)
    row = payload["rows"][0]

    assert (
        payload["summary"]["overall_status"]
        == "fairness_group_diagnostic_audit_completed_no_fairness_claim"
    )
    assert payload["summary"]["group_counts_recorded_bundle_count"] == 1
    assert payload["summary"]["missingness_by_group_audited_bundle_count"] == 1
    assert payload["summary"]["group_gap_uncertainty_recorded_bundle_count"] == 1
    assert row["group_counts"] == {"B": 3, "A": 2}
    assert row["coverage_by_group"] == {"A": 0.91, "B": 0.955}
    assert row["width_by_group"] == {"A": 2.1, "B": 3.1}
    assert row["population_fairness_claim_promoted"] is False


def test_checked_in_fairness_group_diagnostic_audit_is_current():
    payload = json.loads(
        (
            ROOT
            / "experiments/regression/reports/methodology_sanity_audit_20260627/"
            "fairness_group_diagnostic_audit.json"
        ).read_text(encoding="utf-8")
    )
    summary = payload["summary"]

    assert (
        summary["overall_status"]
        == "fairness_group_diagnostic_audit_completed_no_fairness_claim"
    )
    assert summary["action_status"] == "empirical_execution_complete"
    assert summary["bundle_count"] == 15
    assert summary["dataset_count"] == 6
    assert summary["group_counts_recorded_bundle_count"] == 15
    assert summary["missingness_by_group_audited_bundle_count"] == 15
    assert summary["coverage_by_group_recorded_bundle_count"] == 15
    assert summary["width_by_group_recorded_bundle_count"] == 15
    assert summary["group_gap_uncertainty_recorded_bundle_count"] == 15
    assert summary["population_fairness_ready_bundle_count"] == 0
