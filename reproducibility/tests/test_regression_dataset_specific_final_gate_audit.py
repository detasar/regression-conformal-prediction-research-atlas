import json

from experiments.regression.scripts import (
    audit_dataset_specific_final_gate_readiness as audit,
)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_sources(
    root,
    *,
    main_ready=False,
    evidence_role=None,
    status=None,
    paper_table_candidate=None,
    promotion_blockers=None,
):
    role = evidence_role or ("main_result" if main_ready else "robustness")
    bundle_status = status or ("completed" if main_ready else "completed_with_caveats")
    table_candidate = paper_table_candidate or (
        "main_results_table" if main_ready else "robustness_results_table"
    )
    blockers = (
        promotion_blockers
        if promotion_blockers is not None
        else ([] if main_ready else ["no final-selection claim"])
    )
    bundle = {
        "bundle_id": "demo_bundle",
        "dataset_id": "demo_dataset",
        "target": "y",
        "target_transform": "identity",
        "diagnostic_group": "group",
        "manifest_path": "experiments/regression/reports/demo/publication_readiness_manifest.md",
        "evidence_role": role,
        "status": bundle_status,
        "paper_table_candidate": table_candidate,
        "promotion_blockers": blockers,
    }
    write_json(
        root / audit.BUNDLE_INDEX,
        {"bundle_summary": {"manifest_count": 1}, "bundles": [bundle]},
    )
    write_json(
        root / audit.BUNDLE_ELIGIBILITY,
        {
            "rows": [
                {
                    "bundle_id": "demo_bundle",
                    "dataset_id": "demo_dataset",
                    "evidence_role": role,
                    "status": bundle_status,
                    "paper_table_candidate": table_candidate,
                    "promotion_blockers": blockers,
                    "manifest_present": True,
                    "surface_eligibility": {
                        "main_results_table": {
                            "eligible": main_ready,
                            "status": "eligible" if main_ready else "blocked",
                        }
                    },
                }
            ]
        },
    )
    write_json(
        root / audit.MANIFEST_COMPLETENESS,
        {
            "rows": [
                {
                    "path": bundle["manifest_path"],
                    "status": "pass",
                    "selection_multiplicity_evidence": {"status": "pass"},
                }
            ]
        },
    )
    write_json(
        root / audit.BOUNDED_SUPPORT_DATASET_AUDIT,
        {
            "rows": [
                {
                    "bundle_id": "demo_bundle",
                    "claim_status": "ready" if main_ready else "blocked",
                    "can_support_bounded_support_validity": main_ready,
                }
            ]
        },
    )
    write_json(
        root / audit.FAIRNESS_POPULATION_READINESS,
        {
            "rows": [
                {
                    "bundle_id": "demo_bundle",
                    "fairness_population_claim_status": "ready"
                    if main_ready
                    else "blocked_diagnostic_only_no_population_claim",
                }
            ]
        },
    )
    write_json(
        root / audit.FINAL_SELECTION,
        {"summary": {"claim_status": "ready" if main_ready else "blocked"}},
    )
    write_json(
        root / audit.PAPER_READINESS,
        {
            "summary": {
                "overall_status": "paper_readiness_ready_for_extraction"
                if main_ready
                else "paper_readiness_blocked_with_evidence_map",
                "blocked_gate_count": 0 if main_ready else 6,
            }
        },
    )


def test_dataset_specific_final_gate_blocks_robustness_bundles(tmp_path):
    write_sources(tmp_path, main_ready=False)

    payload = audit.build_payload(tmp_path)
    row = payload["bundle_rows"][0]

    assert (
        payload["summary"]["overall_status"]
        == "dataset_specific_final_gate_audit_completed_no_final_dataset_promotions"
    )
    assert payload["summary"]["main_result_ready_bundle_count"] == 0
    assert row["main_result_promotion_ready"] is False
    assert "not_indexed_as_main_result_bundle" in row["blocking_reasons"]
    assert "final_selection_claim_blocked" in row["blocking_reasons"]


def test_dataset_specific_final_gate_audits_main_result_candidates_without_promotion(tmp_path):
    write_sources(
        tmp_path,
        evidence_role="main_result_candidate_diagnostic",
        status="completed_main_result_candidate_blocked_with_caveats",
        paper_table_candidate="main_results_table_blocked_diagnostic_only",
        promotion_blockers=[
            "candidate evidence is diagnostic and cannot support final method/model selection"
        ],
    )

    payload = audit.build_payload(tmp_path)
    row = payload["bundle_rows"][0]

    assert payload["summary"]["bundle_count"] == 1
    assert payload["summary"]["main_result_candidate_diagnostic_bundle_count"] == 1
    assert payload["summary"]["main_result_ready_bundle_count"] == 0
    assert row["main_result_promotion_ready"] is False
    assert "main_result_candidate_diagnostic_only" in row["blocking_reasons"]
    assert "not_indexed_as_main_result_bundle" not in row["blocking_reasons"]


def test_dataset_specific_final_gate_can_identify_ready_main_result_bundle(tmp_path):
    write_sources(tmp_path, main_ready=True)

    payload = audit.build_payload(tmp_path)
    row = payload["bundle_rows"][0]

    assert payload["summary"]["overall_status"] == "dataset_specific_final_gate_ready"
    assert payload["summary"]["main_result_ready_bundle_count"] == 1
    assert payload["summary"]["main_result_ready_dataset_count"] == 1
    assert row["main_result_promotion_ready"] is True
    assert row["blocking_reasons"] == []


def test_checked_in_dataset_specific_final_gate_stays_blocked_without_promotions():
    payload = audit.build_payload(audit.Path("."))

    assert (
        payload["summary"]["overall_status"]
        == "dataset_specific_final_gate_audit_completed_no_final_dataset_promotions"
    )
    assert payload["summary"]["main_result_ready_bundle_count"] == 0
    assert payload["summary"]["main_result_ready_dataset_count"] == 0
    assert payload["summary"]["bundle_count"] == 15
    assert payload["summary"]["robustness_bundle_count"] == 9
    assert payload["summary"]["main_result_candidate_diagnostic_bundle_count"] == 6
    assert payload["summary"]["eligibility_matrix_bundle_count"] == 15
    assert payload["summary"]["bundle_index_present_count"] == 15
    assert payload["summary"]["missing_bundle_index_count"] == 0
    assert (
        payload["summary"]["blocking_reason_counts"][
            "main_result_candidate_diagnostic_only"
        ]
        == 6
    )
    candidate_rows = [
        row
        for row in payload["bundle_rows"]
        if row["evidence_role"] == "main_result_candidate_diagnostic"
    ]
    assert len(candidate_rows) == 6
    assert all(
        "not_indexed_as_main_result_bundle" not in row["blocking_reasons"]
        for row in candidate_rows
    )
