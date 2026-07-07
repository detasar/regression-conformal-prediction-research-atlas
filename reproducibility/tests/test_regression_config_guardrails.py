import json
from pathlib import Path

import yaml

from experiments.regression.scripts import audit_methodology_sanity as sanity


ROOT = Path(__file__).resolve().parents[1]
MODEL_VISIBLE_DIR = (
    "experiments/regression/reports/"
    "duplicate_cluster_sensitivity_stackoverflow_2025_compensation_log1p_age_model_visible"
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_stackoverflow_model_visible_boundary_fixture(
    root: Path,
    *,
    cqr_sensitivity_nominal_count: int = 0,
) -> None:
    report_dir = root / MODEL_VISIBLE_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        report_dir / "pilot_summary.json",
        {
            "metadata": {
                "ledger_rows": 2184,
                "unique_run_rows": 2184,
                "status_counts": {"completed": 1404, "skipped_method": 780},
            }
        },
    )
    write_json(report_dir / "split_profile.json", {"profiles": []})
    write_json(
        report_dir / "feature_leakage_audit.json",
        {"metadata_files_scanned": 156, "violations_count": 0},
    )
    write_json(
        report_dir / "runtime_cap_audit.json",
        {
            "skipped_method_rows": 780,
            "unexpected_skipped_methods": [],
            "missing_expected_skipped_methods": [],
        },
    )
    method_summaries = [
        {
            "cp_method": "cqr",
            "paired_rows": 52,
            "baseline_nominal_count": 0,
            "sensitivity_nominal_count": cqr_sensitivity_nominal_count,
        },
        {
            "cp_method": "venn_abers_quantile",
            "paired_rows": 52,
            "baseline_nominal_count": 0,
            "sensitivity_nominal_count": 0,
        },
        {
            "cp_method": "venn_abers_split_fallback",
            "paired_rows": 52,
            "baseline_nominal_count": 50,
            "sensitivity_nominal_count": 52,
        },
    ]
    for method in (
        "mondrian_abs",
        "normalized_abs",
        "split_abs",
        "split_tail_0.25",
        "split_tail_0.50",
        "split_tail_0.75",
    ):
        method_summaries.append(
            {
                "cp_method": method,
                "paired_rows": 52,
                "baseline_nominal_count": 1,
                "sensitivity_nominal_count": 1,
            }
        )
    write_json(
        report_dir / "sensitivity_comparison.json",
        {
            "claim_boundaries": [
                (
                    "StackOverflow 2025 compensation is self-selected "
                    "developer-survey method-engineering evidence only; this "
                    "comparison is model-visible feature-plus-target "
                    "duplicate-split sensitivity only and not "
                    "developer-population compensation, wage-gap, "
                    "labor-market, protected-class fairness, causal, policy, "
                    "production, final-selection, bounded-support, full-data "
                    "plus/jackknife, or Venn-Abers regression validation "
                    "evidence."
                )
            ],
            "summary": {
                "paired_rows": 468,
                "seed_imbalanced_paired_rows": 0,
                "baseline_only_rows": 0,
                "sensitivity_only_rows": 0,
                "baseline_nominal_count": 70,
                "sensitivity_nominal_count": 206,
                "method_summaries": method_summaries,
                "sensitivity_lowest_interval_score_nominal_row": {
                    "cp_method": "normalized_abs",
                    "model_id": "xgboost",
                    "coverage_mean": 0.9017403515731713,
                    "interval_score_mean": 507866.5400929645,
                },
            },
        },
    )
    endpoint_method_summary = {}
    for index, method in enumerate(sorted(row["cp_method"] for row in method_summaries)):
        endpoint_method_summary[method] = {
            "runs": 156,
            "lower_below_floor": 1 if index < 6 else 0,
            "lower_below_observed_min": 0,
            "upper_above_observed_max": 0,
            "upper_above_warning": 0,
            "width_above_observed_range": 0,
            "width_above_twice_observed_range": 0,
        }
    write_json(
        report_dir / "endpoint_audit.json",
        {
            "reconstructed_runs": 1404,
            "reconstruction_failures": 0,
            "method_summary": endpoint_method_summary,
        },
    )
    (report_dir / "publication_readiness_manifest.md").write_text(
        """
CQR remains unsupported because it has 0/52 seed-aggregated nominal paired rows.
The model-visible lowest nominal interval-score row is exploratory:
`normalized_abs` with XGBoost.
Fast `venn_abers_quantile` remains negative diagnostic evidence;
`venn_abers_split_fallback` remains ordinary split fallback evidence, not
Venn-Abers regression validation.
""",
        encoding="utf-8",
    )
    write_json(
        root / "experiments/regression/catalogs/manuscript_claim_register.json",
        {
            "claims": [
                {
                    "claim_id": "stackoverflow_model_visible_duplicate_sensitivity_pending",
                    "status": "robustness_evidence_gate_passed_with_caveats",
                    "not_claiming": [
                        (
                            "This is not a final method/model selection claim. "
                            "No developer-population compensation, wage-gap, "
                            "protected-class fairness, labor-market, causal, "
                            "policy, production, final-selection, nonnegative "
                            "interval validity, full-data plus/jackknife, or "
                            "Venn-Abers regression validation claim is made."
                        )
                    ],
                    "requirements": [
                        {
                            "requirement_id": "complete_model_ledger",
                            "status": "complete",
                        },
                        {
                            "requirement_id": "post_run_sidecars",
                            "status": "present_with_endpoint_caveats",
                        },
                        {
                            "requirement_id": "selection_multiplicity_record",
                            "status": "recorded_no_selection",
                        },
                        {
                            "requirement_id": "methodology_gate_refresh",
                            "status": "pass_with_caveats",
                        },
                    ],
                }
            ]
        },
    )
    write_json(
        root / "experiments/regression/manuscript/evidence_view.json",
        {
            "rows": [
                {
                    "claim_id": "stackoverflow_model_visible_duplicate_sensitivity_pending",
                    "bundle_ids": [
                        "duplicate_cluster_sensitivity_stackoverflow_2025_compensation_log1p_age_model_visible"
                    ],
                    "endpoint_result_count": 9,
                    "endpoint_caveat_count": 6,
                    "clean_endpoint_state_count": 3,
                }
            ]
        },
    )
    robustness_path = root / "experiments/regression/manuscript/robustness_results_table.md"
    robustness_path.parent.mkdir(parents=True, exist_ok=True)
    robustness_path.write_text(
        (
            "StackOverflow model-visible sensitivity keeps CQR out of a "
            "supported-candidate claim because it has 0/52 nominal rows. "
            "`normalized_abs` plus XGBoost is exploratory and not a selected "
            "method."
        ),
        encoding="utf-8",
    )


