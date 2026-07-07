import json
from pathlib import Path

from experiments.regression.scripts import build_duplicate_split_caveat_backlog as backlog
from experiments.regression.scripts import audit_methodology_sanity as methodology


def write_split_profile(path: Path) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema": "cpfi_regression_split_profile_v2",
                "config_path": "experiments/regression/configs/toy.yaml",
                "experiment_id": "toy_v0",
                "profiles": [
                    {
                        "dataset_id": "toy_duplicate",
                        "target": "y",
                        "primary_group": "group",
                        "split_strategy": "random",
                        "split_group_col": None,
                        "rows_after_target_drop": 5,
                        "seeds": [
                            {
                                "seed": 11,
                                "row_signature_overlaps": {
                                    "train_cal": 2,
                                    "train_test": 0,
                                    "cal_test": 1,
                                },
                                "row_id_overlaps": {
                                    "train_cal": 0,
                                    "train_test": 0,
                                    "cal_test": 0,
                                },
                                "split_group_overlaps": {
                                    "train_cal": 0,
                                    "train_test": 0,
                                    "cal_test": 0,
                                },
                            }
                        ],
                    },
                    {
                        "dataset_id": "toy_duplicate_dedup",
                        "target": "y",
                        "primary_group": "group",
                        "split_strategy": "random",
                        "split_group_col": None,
                        "rows_after_target_drop": 4,
                        "seeds": [
                            {
                                "seed": 11,
                                "row_signature_overlaps": {
                                    "train_cal": 0,
                                    "train_test": 0,
                                    "cal_test": 0,
                                },
                                "row_id_overlaps": {
                                    "train_cal": 0,
                                    "train_test": 0,
                                    "cal_test": 0,
                                },
                                "split_group_overlaps": {
                                    "train_cal": 0,
                                    "train_test": 0,
                                    "cal_test": 0,
                                },
                            }
                        ],
                    },
                    {
                        "dataset_id": "toy_clean",
                        "target": "y",
                        "primary_group": "group",
                        "split_strategy": "random",
                        "split_group_col": None,
                        "rows_after_target_drop": 5,
                        "seeds": [
                            {
                                "seed": 11,
                                "row_signature_overlaps": {
                                    "train_cal": 0,
                                    "train_test": 0,
                                    "cal_test": 0,
                                },
                                "row_id_overlaps": {
                                    "train_cal": 0,
                                    "train_test": 0,
                                    "cal_test": 0,
                                },
                                "split_group_overlaps": {
                                    "train_cal": 0,
                                    "train_test": 0,
                                    "cal_test": 0,
                                },
                            }
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_duplicate_backlog_extracts_only_duplicate_content_caveats(tmp_path):
    split_path = (
        tmp_path
        / "experiments/regression/reports/toy_duplicate_report/split_profile.json"
    )
    write_split_profile(split_path)

    payload = backlog.build_payload(tmp_path)

    assert payload["schema"] == backlog.SCHEMA
    assert payload["summary"]["affected_dataset_count"] == 1
    assert payload["summary"]["affected_seed_profile_count"] == 1
    assert payload["summary"]["total_duplicate_signature_pair_overlaps"] == 3
    row = payload["rows"][0]
    assert row["dataset_id"] == "toy_duplicate"
    assert row["report_id"] == "report:toy_duplicate_report"
    assert row["pair_totals"] == {"train_cal": 2, "train_test": 0, "cal_test": 1}
    assert row["hard_split_leakage_status"] == "no_row_id_or_split_group_overlap"
    assert row["paired_dedup_variant_available"] is True
    assert row["paired_dedup_variant_dataset_id"] == "toy_duplicate_dedup"
    assert "duplicate content remains a sensitivity caveat" in row["allowed_interpretation"]
    assert row["status"] == "needs_duplicate_aware_sensitivity"
    assert "toy_clean" not in {item["dataset_id"] for item in payload["rows"]}


def test_render_markdown_records_claim_boundaries(tmp_path):
    split_path = (
        tmp_path
        / "experiments/regression/reports/toy_duplicate_report/split_profile.json"
    )
    write_split_profile(split_path)

    text = backlog.render_markdown(backlog.build_payload(tmp_path))

    assert "# Duplicate Split Caveat Backlog" in text
    assert "`toy_duplicate`" in text
    assert "`toy_duplicate_dedup`" in text
    assert "not row-id leakage evidence" in text
    assert "needs_duplicate_aware_sensitivity" in text


def test_methodology_status_accepts_synchronized_duplicate_backlog(tmp_path):
    split_path = (
        tmp_path
        / "experiments/regression/reports/toy_duplicate_report/split_profile.json"
    )
    write_split_profile(split_path)
    payload = backlog.build_payload(tmp_path)
    out_path = tmp_path / methodology.DUPLICATE_SPLIT_CAVEAT_BACKLOG
    out_path.parent.mkdir(parents=True)
    out_path.write_text(json.dumps(payload), encoding="utf-8")

    split_integrity = methodology.split_profile_integrity_scan(tmp_path)
    status = methodology.duplicate_split_caveat_backlog_status(
        tmp_path,
        split_integrity,
    )

    assert status["synchronized"] is True
    assert status["actual_datasets"] == ["toy_duplicate"]
    assert status["actual_total_duplicate_signature_pair_overlaps"] == 3


def test_rel_accepts_external_probe_outputs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_path = repo_root / "experiments/regression/reports/duplicate.json"
    external_path = tmp_path / "scratch/duplicate.json"

    assert backlog.rel(repo_path, repo_root) == "experiments/regression/reports/duplicate.json"
    assert backlog.rel(external_path, repo_root) == str(external_path)
