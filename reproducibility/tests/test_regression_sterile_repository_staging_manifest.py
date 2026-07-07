import json
from pathlib import Path

from experiments.regression.scripts import (
    build_sterile_repository_staging_manifest as manifest,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (
    ROOT
    / "experiments/regression/manuscript/"
    / "sterile_repository_staging_manifest.json"
)


def load_checked_in_payload():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def copy_sources(tmp_path: Path) -> None:
    for source in manifest.SOURCE_PATHS.values():
        source_path = ROOT / source
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")


def test_checked_in_sterile_repository_manifest_is_staging_only():
    payload = load_checked_in_payload()
    summary = payload["summary"]

    assert summary["overall_status"] == (
        "sterile_repository_staging_manifest_ready_no_repository_created"
    )
    assert summary["phase_state"] == (
        "neutral_sterile_repository_manifest_ready_creation_blocked"
    )
    assert summary["required_content_row_count"] == 9
    assert summary["required_content_traceable_count"] == 9
    assert summary["required_content_with_blocking_gate_count"] == 9
    assert summary["candidate_inclusion_risk_hit_count"] == 0
    assert summary["post_program_exclusion_rule_count"] == 3
    assert summary["expanded_exclusion_rule_count"] == 9
    assert summary["exclusion_policy_row_count"] == 12
    assert summary["exclusion_source_traceable_count"] == 12
    assert summary["source_artifact_count"] == 11
    assert summary["missing_source_artifact_count"] == 0
    assert summary["private_repository_created"] is False
    assert summary["sterile_repository_creation_authorized"] is False
    assert summary["sterile_release_packaging_authorized"] is False
    assert summary["release_authorized"] is False
    assert summary["working_repository_final_citable"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["analysis_only_no_champion_method"] is True
    assert summary["method_champion_authorized"] is False
    assert summary["method_advocacy_authorized"] is False
    assert (
        summary["result_reporting_policy"]
        == "analysis_only_report_observed_behavior_no_method_advocacy"
    )
    assert summary["authorization_violation_count"] == 0
    assert summary["kg_node_count"] >= 3410
    assert summary["kg_edge_count"] >= 19482
    assert summary["kg_isolated_node_count"] == 0
    assert summary["kg_total_observation_count"] >= 8308
    assert summary["failed_check_count"] == 0


def test_required_content_rows_have_sources_and_blocking_gates():
    payload = load_checked_in_payload()
    rows = payload["required_content_rows"]
    rows_by_id = {row["content_id"]: row for row in rows}

    assert len(rows) == 9
    for row in rows:
        assert row["source_traceability_status"] == "pass"
        assert row["source_artifacts"]
        assert row["blocking_gate"]
        assert row["final_content_authorized"] is False
        assert row["release_authorized"] is False
        assert row["candidate_exclusion_risk_hits"] == []

    assert {
        "experiments/regression/manuscript/sterile_repository_readme_draft.md",
        "experiments/regression/manuscript/sterile_repository_readme_draft.json",
    }.issubset(set(rows_by_id["polished_readme"]["source_artifacts"]))
    assert {
        "experiments/regression/manuscript/main_article_draft.md",
        "experiments/regression/manuscript/main_article_draft.json",
    }.issubset(set(rows_by_id["main_article_outputs"]["source_artifacts"]))
    assert {
        "experiments/regression/manuscript/supplementary_document_draft.md",
        "experiments/regression/manuscript/supplementary_document_draft.json",
    }.issubset(set(rows_by_id["supplementary_document_outputs"]["source_artifacts"]))
    assert {
        "experiments/regression/manuscript/individual_experiment_report_draft.md",
        "experiments/regression/manuscript/individual_experiment_report_draft.json",
    }.issubset(set(rows_by_id["individual_experiment_report"]["source_artifacts"]))
    assert {
        "experiments/regression/manuscript/publication_citation_registry.json",
        "experiments/regression/manuscript/publication_citation_registry.md",
        "experiments/regression/manuscript/references.bib",
    }.issubset(
        set(rows_by_id["citation_metadata_and_release_notes"]["source_artifacts"])
    )


def test_manifest_blocks_if_sterile_repository_authorization_is_opened(tmp_path):
    copy_sources(tmp_path)

    auth_path = tmp_path / manifest.FINAL_AUTHORIZATION
    payload = json.loads(auth_path.read_text(encoding="utf-8"))
    payload["summary"]["sterile_repository_creation_authorized"] = True
    auth_path.write_text(json.dumps(payload), encoding="utf-8")

    result = manifest.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in result["checks"]}

    assert result["summary"]["overall_status"] == (
        "sterile_repository_staging_manifest_blocked"
    )
    assert result["summary"]["authorization_violation_count"] == 1
    assert checks["final_authorizations_remain_closed"]["status"] == "fail"


def test_manifest_blocks_if_post_program_exclusion_rules_are_missing(tmp_path):
    copy_sources(tmp_path)

    post_program_path = tmp_path / manifest.POST_PROGRAM
    payload = json.loads(post_program_path.read_text(encoding="utf-8"))
    payload["sterile_publication_repository_plan"]["exclusion_rules"] = []
    post_program_path.write_text(json.dumps(payload), encoding="utf-8")

    result = manifest.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in result["checks"]}

    assert result["summary"]["overall_status"] == (
        "sterile_repository_staging_manifest_blocked"
    )
    assert result["summary"]["post_program_exclusion_rule_count"] == 0
    assert checks["exclusion_policy_complete"]["status"] == "fail"


def test_manifest_blocks_if_champion_method_policy_is_missing(tmp_path):
    copy_sources(tmp_path)

    auth_path = tmp_path / manifest.FINAL_AUTHORIZATION
    payload = json.loads(auth_path.read_text(encoding="utf-8"))
    payload["summary"]["analysis_only_no_champion_method"] = False
    payload["summary"]["method_champion_authorized"] = True
    auth_path.write_text(json.dumps(payload), encoding="utf-8")

    result = manifest.build_payload(tmp_path)
    checks = {row["check_id"]: row for row in result["checks"]}

    assert result["summary"]["overall_status"] == (
        "sterile_repository_staging_manifest_blocked"
    )
    assert result["summary"]["analysis_only_no_champion_method"] is False
    assert result["summary"]["authorization_violation_count"] == 1
    assert checks["final_authorizations_remain_closed"]["status"] == "fail"
    assert checks["neutral_scientific_reporting_guards_present"]["status"] == "fail"
