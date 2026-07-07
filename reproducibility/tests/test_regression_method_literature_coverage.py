import json
from pathlib import Path

from experiments.regression.scripts import audit_method_literature_coverage as audit


ROOT = Path(__file__).resolve().parents[1]


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_minimal_method_literature_repo(
    root,
    *,
    registry_methods,
    cp_methods=(),
    spec_text="split_abs baseline spec",
    notes_text="Distribution-Free Predictive Inference For Regression https://arxiv.org/abs/1604.04173",
):
    write_json(
        root / audit.METHOD_REGISTRY,
        {"regression_methods": registry_methods},
    )
    write_text(root / audit.LITERATURE_NOTES, notes_text)
    write_text(
        root / audit.METHOD_TABLE,
        "No final manuscript method ranking\nNo final empirical ranking is claimed.\n",
    )
    write_text(root / audit.METHOD_SPECS_DIR / "split_and_cqr_regression.md", spec_text)
    write_text(
        root / "experiments/regression/configs/demo.yaml",
        "cp_methods:\n" + "".join(f"  - {method}\n" for method in cp_methods),
    )


def test_checked_in_method_literature_coverage_tracks_current_boundaries():
    payload = json.loads(
        (
            ROOT
            / "experiments/regression/reports/methodology_sanity_audit_20260627/"
            "method_literature_coverage_audit.json"
        ).read_text(encoding="utf-8")
    )
    summary = payload["summary"]
    requirements = {row["requirement_id"]: row for row in payload["requirements"]}

    assert summary["overall_status"] == "method_literature_coverage_pass"
    assert summary["literature_requirement_count"] == 16
    assert summary["hard_failed_requirement_count"] == 0
    assert summary["failed_check_count"] == 0
    assert summary["tracked_gap_count"] == 0
    assert summary["status_counts"] == {"pass": 16}
    assert summary["registry_method_count"] == 30
    assert summary["runner_dispatch_method_count"] == 30
    assert summary["configured_cp_method_count"] == 31
    assert summary["primary_source_url_count"] >= 15
    assert payload["hard_checks"]["all_config_methods_registered"] is True
    assert payload["hard_checks"]["runner_dispatch_methods_registered"] is True
    assert payload["hard_checks"]["method_table_preserves_no_final_ranking_boundary"] is True

    for requirement_id in [
        "split_conformal_regression",
        "conformalized_quantile_regression",
        "distributional_conformal_prediction",
        "full_conformal_score_grid_reference",
        "rank_one_out_reference",
        "conformal_predictive_systems",
        "tail_allocation_shortest_interval_watchlist",
        "split_tail_grid_shortest_diagnostic",
        "plus_family_and_resampling",
        "generalized_venn_abers_quantile_bridge",
    ]:
        assert requirements[requirement_id]["status"] == "pass"
        assert not requirements[requirement_id]["hard_fail_reasons"]
    assert requirements["split_tail_grid_shortest_diagnostic"]["queued_config_total"] == 1

    assert payload["tracked_gaps"] == []


def test_method_literature_coverage_fails_when_runner_method_is_unregistered(
    tmp_path,
    monkeypatch,
):
    requirement = audit.LiteratureRequirement(
        "split_conformal_regression",
        "core_interval",
        "runner_required",
        ("split_abs",),
        ("split_abs",),
        ("experiments/regression/method_specs/split_and_cqr_regression.md",),
        ("https://arxiv.org/abs/1604.04173",),
        ("Distribution-Free Predictive Inference For Regression",),
        "Split conformal must be registered before it is claimed.",
    )
    monkeypatch.setattr(audit, "REQUIREMENTS", (requirement,))
    monkeypatch.setattr(audit, "get_regression_cp_methods", lambda: ["split_abs"])
    write_minimal_method_literature_repo(
        tmp_path,
        registry_methods=[],
        cp_methods=("split_abs",),
    )

    payload = audit.build_payload(tmp_path)
    row = payload["requirements"][0]

    assert payload["summary"]["overall_status"] == "fail"
    assert payload["summary"]["hard_failed_requirement_count"] == 1
    assert payload["summary"]["failed_check_count"] >= 1
    assert payload["hard_checks"]["all_config_methods_registered"] is False
    assert payload["hard_checks"]["runner_dispatch_methods_registered"] is False
    assert payload["hard_checks"]["no_requirement_hard_failures"] is False
    assert row["status"] == "fail"
    assert row["registry_missing"] == ["split_abs"]
    assert "missing_registry_methods" in row["hard_fail_reasons"]


def test_method_literature_coverage_keeps_tracked_gap_nonfatal(tmp_path, monkeypatch):
    requirement = audit.LiteratureRequirement(
        "distributional_conformal_prediction",
        "distributional_interval",
        "tracked_gap",
        ("distributional_conformal_prediction",),
        (),
        ("experiments/regression/method_specs/split_and_cqr_regression.md",),
        ("https://arxiv.org/abs/1604.04173",),
        ("Distribution-Free Predictive Inference For Regression",),
        "Distributional methods need a separate interval-extraction policy.",
    )
    monkeypatch.setattr(audit, "REQUIREMENTS", (requirement,))
    monkeypatch.setattr(audit, "get_regression_cp_methods", lambda: [])
    write_minimal_method_literature_repo(
        tmp_path,
        registry_methods=[
            {
                "method_id": "distributional_conformal_prediction",
                "status": "planned_distributional_method_not_runner_interval",
            }
        ],
        spec_text="distributional_conformal_prediction tracked gap spec",
    )

    payload = audit.build_payload(tmp_path)
    row = payload["requirements"][0]

    assert payload["summary"]["overall_status"] == (
        "method_literature_coverage_pass_with_tracked_gaps"
    )
    assert payload["summary"]["hard_failed_requirement_count"] == 0
    assert payload["summary"]["tracked_gap_count"] == 1
    assert payload["summary"]["failed_check_count"] == 0
    assert row["status"] == "tracked_gap"
    assert row["hard_fail_reasons"] == []
