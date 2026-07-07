import json
from pathlib import Path

from experiments.regression.scripts import (
    audit_main_result_candidate_post_run_closure as closure,
)


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_post_run_closure_audit_tracks_missing_sidecars(tmp_path):
    ledger = tmp_path / "experiments/regression/results/main_result_candidate_bundle_demo/ledger.jsonl"
    report_dir = (
        tmp_path / "experiments/regression/reports/main_result_candidate_bundle_demo"
    )
    plan_path = tmp_path / closure.DEFAULT_PLAN
    results_path = tmp_path / closure.DEFAULT_RESULTS
    write_jsonl(
        ledger,
        [
            {
                "run_id": "r1",
                "status": "completed",
                "dataset_id": "demo",
                "seed": 401,
                "alpha": 0.1,
                "model_id": "ridge",
                "model_params": {"alpha": 1.0},
                "cp_method": "cqr",
            }
        ],
    )
    write_json(
        report_dir / "pilot_summary.json",
        {
            "metadata": {
                "unique_run_rows": 1,
                "status_counts": {"completed": 1},
            },
            "rows": [{"dataset_id": "demo"}],
        },
    )
    write_json(
        report_dir / "split_profile.json",
        {
            "schema": "cpfi_regression_split_profile_v2",
            "profiles": [
                {
                    "dataset_id": "demo",
                    "seeds": [
                        {
                            "seed": 401,
                            "all_row_id_overlaps_zero": True,
                            "all_split_group_overlaps_zero": None,
                            "sparse_primary_group_cell_count": 1,
                            "all_model_visible_feature_signature_overlaps_zero": False,
                            "all_model_visible_feature_plus_target_signature_overlaps_zero": False,
                        }
                    ],
                }
            ],
        },
    )
    write_json(
        plan_path,
        {
            "candidate_rows": [
                {
                    "dataset_id": "demo",
                    "config_path": "experiments/regression/configs/demo.yaml",
                    "ledger": str(ledger.relative_to(tmp_path)),
                    "expected_atomic_run_count": 1,
                    "required_post_run_artifacts": ["completed ledger"],
                }
            ]
        },
    )
    write_json(
        results_path,
        {
            "summary": {
                "completed_atomic_run_count": 1,
                "expected_atomic_run_count": 1,
            }
        },
    )
    write_json(
        tmp_path / closure.PAPER_READINESS,
        {"summary": {"main_result_candidate_results_status": "ready"}},
    )
    write_json(
        tmp_path / closure.KG_CATALOG,
        {"nodes": [{"id": "report:main_result_candidate_bundle_results"}]},
    )
    write_json(tmp_path / closure.CLAIM_REGISTER, {"claims": []})
    write_json(tmp_path / closure.BUNDLE_INDEX, {"bundles": []})

    payload = closure.build_payload(
        tmp_path,
        plan_path=plan_path,
        results_path=results_path,
    )

    assert (
        payload["summary"]["overall_status"]
        == "main_result_candidate_post_run_closure_blocked"
    )
    assert payload["summary"]["blocker_counts_by_artifact"] == {
        "bundle_eligibility_refresh": 1,
        "claim_register_refresh": 1,
        "endpoint_audit": 1,
        "feature_leakage_audit": 1,
        "publication_readiness_manifest": 1,
    }
    row = payload["dataset_rows"][0]
    assert row["blocker_count"] == 5
    assert row["caveat_count"] == 1
    split = next(item for item in row["checks"] if item["artifact_id"] == "split_profile")
    assert split["status"] == "pass_with_caveats"


def test_checked_in_candidate_post_run_closure_is_ready_without_promotions():
    payload = json.loads((ROOT / closure.DEFAULT_OUT).read_text(encoding="utf-8"))

    assert (
        payload["summary"]["overall_status"]
        == "main_result_candidate_post_run_closure_ready_no_promotions"
    )
    assert payload["summary"]["can_support_main_result_promotion"] is False
    assert payload["summary"]["candidate_dataset_count"] == 6
    assert payload["summary"]["completed_atomic_run_count"] == 270
    assert payload["summary"]["total_blocker_count"] == 0
    assert payload["summary"]["dataset_blocked_count"] == 0
    assert payload["summary"]["blocker_counts_by_artifact"] == {}
    assert payload["summary"]["artifact_status_counts"]["completed_ledger"] == {
        "pass": 6
    }
    assert payload["summary"]["artifact_status_counts"]["endpoint_audit"] == {
        "present": 6
    }
    assert payload["summary"]["artifact_status_counts"]["feature_leakage_audit"] == {
        "present": 6
    }
    assert payload["summary"]["artifact_status_counts"]["pilot_summary"] == {
        "pass": 6
    }
    assert payload["summary"]["artifact_status_counts"][
        "publication_readiness_manifest"
    ] == {"present": 6}
    assert payload["summary"]["artifact_status_counts"]["claim_register_refresh"] == {
        "present": 6
    }
    assert payload["summary"]["artifact_status_counts"][
        "bundle_eligibility_refresh"
    ] == {"present": 6}
    assert payload["summary"]["artifact_status_counts"]["split_profile"] == {
        "pass_with_caveats": 6
    }
