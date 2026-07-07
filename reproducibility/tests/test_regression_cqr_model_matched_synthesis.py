import json
from pathlib import Path

import yaml

from experiments.regression.scripts import build_cqr_model_matched_synthesis as synth


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def completed_row(run_id: str, cp_method: str, coverage: float, score: float) -> dict:
    return {
        "run_id": run_id,
        "status": "completed",
        "dataset_id": "toy",
        "model_family": "linear",
        "model_id": "ridge",
        "model_params": {"alpha": 1.0},
        "cp_method": cp_method,
        "alpha": 0.1,
        "seed": 1,
        "coverage": coverage,
        "mean_width": 2.0,
        "interval_score": score,
    }


def write_manifest_fixture(root: Path, *, include_model_matched: bool) -> Path:
    source_config = root / "experiments/regression/configs/model_family_sweep_toy.yaml"
    generated_config = (
        root
        / "experiments/regression/configs/model_family_sweep_toy_model_matched_cqr_v1.yaml"
    )
    source_ledger = root / "experiments/regression/results/source/ledger.jsonl"
    generated_ledger = root / "experiments/regression/results/generated/ledger.jsonl"
    write_yaml(
        source_config,
        {
            "experiment_id": "regression_model_family_sweep_toy_v0",
            "logging": {"ledger": source_ledger.relative_to(root).as_posix()},
        },
    )
    write_yaml(
        generated_config,
        {
            "experiment_id": "regression_model_family_sweep_toy_model_matched_cqr_v1",
            "logging": {"ledger": generated_ledger.relative_to(root).as_posix()},
        },
    )
    write_jsonl(source_ledger, [completed_row("fixed", "cqr", 0.91, 5.0)])
    if include_model_matched:
        write_jsonl(
            generated_ledger,
            [completed_row("matched", "cqr_model_matched", 0.93, 4.0)],
        )
    manifest = root / "manifest.json"
    write_json(
        manifest,
        {
            "generated_configs": [
                {
                    "source_config": source_config.relative_to(root).as_posix(),
                    "generated_config": generated_config.relative_to(root).as_posix(),
                    "ledger": generated_ledger.relative_to(root).as_posix(),
                }
            ]
        },
    )
    return manifest


def test_cqr_model_matched_synthesis_reports_pending_without_rerun_rows(tmp_path):
    manifest = write_manifest_fixture(tmp_path, include_model_matched=False)

    payload = synth.build_payload(tmp_path, manifest)

    assert payload["summary"]["status"] == "pending_model_matched_rerun_rows"
    assert payload["summary"]["fixed_gbm_cqr_completed_rows"] == 1
    assert payload["summary"]["model_matched_cqr_completed_rows"] == 0
    assert payload["summary"]["paired_cell_count"] == 0


def test_cqr_model_matched_synthesis_reports_deltas_and_selected_counts(tmp_path):
    manifest = write_manifest_fixture(tmp_path, include_model_matched=True)

    payload = synth.build_payload(tmp_path, manifest)

    assert payload["summary"]["status"] == (
        "descriptive_fixed_vs_model_matched_cqr_synthesis"
    )
    assert payload["summary"]["paired_cell_count"] == 1
    delta = payload["paired_deltas"][0]
    assert delta["coverage_delta_model_matched_minus_fixed"] == 0.020000000000000018
    assert delta["interval_score_delta_model_matched_minus_fixed"] == -1.0
    assert payload["summary"]["coverage_eligible_interval_score_selected_counts"] == {
        "model_matched_cqr": 1
    }
    assert payload["summary"]["can_support_method_winner_claim"] is False
