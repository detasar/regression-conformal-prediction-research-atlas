import json
from pathlib import Path

import yaml

from experiments.regression.scripts import (
    build_method_selection_post_selection_validation_batch as batch,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def source_config(path: Path, dataset_id: str, seeds: list[int]) -> None:
    write_yaml(
        path,
        {
            "experiment_id": f"alpha_source_{dataset_id}_v1",
            "random_seeds": seeds,
            "alphas": [0.01, 0.05, 0.15],
            "target_transform": "log1p",
            "splits": {"train": 0.6, "calibration": 0.2, "test": 0.2},
            "conformal": {"cv_plus_folds": 5, "jackknife_plus_max_train_rows": 500},
            "datasets": [dataset_id],
            "models": [
                {
                    "model_id": "ridge",
                    "family": "linear",
                    "grid": {"alpha": [1.0]},
                }
            ],
            "cp_methods": ["cqr", "cv_plus", "mondrian_abs"],
            "quality_controls": {"interpret_cqr_as_fixed_quantile_backend": True},
        },
    )


def source_row(dataset_id: str, config_path: Path, seeds: list[int]) -> dict:
    return {
        "dataset_id": dataset_id,
        "config_path": str(config_path),
        "experiment_id": f"regression_method_selection_alpha_expansion_{dataset_id}_v1",
        "random_seeds": seeds,
        "target_alphas": ["0.01", "0.05", "0.15"],
        "cp_methods": ["cqr", "cv_plus", "mondrian_abs"],
        "expected_atomic_run_count": 27,
    }


def write_support_artifacts(root: Path, source_rows: list[dict]) -> dict[str, Path]:
    report_dir = root / "experiments/regression/reports/methodology_sanity_audit_20260627"
    manuscript_dir = root / "experiments/regression/manuscript"
    paths = {
        "source_batch": report_dir / "method_selection_alpha_expansion_batch.json",
        "candidate_audit": report_dir / "method_selection_candidate_audit.json",
        "robustness_audit": report_dir / "method_selection_robustness_audit.json",
        "alpha_plan": report_dir / "method_selection_alpha_expansion_plan.json",
        "multiplicity_protocol": manuscript_dir / "selection_multiplicity_protocol.json",
    }
    write_json(
        paths["source_batch"],
        {
            "summary": {
                "overall_status": "method_selection_alpha_expansion_batch_ready",
                "generated_config_count": len(source_rows),
                "expected_atomic_run_count": 54,
                "can_support_final_method_selection": False,
            },
            "generated_configs": source_rows,
        },
    )
    write_json(
        paths["candidate_audit"],
        {
            "summary": {
                "overall_status": "method_selection_candidate_audit_ready_no_final_selection",
                "can_support_final_method_selection": False,
                "primary_candidate_method": "cqr",
            }
        },
    )
    write_json(
        paths["robustness_audit"],
        {
            "summary": {
                "overall_status": "method_selection_robustness_audit_ready_no_final_selection",
                "can_support_final_method_selection": False,
                "candidate_methods": ["cqr", "mondrian_abs", "cv_plus"],
                "common_cell_winner_counts": {
                    "cqr": 55,
                    "cv_plus": 14,
                    "mondrian_abs": 20,
                },
            }
        },
    )
    write_json(
        paths["alpha_plan"],
        {
            "summary": {
                "overall_status": "method_selection_alpha_expansion_plan_not_needed",
                "failed_check_count": 0,
                "can_support_final_method_selection": False,
            }
        },
    )
    write_json(
        paths["multiplicity_protocol"],
        {
            "summary": {
                "overall_status": "selection_multiplicity_protocol_ready",
                "selection_protocol_can_support_final_method_selection": False,
            }
        },
    )
    return paths


def test_post_selection_validation_batch_materializes_independent_validation_configs(
    tmp_path,
):
    root = tmp_path
    config_dir = Path("experiments/regression/configs")
    d1_config = config_dir / "method_selection_alpha_expansion_d1.yaml"
    d2_config = config_dir / "method_selection_alpha_expansion_d2.yaml"
    source_config(root / d1_config, "d1", [11, 23, 47])
    source_config(root / d2_config, "d2", [42, 71])
    paths = write_support_artifacts(
        root,
        [
            source_row("d1", d1_config, [11, 23, 47]),
            source_row("d2", d2_config, [42, 71]),
        ],
    )

    payload, writes = batch.build_payload(
        root=root,
        source_batch_path=paths["source_batch"],
        candidate_audit_path=paths["candidate_audit"],
        robustness_audit_path=paths["robustness_audit"],
        alpha_plan_path=paths["alpha_plan"],
        multiplicity_protocol_path=paths["multiplicity_protocol"],
        config_dir=root / config_dir,
        results_root=Path("experiments/regression/results"),
        batch_id="test_post_selection_validation",
    )

    assert (
        payload["summary"]["overall_status"]
        == "method_selection_post_selection_validation_batch_ready"
    )
    assert payload["summary"]["generated_config_count"] == 2
    assert payload["summary"]["expected_atomic_run_count"] == 90
    assert payload["summary"]["can_support_final_method_selection"] is False
    assert payload["summary"]["target_alphas"] == ["0.01", "0.05", "0.1", "0.15", "0.2"]
    assert payload["summary"]["candidate_methods"] == ["cqr", "cv_plus", "mondrian_abs"]
    assert {path.name for path, _ in writes} == {
        "method_selection_post_selection_validation_d1.yaml",
        "method_selection_post_selection_validation_d2.yaml",
    }

    configs = {config["datasets"][0]: config for _, config in writes}
    assert configs["d1"]["random_seeds"] == [101, 211, 307]
    assert configs["d1"]["alphas"] == [0.01, 0.05, 0.1, 0.15, 0.2]
    assert configs["d1"]["cp_methods"] == ["cqr", "cv_plus", "mondrian_abs"]
    assert configs["d1"]["models"] == [
        {"model_id": "ridge", "family": "linear", "grid": {"alpha": [1.0]}}
    ]
    assert configs["d1"]["post_selection_validation_provenance"]["seed_overlap"] == []
    assert configs["d1"]["quality_controls"][
        "post_selection_validation_only_no_final_selection"
    ]


def test_post_selection_validation_batch_fails_on_seed_overlap(tmp_path):
    root = tmp_path
    config_dir = Path("experiments/regression/configs")
    d1_config = config_dir / "method_selection_alpha_expansion_d1.yaml"
    source_config(root / d1_config, "d1", [101, 23])
    paths = write_support_artifacts(root, [source_row("d1", d1_config, [101, 23])])

    payload, writes = batch.build_payload(
        root=root,
        source_batch_path=paths["source_batch"],
        candidate_audit_path=paths["candidate_audit"],
        robustness_audit_path=paths["robustness_audit"],
        alpha_plan_path=paths["alpha_plan"],
        multiplicity_protocol_path=paths["multiplicity_protocol"],
        config_dir=root / config_dir,
        results_root=Path("experiments/regression/results"),
        batch_id="test_post_selection_validation",
    )

    assert (
        payload["summary"]["overall_status"]
        == "method_selection_post_selection_validation_batch_failed"
    )
    failed = {check["check_id"] for check in payload["failed_checks"]}
    assert "validation_seeds_disjoint_from_selection_surface" in failed
    assert writes[0][1]["post_selection_validation_provenance"]["seed_overlap"] == [101]
