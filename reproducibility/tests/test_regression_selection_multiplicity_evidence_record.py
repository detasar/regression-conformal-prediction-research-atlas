import json

from experiments.regression.scripts import (
    build_selection_multiplicity_evidence_record as evidence_record,
)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_minimal_sources(root):
    write_json(
        root / evidence_record.MANIFEST_SCHEMA,
        {
            "selection_multiplicity_evidence_fields": [
                "predeclared_operating_criterion",
                "ranking_scope",
                "multiplicity_scope",
                "tie_break_rule",
                "nominal_coverage_requirement",
                "post_selection_claim_boundary",
                "exploratory_ranking_label",
                "sensitivity_or_holdout_validation",
            ]
        },
    )
    write_json(
        root / evidence_record.SELECTION_PROTOCOL,
        {
            "summary": {
                "overall_status": (
                    "selection_multiplicity_protocol_defined_no_final_selection"
                )
            }
        },
    )
    write_json(
        root / evidence_record.PAPER_READINESS,
        {
            "summary": {
                "overall_status": "paper_readiness_blocked_with_evidence_map",
                "blocked_gate_count": 2,
            },
            "blocked_gates": [
                {"gate_id": "final_method_model_selection_gate", "status": "blocked"},
                {"gate_id": "multiplicity_selection_record", "status": "blocked"},
            ],
        },
    )
    write_json(
        root / evidence_record.CANDIDATE_AUDIT,
        {
            "summary": {
                "primary_candidate_method": "cqr",
                "source_completed_ledger_rows": 100,
            }
        },
    )
    write_json(
        root / evidence_record.ROBUSTNESS_AUDIT,
        {
            "summary": {
                "common_cell_selected_method": "cqr",
                "common_dataset_alpha_cell_count": 10,
            }
        },
    )
    write_json(
        root / evidence_record.VALIDATION_RESULTS,
        {
            "summary": {
                "overall_status": (
                    "method_selection_post_selection_validation_results_"
                    "ready_no_final_selection"
                ),
                "expected_atomic_run_count": 18,
                "completed_atomic_run_count": 18,
                "failed_check_count": 0,
                "common_dataset_alpha_cell_count": 4,
                "diagnostic_winner_counts": {"cqr": 3, "mondrian_abs": 1},
                "candidate_methods": ["cqr", "cv_plus", "mondrian_abs"],
                "feature_leakage_violation_count": 0,
                "width_pathology_row_count": 1,
            },
            "dataset_rows": [
                {"dataset_id": "dataset_a"},
                {"dataset_id": "dataset_b"},
            ],
            "diagnostic_selection": {
                "per_cell": [
                    {"alpha": 0.05},
                    {"alpha": 0.1},
                    {"alpha": 0.05},
                    {"alpha": 0.1},
                ]
            },
        },
    )
    write_json(
        root / evidence_record.FINAL_SELECTION,
        {"summary": {"claim_status": "blocked"}},
    )
    write_json(
        root / evidence_record.PUBLICATION_METHODOLOGY,
        {"summary": {"overall_status": "publication_workbench_ready_with_caveats"}},
    )


def test_selection_multiplicity_evidence_records_diagnostic_primary_without_winner(
    tmp_path,
):
    write_minimal_sources(tmp_path)

    payload = evidence_record.build_payload(tmp_path)
    summary = payload["summary"]
    record = payload["selection_multiplicity_evidence"]["selection_records"][0]
    field_record = payload["selection_multiplicity_evidence"]["field_record"]

    assert (
        summary["overall_status"]
        == "selection_multiplicity_evidence_record_ready_no_final_selection"
    )
    assert summary["diagnostic_primary_method"] == "cqr"
    assert summary["diagnostic_primary_win_count"] == 3
    assert summary["diagnostic_runner_up_method"] == "mondrian_abs"
    assert summary["diagnostic_primary_margin"] == 2
    assert summary["can_support_final_method_selection"] is False
    assert summary["final_selection_claim_status"] == "blocked"
    assert summary["failed_check_count"] == 0
    assert record["final_selection_eligible"] is False
    assert record["blocking_gate_ids"] == [
        "final_method_model_selection_gate",
        "multiplicity_selection_record",
    ]
    assert set(field_record) == set(
        payload["selection_multiplicity_evidence"]["required_fields"]
    )
    assert field_record["multiplicity_scope"]["nonselected_methods"] == [
        "cv_plus",
        "mondrian_abs",
    ]


def test_selection_multiplicity_evidence_fails_on_uncovered_schema_field(tmp_path):
    write_minimal_sources(tmp_path)
    schema_path = tmp_path / evidence_record.MANIFEST_SCHEMA
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["selection_multiplicity_evidence_fields"].append("new_required_field")
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    payload = evidence_record.build_payload(tmp_path)

    assert (
        payload["summary"]["overall_status"]
        == "selection_multiplicity_evidence_record_failed"
    )
    assert "new_required_field" in payload["selection_multiplicity_evidence"][
        "missing_fields"
    ]
    assert payload["summary"]["failed_check_count"] == 1


def test_selection_multiplicity_evidence_markdown_keeps_claim_boundary(tmp_path):
    write_minimal_sources(tmp_path)
    payload = evidence_record.build_payload(tmp_path)

    markdown = evidence_record.render_markdown(payload)

    assert "# Selection Multiplicity Evidence Record" in markdown
    assert "This record does not promote a final winner." in markdown
    assert "`diagnostic_primary_candidate_recorded_no_final_selection`" in markdown
    assert "Final winner" in markdown
