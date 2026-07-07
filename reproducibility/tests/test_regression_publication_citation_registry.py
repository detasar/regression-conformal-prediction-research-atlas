import json
from pathlib import Path

from experiments.regression.scripts import build_publication_citation_registry as registry


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "experiments/regression/manuscript/publication_citation_registry.json"
BIBTEX = ROOT / "experiments/regression/manuscript/references.bib"


def load_artifact():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_publication_citation_registry_is_complete_and_pre_prose():
    payload = load_artifact()
    summary = payload["summary"]

    assert summary["overall_status"] == (
        "publication_citation_registry_ready_no_final_prose"
    )
    assert summary["phase_state"] == (
        "pre_prose_citation_metadata_registry_final_outputs_blocked"
    )
    assert summary["citation_row_count"] == 15
    assert summary["bibtex_entry_count"] == 15
    assert summary["primer_primary_url_covered_count"] == 14
    assert summary["primer_primary_url_count"] == 14
    assert summary["literature_primary_url_covered_count"] == 15
    assert summary["literature_primary_url_count"] == 15
    assert summary["expected_upstream_url_count"] == 15
    assert summary["registry_url_count"] == 15
    assert summary["failed_check_count"] == 0
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["method_champion_authorized"] is False
    assert summary["method_advocacy_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False


def test_publication_citation_registry_covers_required_method_sources():
    payload = load_artifact()
    rows = {row["citation_key"]: row for row in payload["citation_rows"]}

    cqr = rows["romano2019conformalized_quantile_regression"]
    assert cqr["url"] == "https://arxiv.org/abs/1905.03222"
    assert cqr["source_role"] == "primer_and_literature"
    assert cqr["covered_primer_concept_ids"] == [
        "alpha_and_nominal_coverage",
        "conformalized_quantile_regression_cqr",
        "result_metrics_and_claim_boundaries",
    ]
    assert cqr["covered_literature_requirement_ids"] == [
        "conformalized_quantile_regression"
    ]

    cv_plus = rows["barber2020jackknife_plus"]
    assert cv_plus["url"] == "https://arxiv.org/abs/1905.02928"
    assert cv_plus["covered_primer_concept_ids"] == ["jackknife_plus_and_cv_plus"]
    assert cv_plus["covered_literature_requirement_ids"] == [
        "plus_family_and_resampling"
    ]

    venn = rows["nouretdinov2018ivapd"]
    assert venn["url"] == "https://proceedings.mlr.press/v91/nouretdinov18a.html"
    assert venn["covered_primer_concept_ids"] == [
        "venn_abers_predictive_distributions"
    ]
    assert venn["covered_literature_requirement_ids"] == [
        "venn_abers_predictive_distribution"
    ]

    crc = rows["angelopoulos2025conformal_risk_control"]
    assert crc["source_role"] == "literature"
    assert crc["covered_primer_concept_ids"] == []
    assert crc["covered_literature_requirement_ids"] == [
        "conformal_risk_control_boundary"
    ]


def test_publication_citation_registry_bibtex_is_key_complete():
    payload = load_artifact()
    bibtex = BIBTEX.read_text(encoding="utf-8")
    keys = [row["citation_key"] for row in payload["citation_rows"]]

    assert len(keys) == len(set(keys)) == 15
    assert bibtex.count("@") == 15
    for row in payload["citation_rows"]:
        assert f"@{row['entry_type']}{{{row['citation_key']}," in bibtex
        assert row["bibtex"] in bibtex
        assert row["claim_use_boundary"].startswith("Citation metadata only")


def test_publication_citation_registry_blocks_missing_upstream_url(tmp_path):
    for path in [registry.READER_METHOD_PRIMER, registry.METHOD_LITERATURE_AUDIT]:
        src = ROOT / path
        dst = tmp_path / path
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    primer_path = tmp_path / registry.READER_METHOD_PRIMER
    primer_payload = json.loads(primer_path.read_text(encoding="utf-8"))
    primer_payload["concept_rows"][0]["primary_source_urls"].append(
        "https://example.invalid/missing-source"
    )
    primer_path.write_text(json.dumps(primer_payload), encoding="utf-8")

    result = registry.build_payload(tmp_path)
    summary = result["summary"]

    assert summary["overall_status"] == "publication_citation_registry_blocked"
    assert summary["failed_check_count"] == 2
    failed_ids = {row["check_id"] for row in result["failed_checks"]}
    assert "primer_primary_urls_all_covered" in failed_ids
    assert "registry_urls_exactly_match_upstream_union" in failed_ids