def test_model_family_venn_abers_configs_forbid_validated_regression_claims():
    config_paths = sorted(
        (ROOT / "experiments/regression/configs").glob("model_family_sweep_*.yaml")
    )
    missing = []
    for path in config_paths:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        methods = set(config.get("cp_methods", []) or [])
        if not methods.intersection(
            {"venn_abers_quantile", "venn_abers_split_fallback"}
        ):
            continue
        controls = config.get("quality_controls", {}) or {}
        if not controls.get("forbid_validated_venn_abers_regression_claims"):
            missing.append(path.relative_to(ROOT).as_posix())

    assert missing == []


def test_all_configs_with_cqr_or_venn_abers_have_claim_guards():
    config_paths = sorted((ROOT / "experiments/regression/configs").glob("*.yaml"))
    missing = []
    for path in config_paths:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        methods = set(config.get("cp_methods", []) or [])
        controls = config.get("quality_controls", {}) or {}
        if "cqr" in methods and not controls.get("interpret_cqr_as_fixed_quantile_backend"):
            missing.append((path.relative_to(ROOT).as_posix(), "cqr"))
        if (
            methods.intersection({"venn_abers_quantile", "venn_abers_split_fallback"})
            and not controls.get("forbid_validated_venn_abers_regression_claims")
        ):
            missing.append((path.relative_to(ROOT).as_posix(), "venn_abers"))

    assert missing == []


