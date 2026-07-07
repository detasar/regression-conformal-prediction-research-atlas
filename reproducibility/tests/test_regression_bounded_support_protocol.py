import json

from experiments.regression.scripts import build_bounded_support_protocol as protocol


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_minimal_sources(root):
    write_json(
        root / protocol.MANIFEST_SCHEMA,
        {
            "data_evidence_fields": [
                "source_registry_entry",
                "dataset_audit_json",
                "dataset_audit_md",
                "data_policy",
                "missingness_policy",
                "dropped_feature_policy",
                "duplicate_profile",
                "bounded_support_policy",
            ]
        },
    )
    (root / protocol.PUBLICATION_PROTOCOL).parent.mkdir(parents=True, exist_ok=True)
    (root / protocol.PUBLICATION_PROTOCOL).write_text(
        "A manuscript dataset needs bounded-support or endpoint-domain policy when the target has natural bounds.",
        encoding="utf-8",
    )
    write_json(
        root / protocol.PUBLICATION_METHODOLOGY,
        {
            "summary": {"can_support_bounded_support_validity": False},
            "requirement_statuses": {"endpoint_bounded_support_gate": "blocked"},
        },
    )
    write_json(
        root / protocol.FINAL_SELECTION,
        {
            "summary": {"claim_status": "blocked"},
            "requirement_statuses": {"endpoint_bounded_support_gate": "blocked"},
        },
    )
    (root / protocol.RETROSPECTIVE_CONTROLS_MD).parent.mkdir(parents=True, exist_ok=True)
    (root / protocol.RETROSPECTIVE_CONTROLS_MD).write_text(
        "Endpoint v2 closure means reconstruction integrity, not bounded-support validity.",
        encoding="utf-8",
    )
    write_json(
        root / protocol.RETROSPECTIVE_GATE,
        {
            "summary": {
                "knowledge_graph": {
                    "endpoint_result_count": 458,
                    "endpoint_caveat_count": 404,
                    "endpoint_result_relation_coverage": {
                        "HAS_ENDPOINT_STATE": 1.0,
                    },
                }
            }
        },
    )
    write_json(
        root / protocol.EVIDENCE_VIEW,
        {
            "summary": {
                "endpoint_result_count": 105,
                "endpoint_caveat_count": 91,
                "clean_endpoint_state_count": 14,
            }
        },
    )


def test_bounded_support_protocol_defines_required_evidence_without_validity_claim(tmp_path):
    write_minimal_sources(tmp_path)

    payload = protocol.build_payload(tmp_path)

    assert (
        payload["summary"]["overall_status"]
        == "bounded_support_protocol_defined_no_validity_claim"
    )
    assert payload["summary"]["bounded_support_policy_field_present"] is True
    assert payload["summary"]["can_support_bounded_support_validity"] is False
    assert payload["summary"]["publication_can_support_bounded_support_validity"] is False
    assert payload["summary"]["endpoint_bounded_support_gate_status"] == "blocked"
    assert payload["summary"]["target_domain_class_count"] == 5
    assert payload["summary"]["interval_handling_policy_count"] == 4
    assert payload["summary"]["required_evidence_count"] >= 10
    assert payload["summary"]["manuscript_endpoint_result_count"] == 105
    assert payload["summary"]["kg_endpoint_caveat_count"] == 404
    assert payload["failed_checks"] == []


def test_bounded_support_protocol_fails_when_manifest_field_missing(tmp_path):
    write_minimal_sources(tmp_path)
    schema_path = tmp_path / protocol.MANIFEST_SCHEMA
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["data_evidence_fields"].remove("bounded_support_policy")
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    payload = protocol.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "bounded_support_protocol_incomplete"
    assert "manifest_schema_has_bounded_support_policy" in payload["failed_checks"]


def test_bounded_support_protocol_fails_when_publication_claim_is_promoted(tmp_path):
    write_minimal_sources(tmp_path)
    publication_path = tmp_path / protocol.PUBLICATION_METHODOLOGY
    publication = json.loads(publication_path.read_text(encoding="utf-8"))
    publication["summary"]["can_support_bounded_support_validity"] = True
    publication_path.write_text(json.dumps(publication), encoding="utf-8")

    payload = protocol.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "bounded_support_protocol_incomplete"
    assert "publication_methodology_keeps_bounded_support_blocked" in payload["failed_checks"]
    assert "endpoint_reconstruction_not_promoted_to_validity" in payload["failed_checks"]


def test_bounded_support_markdown_lists_interval_handling_policies(tmp_path):
    write_minimal_sources(tmp_path)
    payload = protocol.build_payload(tmp_path)

    markdown = protocol.render_markdown(payload)

    assert "# Bounded Support Protocol" in markdown
    assert "bounded_support_policy" in markdown
    assert "report_raw_unclipped_with_excursion_audit" in markdown
    assert "truncate_with_recalibration_required" in markdown
