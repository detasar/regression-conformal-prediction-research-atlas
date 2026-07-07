import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "experiments/regression/manuscript/supplementary_document_draft.json"
SUPPLEMENT = ROOT / "experiments/regression/manuscript/supplementary_document_draft.md"
REGISTRY = ROOT / "experiments/regression/manuscript/publication_citation_registry.json"
KG_QUALITY = ROOT / "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"


def load_artifact():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_supplementary_document_draft_is_source_backed_and_neutral():
    payload = load_artifact()
    summary = payload["summary"]
    kg_quality = json.loads(KG_QUALITY.read_text(encoding="utf-8"))
    graph = kg_quality["graph"]

    assert summary["overall_status"] == "supplementary_document_draft_ready"
    assert summary["draft_not_final"] is True
    assert summary["author_name"] == "Emre Tasar"
    assert summary["author_role"] == "Data Scientist"
    assert summary["author_email"] == "detasar@gmail.com"
    assert summary["author_header"] == "Author: Emre Tasar, Data Scientist"
    assert summary["publication_completed_rows"] == 145839
    assert summary["dataset_count"] == 67
    assert summary["dataset_alpha_cell_count"] == 95
    assert summary["method_count"] == 28
    assert summary["supplement_blueprint_row_count"] == 5
    assert summary["supplement_section_count"] == 6
    assert summary["supplement_reader_crosswalk_row_count"] == 6
    assert summary["supplement_reading_protocol_row_count"] == 6
    assert summary["failed_check_count"] == 0
    assert len(payload["supplement_reader_crosswalk"]) == 6
    assert {
        row["main_article_surface"] for row in payload["supplement_reader_crosswalk"]
    } == {
        "CQR/CV+ descriptive performance",
        "Venn-Abers bridge negative evidence",
        "Bounded-support validity",
        "Population fairness",
        "Duplicate and leakage integrity",
        "Knowledge-graph traceability and release state",
    }
    assert len(payload["supplement_reading_protocol_rows"]) == 6
    assert {
        row["section_id"] for row in payload["supplement_reading_protocol_rows"]
    } == {"S1", "S2", "S3", "S4", "S5", "S6"}
    assert all(
        row["reader_check"]
        and row["evidence_metric"]
        and row["allowed_use"]
        and row["blocked_use"].startswith("Do not ")
        for row in payload["supplement_reading_protocol_rows"]
    )

    assert summary["candidate_method_count"] == 3
    assert summary["common_dataset_alpha_cell_count"] == 94
    assert summary["common_cell_selected_method"] == "cqr"
    assert summary["common_cell_winner_counts"] == {
        "cqr": 58,
        "cv_plus": 15,
        "mondrian_abs": 21,
    }
    assert summary["bootstrap_selection_counts"] == {"cqr": 1000}
    assert summary["bootstrap_primary_selection_rate"] == 1.0
    assert summary["bootstrap_primary_selection_rate_ci95"] == {
        "low": 0.9961731014136095,
        "high": 1.0,
    }
    assert summary["leave_one_dataset_primary_retention_rate"] == 1.0
    assert summary["leave_one_alpha_primary_retention_rate"] == 1.0
    assert summary["final_selection_claim_status"] == "blocked"
    assert summary["inferential_candidate_min_shared_pairwise_cell_count"] == 94
    assert summary["inferential_pairwise_comparison_count"] == 2
    assert summary["main_result_candidate_primary_win_rate"] == 0.6777777777777778
    assert summary["main_result_candidate_primary_win_rate_ci95"] == {
        "low": 0.5756664407220551,
        "high": 0.765333712728014,
    }
    assert summary["robustness_common_cell_primary_win_rate"] == 0.6170212765957447
    assert summary["post_selection_validation_primary_win_rate"] == 0.72

    assert summary["post_selection_dataset_count"] == 5
    assert summary["post_selection_common_dataset_alpha_cell_count"] == 25
    assert summary["post_selection_completed_atomic_run_count"] == 225
    assert summary["post_selection_diagnostic_winner_counts"] == {
        "cqr": 18,
        "mondrian_abs": 7,
    }
    assert summary["post_selection_feature_leakage_violation_count"] == 0
    assert summary["bridge_validation_completed_atomic_run_count"] == 45
    assert summary["bridge_validation_diagnostic_winner_counts"] == {
        "cqr": 3,
        "cv_plus": 1,
        "mondrian_abs": 1,
    }
    assert summary["venn_undercoverage_run_count"] == 14

    assert summary["bounded_bundle_count"] == 15
    assert summary["bounded_raw_endpoint_excursion_bundle_count"] == 11
    assert summary["bounded_posthandling_validated_bundle_count"] == 15
    assert summary["bounded_support_validity_ready_bundle_count"] == 0
    assert summary["bounded_positive_claim_ready_bundle_count"] == 0
    assert summary["bounded_endpoint_support_status_counts"] == {
        "blocked_natural_domain_endpoint_excursions": 11,
        "clean_no_natural_domain_endpoint_excursions": 3,
        "not_applicable_unbounded_target_endpoint_hygiene_recorded": 1,
    }

    assert summary["fairness_bundle_count"] == 15
    assert summary["fairness_bootstrap_replicates"] == 500
    assert summary["fairness_pairwise_group_comparison_count"] == 187
    assert summary["fairness_population_estimand_declared_bundle_count"] == 0
    assert summary["fairness_protected_attribute_scope_declared_bundle_count"] == 0
    assert summary["fairness_weighted_estimand_applied_bundle_count"] == 0
    assert summary["fairness_sampling_weight_policy_declared_bundle_count"] == 15
    assert summary["fairness_population_ready_bundle_count"] == 0

    assert summary["duplicate_action_count"] == 29
    assert summary["duplicate_open_action_count"] == 0
    assert summary["duplicate_quarantined_action_count"] == 46
    assert summary["duplicate_unquarantined_action_count"] == 0
    assert (
        summary["cross_run_leakage_status"]
        == "hard_leakage_not_detected_in_scanned_artifacts"
    )
    assert summary["cross_run_unsupported_claim_hits"] == 0
    assert summary["cross_run_risk_counts"] == {"medium": 39, "pass": 109}
    assert summary["cross_run_caveat_counts"] == {
        "duplicate_cluster_plus_family_internal_fold_caveat": 17,
        "duplicate_signature_cross_split_caveat": 14,
        "model_visible_signature_cross_split_caveat": 15,
    }

    assert summary["kg_node_count"] == graph["node_count"]
    assert summary["kg_edge_count"] == graph["edge_count"]
    assert summary["kg_isolated_node_count"] == 0
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["method_champion_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["release_authorized"] is False


def test_supplementary_document_draft_uses_registered_citations():
    payload = load_artifact()
    supplement = SUPPLEMENT.read_text(encoding="utf-8")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    registered = {row["citation_key"] for row in registry["citation_rows"]}
    cited = set(re.findall(r"\[@([A-Za-z0-9_]+)", supplement))
    cited.update(re.findall(r"; @([A-Za-z0-9_]+)", supplement))
    cited.update(re.findall(r"`@([A-Za-z0-9_]+)`", supplement))

    assert cited
    assert cited.issubset(registered)
    for required_key in [
        "lei2017distribution_free_regression",
        "romano2019conformalized_quantile_regression",
        "barber2020jackknife_plus",
        "kim2020jackknife_after_bootstrap",
        "tibshirani2020covariate_shift",
        "nouretdinov2018ivapd",
        "nouretdinov2024ivapd_applications",
        "vanderlaan2025generalized_venn_abers",
        "petej2026inductive_venn_abers_regressors",
    ]:
        assert required_key in cited
        assert required_key in payload["citation_keys"].values()


def test_supplementary_document_draft_markdown_keeps_claim_boundaries_visible():
    supplement = SUPPLEMENT.read_text(encoding="utf-8")

    for heading in [
        "## Supplement Reader Crosswalk",
        "## Supplement Reading Protocol",
        "## S1. Method Selection Robustness Diagnostics",
        "## S2. Post-Selection Validation Diagnostics",
        "## S3. Bounded-Support Endpoint Policy",
        "## S4. Fairness Group Diagnostics",
        "## S5. Duplicate And Integrity Caveats",
        "## S6. Traceability And Release State",
        "## Claim Boundaries",
        "## References",
        "## Source Artifacts",
    ]:
        assert heading in supplement

    assert "not final manuscript prose" in supplement
    assert "how the supplement should be read with the main article" in supplement
    assert "The supplement is intentionally broader than the main article" in supplement
    assert "| Section | Reviewer check | Evidence metric | Allowed use | Blocked use |" in supplement
    assert "Check whether the method-selection signal is robust enough to describe" in supplement
    assert "Do not call CQR the final selected method or a universal recommendation" in supplement
    assert "CQR/CV+ descriptive performance" in supplement
    assert "`method_selection_robustness_audit`" in supplement
    assert "No validated Venn-Abers regression interval claim" in supplement
    assert "No public citable KG/site/repository release" in supplement
    assert "final-selection gate remains closed" in supplement
    assert "post-selection diagnostics are stress tests" in supplement
    assert "The confidence intervals quantify diagnostic uncertainty" in supplement
    assert "predictive-distribution and generalized Venn-Abers work remain separate literature objects" in supplement
    assert "Not a final winner" in supplement
    assert "No bounded-support validity claim" in supplement
    assert "reports endpoint closure as a limitation" in supplement
    assert "No population fairness claim" in supplement
    assert "fairness is an estimand-level claim" in supplement
    assert "the caveats still travel with the empirical interpretation" in supplement
    assert "no final winner or recommendation is authorized" in supplement
    assert "does not claim that the current interval bridge validates" in supplement
    assert "best regression conformal method" not in supplement.lower()
