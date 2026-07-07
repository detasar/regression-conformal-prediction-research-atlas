import json

from experiments.regression.scripts import (
    build_manuscript_bundle_eligibility_matrix as matrix,
)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_sources(root, *, manifest_present=True):
    manifest = (
        "experiments/regression/reports/demo_bundle/publication_readiness_manifest.md"
    )
    if manifest_present:
        (root / manifest).parent.mkdir(parents=True, exist_ok=True)
        (root / manifest).write_text("manifest", encoding="utf-8")
    write_json(
        root / matrix.BUNDLE_INDEX,
        {
            "bundles": [
                {
                    "bundle_id": "demo_bundle",
                    "dataset_id": "demo_dataset",
                    "target": "y",
                    "target_transform": "identity",
                    "diagnostic_group": "group",
                    "manifest_path": manifest,
                    "evidence_role": "robustness",
                    "status": "completed_with_caveats",
                    "paper_table_candidate": "robustness_results_table_with_caveats",
                    "claim_scope": "Scoped robustness only.",
                    "promotion_blockers": [
                        "no final-selection claim",
                        "no fairness claim",
                    ],
                }
            ]
        },
    )
    write_json(
        root / matrix.CLAIM_REGISTER,
        {
            "claims": [
                {
                    "claim_id": "demo_claim",
                    "status": "robustness_evidence_gate_passed_with_caveats",
                }
            ]
        },
    )
    write_json(
        root / matrix.EVIDENCE_VIEW,
        {
            "rows": [
                {
                    "claim_id": "demo_claim",
                    "status": "robustness_evidence_gate_passed_with_caveats",
                    "bundle_ids": ["demo_bundle"],
                }
            ]
        },
    )
    write_json(
        root / matrix.READINESS_MAP,
        {
            "summary": {
                "overall_status": "paper_readiness_blocked_with_evidence_map",
                "final_selection_claim_status": "blocked",
            },
            "blocked_gates": [
                {
                    "gate_id": "final_method_model_selection_gate",
                    "status": "blocked",
                },
                {"gate_id": "multiplicity_selection_record", "status": "blocked"},
                {"gate_id": "dataset_specific_final_gates", "status": "blocked"},
            ],
            "paper_surfaces": [
                {"surface_id": "main_results_table", "status": "blocked"},
                {
                    "surface_id": "robustness_results_table",
                    "status": "caveated_extraction_candidate",
                },
            ],
        },
    )
    write_json(
        root / matrix.PUBLICATION_METHODOLOGY,
        {"summary": {"overall_status": "publication_workbench_ready_with_caveats"}},
    )


def test_bundle_eligibility_matrix_keeps_main_results_blocked(tmp_path):
    write_sources(tmp_path)

    payload = matrix.build_payload(tmp_path)
    row = payload["rows"][0]

    assert (
        payload["summary"]["overall_status"]
        == "bundle_eligibility_matrix_ready_no_final_claims"
    )
    assert payload["summary"]["bundle_count"] == 1
    assert payload["summary"]["manifest_present_count"] == 1
    assert payload["summary"]["claim_linked_bundle_count"] == 1
    assert payload["summary"]["robustness_candidate_count"] == 1
    assert payload["summary"]["caveated_robustness_candidate_count"] == 1
    assert payload["summary"]["main_results_eligible_count"] == 0
    assert payload["summary"]["final_claim_eligible_count"] == 0
    assert row["surface_eligibility"]["robustness_results_table"]["eligible"] is True
    assert (
        row["surface_eligibility"]["robustness_results_table"]["status"]
        == "eligible_with_caveats"
    )
    assert row["surface_eligibility"]["main_results_table"]["eligible"] is False
    assert row["surface_eligibility"]["main_results_table"]["blocking_gates"] == [
        "final_method_model_selection_gate",
        "multiplicity_selection_record",
        "dataset_specific_final_gates",
    ]
    assert row["linked_claim_statuses"] == {
        "demo_claim": "robustness_evidence_gate_passed_with_caveats"
    }


def test_bundle_eligibility_matrix_requires_manifest_presence(tmp_path):
    write_sources(tmp_path, manifest_present=False)

    payload = matrix.build_payload(tmp_path)

    assert (
        payload["summary"]["overall_status"]
        == "bundle_eligibility_matrix_review_required"
    )
    assert payload["summary"]["missing_manifest_count"] == 1
    assert payload["rows"][0]["surface_eligibility"]["dataset_table"]["eligible"] is False


def test_bundle_eligibility_markdown_lists_surface_status(tmp_path):
    write_sources(tmp_path)
    payload = matrix.build_payload(tmp_path)

    markdown = matrix.render_markdown(payload)

    assert "# Bundle Eligibility Matrix" in markdown
    assert "`eligible_with_caveats`" in markdown
    assert "`blocked`" in markdown
    assert "no final-selection claim" in markdown
