import json

from experiments.regression.scripts import build_selection_multiplicity_protocol as protocol


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_minimal_sources(root):
    write_json(
        root / protocol.MANIFEST_SCHEMA,
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
    (root / protocol.PUBLICATION_PROTOCOL).parent.mkdir(parents=True, exist_ok=True)
    (root / protocol.PUBLICATION_PROTOCOL).write_text("protocol", encoding="utf-8")
    write_json(
        root / protocol.PUBLICATION_METHODOLOGY,
        {
            "summary": {"can_support_final_method_selection": False},
            "requirement_statuses": {
                "multiplicity_selection_record": "blocked"
            },
        },
    )
    write_json(
        root / protocol.FINAL_SELECTION,
        {"summary": {"claim_status": "blocked"}},
    )
    write_json(root / protocol.EVIDENCE_VIEW, {"rows": []})
    write_json(
        root / protocol.BUNDLE_INDEX,
        {
            "bundle_summary": {"manifest_count": 2},
            "bundles": [
                {
                    "bundle_id": "a",
                    "dataset_id": "dataset_a",
                    "target": "target_a",
                    "target_transform": "identity",
                    "diagnostic_group": "group_a",
                    "evidence_role": "robustness",
                    "paper_table_candidate": "robustness_results_table",
                    "status": "completed_with_caveats",
                    "manifest_path": "reports/a/publication_readiness_manifest.md",
                },
                {
                    "bundle_id": "b",
                    "dataset_id": "dataset_b",
                    "target": "target_b",
                    "target_transform": "log1p",
                    "diagnostic_group": "group_b",
                    "evidence_role": "robustness",
                    "paper_table_candidate": "robustness_results_table",
                    "status": "completed_with_caveats",
                    "manifest_path": "reports/b/publication_readiness_manifest.md",
                },
            ],
        },
    )


def test_selection_multiplicity_protocol_covers_manifest_fields_without_selection(tmp_path):
    write_minimal_sources(tmp_path)

    payload = protocol.build_payload(tmp_path)

    assert (
        payload["summary"]["overall_status"]
        == "selection_multiplicity_protocol_defined_no_final_selection"
    )
    assert payload["summary"]["required_manifest_field_count"] == 8
    assert payload["summary"]["covered_manifest_field_count"] == 8
    assert payload["summary"]["can_support_final_method_selection"] is False
    assert payload["summary"]["final_selection_claim_status"] == "blocked"
    assert payload["summary"]["ranking_scope_count"] == 2
    assert payload["summary"]["selection_record_count"] == 1
    assert payload["summary"]["unlinked_indexed_bundle_count"] == 2
    assert payload["observed_multiplicity_scope"]["unique_dataset_count"] == 2
    assert payload["ranking_scopes"][0]["final_selection_eligible"] is False
    assert payload["selection_records"][0]["status"] == "blocked_no_final_selection"
    assert payload["manifest_coverage"]["indexed_manifest_path_count"] == 2
    assert payload["failed_checks"] == []


def test_selection_multiplicity_protocol_fails_when_schema_field_missing(tmp_path):
    write_minimal_sources(tmp_path)
    schema_path = tmp_path / protocol.MANIFEST_SCHEMA
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["selection_multiplicity_evidence_fields"].append("unmapped_new_field")
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    payload = protocol.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "selection_multiplicity_protocol_incomplete"
    assert "all_manifest_selection_fields_covered" in payload["failed_checks"]


def test_selection_multiplicity_markdown_preserves_no_winner_rule(tmp_path):
    write_minimal_sources(tmp_path)
    payload = protocol.build_payload(tmp_path)

    markdown = protocol.render_markdown(payload)

    assert "# Selection And Multiplicity Protocol" in markdown
    assert "no_winner_rule" in markdown
    assert "best interval score among eligible nominal-or-above rows" in markdown
    assert "## Observed Multiplicity Scope" in markdown
    assert "`blocked_no_final_selection`" in markdown
