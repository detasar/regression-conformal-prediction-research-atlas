import json
from pathlib import Path

from experiments.regression.scripts import (
    audit_manuscript_claim_citation_readiness as audit,
)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = (
    ROOT
    / "experiments/regression/manuscript/"
    / "manuscript_claim_citation_readiness_audit.json"
)
KG_QUALITY = ROOT / "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"


def load_artifact():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def load_kg_graph():
    return json.loads(KG_QUALITY.read_text(encoding="utf-8"))["graph"]


def copy_audit_sources(tmp_path):
    for path in audit.SOURCE_PATHS.values():
        src = ROOT / path
        dst = tmp_path / path
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def test_manuscript_claim_citation_readiness_summary_is_clean():
    payload = load_artifact()
    summary = payload["summary"]
    graph = load_kg_graph()

    assert (
        summary["overall_status"]
        == "manuscript_claim_citation_readiness_ready_no_final_prose"
    )
    assert (
        summary["phase_state"]
        == "pre_final_prose_claim_citation_readiness_final_outputs_blocked"
    )
    assert summary["document_count"] == 2
    assert summary["document_pass_count"] == 2
    assert summary["used_unique_citation_key_count"] == 9
    assert summary["unregistered_citation_key_count"] == 0
    assert summary["missing_reference_key_count"] == 0
    assert summary["bibtex_missing_key_count"] == 0
    assert summary["metadata_incomplete_key_count"] == 0
    assert summary["missing_reader_concept_count"] == 0
    assert summary["missing_document_source_key_count"] == 0
    assert summary["document_authorization_violation_count"] == 0
    assert summary["citation_registry_row_count"] == 15
    assert summary["citation_registry_bibtex_entry_count"] == 15
    assert summary["reader_primer_concept_count"] == 12
    assert summary["claim_matrix_verification_row_count"] == 8
    assert summary["claim_matrix_current_draft_artifact_count"] == 6
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["latex_html_authoring_authorized"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["method_champion_authorized"] is False
    assert summary["method_advocacy_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["release_authorized"] is False
    assert summary["kg_node_count"] == graph["node_count"]
    assert summary["kg_edge_count"] == graph["edge_count"]
    assert summary["kg_isolated_node_count"] == graph["isolated_node_count"]
    assert summary["failed_check_count"] == 0


def test_manuscript_claim_citation_readiness_document_rows_are_traceable():
    payload = load_artifact()
    rows = {row["document_id"]: row for row in payload["document_rows"]}

    assert set(rows) == {"main_article_draft", "supplementary_document_draft"}
    assert len(rows["main_article_draft"]["used_citation_keys"]) == 8
    assert len(rows["supplementary_document_draft"]["used_citation_keys"]) == 9
    assert (
        "vanderlaan2025generalized_venn_abers"
        in rows["supplementary_document_draft"]["used_citation_keys"]
    )
    for row in rows.values():
        assert row["readiness_status"] == "pass"
        assert row["unregistered_used_citation_keys"] == []
        assert row["missing_reference_keys"] == []
        assert row["bibtex_missing_keys"] == []
        assert row["metadata_incomplete_keys"] == []
        assert row["missing_concept_ids"] == []
        assert row["missing_required_source_keys"] == []
        assert row["authorization_violations"] == []
        assert row["method_champion_authorized"] is False
        assert row["positive_claim_promotion_authorized"] is False
        assert all(
            concept_row["coverage_status"] == "pass"
            for concept_row in row["concept_rows"]
        )


def test_manuscript_claim_citation_readiness_blocks_unregistered_citation(tmp_path):
    copy_audit_sources(tmp_path)
    article_path = tmp_path / audit.MAIN_ARTICLE_MD
    text = article_path.read_text(encoding="utf-8")
    text = text.replace(
        "under exchangeability [@lei2017distribution_free_regression]",
        "under exchangeability [@missing_citation_key]",
    )
    article_path.write_text(text, encoding="utf-8")

    result = audit.build_payload(tmp_path)
    summary = result["summary"]

    assert summary["overall_status"] == "manuscript_claim_citation_readiness_blocked"
    assert summary["unregistered_citation_key_count"] == 1
    assert summary["document_pass_count"] == 1
    failed_ids = {row["check_id"] for row in result["failed_checks"]}
    assert "document_citations_registered_and_referenced" in failed_ids


def test_manuscript_claim_citation_readiness_ignores_email_addresses():
    text = (
        "Author email: detasar@gmail.com\n"
        "See [@lei2017distribution_free_regression] and "
        "`@romano2019conformalized_quantile_regression`."
    )

    assert audit.citation_keys_from_text(text) == {
        "lei2017distribution_free_regression",
        "romano2019conformalized_quantile_regression",
    }


def test_manuscript_claim_citation_readiness_blocks_missing_reader_concept(tmp_path):
    copy_audit_sources(tmp_path)
    article_path = tmp_path / audit.MAIN_ARTICLE_MD
    text = article_path.read_text(encoding="utf-8")
    text = text.replace("[@romano2019conformalized_quantile_regression]", "")
    article_path.write_text(text, encoding="utf-8")

    result = audit.build_payload(tmp_path)
    summary = result["summary"]

    assert summary["overall_status"] == "manuscript_claim_citation_readiness_blocked"
    assert summary["missing_reader_concept_count"] >= 1
    failed_ids = {row["check_id"] for row in result["failed_checks"]}
    assert "reader_concept_citations_covered" in failed_ids