def test_runner_feature_drop_guard_scan_covers_target_group_and_split_group():
    evidence = sanity.runner_feature_drop_guard_scan(ROOT)

    assert evidence["fit_block_found"] is True
    assert evidence["drops_target_before_preprocessing"] is True
    assert evidence["drops_primary_group_when_present"] is True
    assert evidence["drops_split_group_when_present"] is True
    assert evidence["drops_base_split_group_when_present"] is True
    assert evidence["drops_loader_extra_feature_drop_columns"] is True
    assert evidence["deduplicates_feature_drop_columns"] is True


def test_model_family_loader_leakage_policy_has_no_hard_backlog():
    config_rows = sanity.scan_configs(ROOT)
    evidence = sanity.config_loader_leakage_policy_scan(config_rows, ROOT)

    assert evidence["unknown_dataset_refs"] == []
    assert evidence["missing_loader_target_or_group"] == []
    assert evidence["model_family_extra_target_boundary_missing"] == []
    assert evidence["model_family_derived_group_source_policy_missing"] == []


def test_model_family_control_contract_backlog_is_limited_to_triage_flag():
    config_rows = sanity.scan_configs(ROOT)
    evidence = sanity.model_family_control_contract_backlog(config_rows, ROOT)

    for item in evidence["missing_by_config"]:
        assert item["missing_controls"] == ["interpret_rankings_as_triage_only"]


def test_stackoverflow_sparse_age_evidence_requires_diagnostic_caveat(tmp_path):
    split_json = tmp_path / "split_profile.json"
    split_json.write_text(
        json.dumps(
            {
                "profiles": [
                    {
                        "dataset_id": "stackoverflow_2025_compensation",
                        "primary_group": "Age",
                        "seeds": [
                            {
                                "seed": 11,
                                "sparse_primary_group_cells": [
                                    {
                                        "split": "test",
                                        "group": "Prefer not to say",
                                        "count": 1,
                                        "threshold": 10,
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    missing = sanity.stackoverflow_sparse_age_evidence(split_json, "Prefer not to say")
    documented = sanity.stackoverflow_sparse_age_evidence(
        split_json,
        "Prefer not to say is a sparse diagnostic-only age cell.",
    )

    assert missing["sparse_cal_or_test_age_cell_count"] == 1
    assert missing["sparse_age_policy_documented"] is False
    assert documented["sparse_age_policy_documented"] is True


def test_stackoverflow_model_visible_claim_boundary_status_is_synchronized():
    evidence = sanity.stackoverflow_model_visible_claim_boundary_status(ROOT)

    assert evidence["synchronized"] is True
    assert evidence["failed_checks"] == []
    assert evidence["method_nominal_counts"]["cqr"] == {
        "paired_rows": 52,
        "baseline_nominal_count": 0,
        "sensitivity_nominal_count": 0,
    }
    assert evidence["sensitivity_frontier"]["cp_method"] == "normalized_abs"
    assert evidence["sensitivity_frontier"]["model_id"] == "xgboost"
    assert len(evidence["endpoint_caveat_methods"]) == 6


def test_stackoverflow_model_visible_claim_boundary_flags_cqr_drift(tmp_path):
    write_stackoverflow_model_visible_boundary_fixture(
        tmp_path,
        cqr_sensitivity_nominal_count=3,
    )

    evidence = sanity.stackoverflow_model_visible_claim_boundary_status(tmp_path)

    assert evidence["synchronized"] is False
    assert "cqr_not_supported_0_of_52" in evidence["failed_checks"]
