import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_cqr_backend_aliases_are_method_config_nodes():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    for dataset_slug, suffix in [
        ("cholesterol", "sex_log1p_age_diagnosis_drop"),
        ("plasma_retinol", "sex_log1p_age_drop"),
    ]:
        experiment = f"regression_cqr_backend_sweep_openml_{dataset_slug}_{suffix}_v0"
        report_id = f"report:cqr_backend_sweep_openml_{dataset_slug}_{suffix}"
        config_id = f"config:{experiment}"
        method_config_id = f"method_config:{experiment}:cqr_gb_deep_n200_d4_lr003"

        assert nodes[method_config_id]["type"] == "method_config"
        assert nodes[method_config_id]["method_id"] == "cqr"
        assert (
            config_id,
            "QUEUES_METHOD_CONFIG",
            method_config_id,
        ) in edges
        assert (method_config_id, "CONFIGURES_METHOD", "method:cqr") in edges
        assert (
            report_id,
            "EVALUATES_METHOD_CONFIG",
            method_config_id,
        ) in edges
        assert (report_id, "EVALUATES_METHOD", "method:cqr") in edges
        assert (
            report_id,
            "EVALUATES_METHOD",
            "method:cqr_gb_deep_n200_d4_lr003",
        ) not in edges


def test_bounded_support_endpoint_closure_audit_links_gate_and_sources():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    report_id = "report:bounded_support_endpoint_closure_audit"
    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "bounded_support_endpoint_closure_audit.json"
    )
    assert "15 closed policy bundle" in nodes[report_id]["summary"]
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    for source_id in [
        "report:bounded_support_protocol",
        "report:target_domain_provenance",
        "report:bounded_support_posthandling_validation",
        "report:bounded_support_dataset_audit",
        "report:manuscript_readiness_map",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
    assert (
        "claim_requirement:final_selection_and_fairness_claims_blocked:endpoint_bounded_support_gate",
        "SUPPORTED_BY",
        report_id,
    ) in edges
    assert (
        "paper_gate:endpoint_bounded_support_gate",
        "DERIVED_FROM",
        report_id,
    ) in edges
    assert (report_id, "SUMMARIZES_DATASET", "dataset:uci_wine_quality") in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:duplicate_cluster_sensitivity_uci_wine_quality_duplicate_sensitivity_row_signature:endpoint_audit",
    ) in edges


def test_bounded_support_positive_validation_links_no_claim_evidence():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    catalog_id = "catalog:bounded_support_positive_validation_protocol"
    report_id = "report:bounded_support_positive_validation_protocol"
    claim_requirement_id = (
        "claim_requirement:final_selection_and_fairness_claims_blocked:"
        "endpoint_bounded_support_gate"
    )

    assert nodes[catalog_id]["type"] == "catalog"
    assert nodes[catalog_id]["json_path"].endswith(
        "experiments/regression/manuscript/"
        "bounded_support_positive_validation_protocol.json"
    )
    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "experiments/regression/manuscript/"
        "bounded_support_positive_validation_protocol.json"
    )
    assert "no-claim evidence" in nodes[report_id]["summary"]
    assert "0 claim-ready bundle" in nodes[report_id]["summary"]
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    for source_id in [
        catalog_id,
        "report:bounded_support_protocol",
        "report:bounded_support_dataset_audit",
        "report:bounded_support_posthandling_validation",
        "report:bounded_support_endpoint_closure_audit",
        "report:manuscript_readiness_map",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
    assert (claim_requirement_id, "SUPPORTED_BY", report_id) in edges
    assert ("paper_gate:endpoint_bounded_support_gate", "DERIVED_FROM", report_id) in edges
    assert (report_id, "SUMMARIZES_DATASET", "dataset:uci_wine_quality") in edges


def test_fairness_group_multiplicity_scope_links_gate_claim_and_sources():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    report_id = "report:fairness_group_multiplicity_scope"
    action_id = (
        "methodology_control:paper_gate_execution:"
        "fairness_population_inference_gate_declare_group_comparison_multiplicity_scope"
    )
    claim_requirement_id = (
        "claim_requirement:final_selection_and_fairness_claims_blocked:"
        "fairness_population_inference_gate"
    )
    execution_plan_id = "report:paper_gate_closure_execution_plan"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "fairness_group_multiplicity_scope.json"
    )
    assert "Diagnostic group-comparison multiplicity scope" in nodes[report_id]["summary"]
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    for source_id in [
        "report:fairness_group_diagnostic_audit",
        "report:fairness_sampling_weight_policy",
        "catalog:manuscript_claim_register",
        "report:paper_gate_closure_execution_plan",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
    assert (report_id, "SUMMARIZES_CONTROL", action_id) in edges
    assert (
        execution_plan_id,
        "SUMMARIZES_CONTROL",
        "paper_gate:fairness_population_inference_gate",
    ) in edges
    assert (claim_requirement_id, "SUPPORTED_BY", report_id) in edges
    assert (report_id, "SUMMARIZES_DATASET", "dataset:uci_wine_quality") in edges


def test_article_supplement_kg_navigation_index_links_boundaries_and_release_blockers():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }

    report_id = "report:article_supplement_kg_navigation_index"
    main_row_id = (
        "methodology_control:article_supplement_kg_navigation_index:"
        "paper_main_results_blocked_evidence"
    )
    negative_row_id = (
        "methodology_control:article_supplement_kg_navigation_index:"
        "supplement_venn_abers_negative_evidence"
    )
    kg_site_row_id = (
        "methodology_control:article_supplement_kg_navigation_index:"
        "kg_site_navigation_candidate"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "article_supplement_kg_navigation_index.json"
    )
    assert "without final prose" in nodes[report_id]["summary"]
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    for source_id in [
        "report:section_claim_boundary_audit",
        "report:publication_release_gap_register",
        "report:publication_visual_table_render_candidate_audit",
        "report:kg_navigation_usability_audit",
        "report:knowledge_graph_quality_summary",
        "report:neutral_reporting_language_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges

    for node_id in [main_row_id, negative_row_id, kg_site_row_id]:
        assert nodes[node_id]["type"] == "methodology_control"
        assert nodes[node_id]["method_recommendation_authorized"] is False
        assert nodes[node_id]["positive_claim_promotion_authorized"] is False
        assert (report_id, "SUMMARIZES_CONTROL", node_id) in edges

    assert nodes[main_row_id]["main_results_positive_boundary_blocked"] is True
    assert (
        main_row_id,
        "DERIVED_FROM",
        "methodology_control:section_claim_boundary_audit:"
        "paper_main_results_blocked_evidence",
    ) in edges
    assert (
        main_row_id,
        "DERIVED_FROM",
        "methodology_control:publication_release_gap:main_article_latex",
    ) in edges

    assert nodes[negative_row_id]["venn_abers_negative_boundary_preserved"] is True
    assert (
        negative_row_id,
        "DERIVED_FROM",
        "methodology_control:neutral_result_ledger:"
        "venn_abers_regression_negative_evidence",
    ) in edges

    assert nodes[kg_site_row_id]["release_authorized"] is False
    assert (
        kg_site_row_id,
        "DERIVED_FROM",
        "report:kg_navigation_usability_audit",
    ) in edges
    assert (
        kg_site_row_id,
        "DERIVED_FROM",
        "methodology_control:publication_release_gap:"
        "article_supplement_kg_navigation_index",
    ) in edges


def test_publication_phase_progress_reconciliation_links_resolved_and_active_blockers():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }

    report_id = "report:publication_phase_progress_reconciliation_audit"
    reviewer_control = (
        "methodology_control:publication_phase_progress_reconciliation:"
        "reviewer_design_and_reconciliation_ready"
    )
    visual_control = (
        "methodology_control:publication_phase_progress_reconciliation:"
        "visual_table_pre_retention_and_render_audits_ready"
    )
    resolved_reviewer = (
        "methodology_control:publication_phase_progress_resolved_blocker:"
        "reviewer_design_reconciliation_pending"
    )
    active_sterile = (
        "methodology_control:publication_phase_progress_active_blocker:"
        "sterile_repository_creation_not_authorized"
    )
    active_positive = (
        "methodology_control:publication_phase_progress_active_blocker:"
        "positive_claim_promotion_not_authorized"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "publication_phase_progress_reconciliation_audit.json"
    )
    assert "still-active final prose" in nodes[report_id]["summary"]
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    for source_id in [
        "report:goal_completion_audit",
        "report:publication_release_gap_register",
        "report:article_supplement_kg_navigation_index",
        "report:neutral_reporting_language_audit",
        "report:kg_publication_quality_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges

    for node_id in [reviewer_control, visual_control]:
        assert nodes[node_id]["type"] == "methodology_control"
        assert nodes[node_id]["status"] == "complete"
        assert nodes[node_id]["method_recommendation_authorized"] is False
        assert nodes[node_id]["positive_claim_promotion_authorized"] is False
        assert (report_id, "SUMMARIZES_CONTROL", node_id) in edges

    assert nodes[resolved_reviewer]["status"] == "resolved"
    assert (
        resolved_reviewer,
        "DERIVED_FROM",
        reviewer_control,
    ) in edges
    for node_id in [active_sterile, active_positive]:
        assert nodes[node_id]["status"] == "active"
        assert nodes[node_id]["method_recommendation_authorized"] is False
        assert nodes[node_id]["positive_claim_promotion_authorized"] is False
        assert (report_id, "SUMMARIZES_CONTROL", node_id) in edges
        assert (
            node_id,
            "DERIVED_FROM",
            "report:publication_release_gap_register",
        ) in edges


def test_scientific_neutrality_interpretation_lock_links_rows_and_sources():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }

    report_id = "report:scientific_neutrality_interpretation_lock"
    method_row = (
        "methodology_control:scientific_neutrality_interpretation_lock:"
        "method_frontier_cqr_cvplus"
    )
    venn_row = (
        "methodology_control:scientific_neutrality_interpretation_lock:"
        "venn_abers_negative_result"
    )
    sterile_row = (
        "methodology_control:scientific_neutrality_interpretation_lock:"
        "sterile_repository_and_manuscript_outputs"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "scientific_neutrality_interpretation_lock.json"
    )
    assert "without final prose" in nodes[report_id]["summary"]
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    for source_id in [
        "report:publication_phase_progress_reconciliation_audit",
        "report:neutral_reporting_language_audit",
        "report:method_performance_synthesis",
        "report:venn_abers_negative_evidence_disposition_audit",
        "report:publication_release_gap_register",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges

    for node_id in [method_row, venn_row, sterile_row]:
        assert nodes[node_id]["type"] == "methodology_control"
        assert nodes[node_id]["final_prose_authorized"] is False
        assert nodes[node_id]["method_recommendation_authorized"] is False
        assert nodes[node_id]["positive_claim_promotion_authorized"] is False
        assert (report_id, "SUMMARIZES_CONTROL", node_id) in edges

    assert "global best method" in nodes[method_row]["blocked_interpretation"]
    assert "negative/failure-mode" in nodes[venn_row]["allowed_interpretation"]
    assert (
        method_row,
        "DERIVED_FROM",
        "report:method_performance_synthesis",
    ) in edges
    assert (
        venn_row,
        "DERIVED_FROM",
        "report:venn_abers_validation_readiness_audit",
    ) in edges
    assert (
        sterile_row,
        "DERIVED_FROM",
        "report:publication_release_gap_register",
    ) in edges


def test_high_volume_kg_edges_have_fact_level_selectors():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    edges = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }

    config_id = (
        "config:regression_duplicate_cluster_sensitivity_nhanes_2017_2018_bmi_"
        "identity_ridreth3_model_visible_v0"
    )
    report_id = (
        "report:duplicate_cluster_sensitivity_nhanes_2017_2018_bmi_"
        "identity_ridreth3_model_visible"
    )
    manifest_id = (
        "manifest:duplicate_cluster_sensitivity_nhanes_2017_2018_bmi_"
        "identity_ridreth3_model_visible:publication_readiness"
    )

    config_method_edge = edges[(config_id, "QUEUES_METHOD", "method:cqr")]
    assert config_method_edge["provenance_granularity"] == "fact_selector"
    assert config_method_edge["evidence"] == 'cp_methods[?value == "cqr"]'
    assert config_method_edge["evidence_path"].endswith(
        "duplicate_cluster_sensitivity_nhanes_2017_2018_bmi_identity_ridreth3_model_visible.yaml"
    )

    report_method_edge = edges[(report_id, "EVALUATES_METHOD", "method:cqr")]
    assert report_method_edge["provenance_granularity"] == "fact_selector"
    assert report_method_edge["evidence"] == 'rows[?(@.cp_method == "cqr")]'
    assert report_method_edge["evidence_path"].endswith("pilot_summary.json")

    manifest_report_edge = edges[(manifest_id, "MANIFESTS_REPORT", report_id)]
    assert manifest_report_edge["provenance_granularity"] == "fact_selector"
    assert manifest_report_edge["evidence"] == "markdown_heading:Identity"
    assert manifest_report_edge["evidence_path"].endswith(
        "publication_readiness_manifest.md"
    )


def test_artifact_root_selectors_are_distinct_from_fact_selectors():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    edges = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }

    profile_edge = edges[
        (
            "audit:nhanes_2017_2018_bmi",
            "HAS_PROFILE",
            "profile:nhanes_2017_2018_bmi",
        )
    ]

    assert profile_edge["provenance_granularity"] == "artifact_root_inferred_selector"
    assert profile_edge["evidence_kind"] == "artifact_root_selector"
    assert profile_edge["evidence"] == "$"
    assert profile_edge["evidence_path"].endswith(
        "experiments/regression/audits/nhanes_2017_2018_bmi/profile.json"
    )
    assert profile_edge["confidence"] == 0.94


def test_brfss_source_review_is_connected_to_audit_index_and_source():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    dataset_id = "dataset:brfss_2024_llcp_source_review"
    audit_id = "audit:brfss_2024_llcp_source_review"
    source_id = "source:CDC Behavioral Risk Factor Surveillance System"

    assert nodes[dataset_id]["type"] == "dataset"
    assert nodes[dataset_id]["source"] == "CDC Behavioral Risk Factor Surveillance System"
    assert nodes[audit_id]["type"] == "audit"
    assert nodes[audit_id]["status"] == "source_review_only_modeling_blocked"
    assert nodes[source_id]["type"] == "source"
    assert nodes[source_id]["url"] == "https://www.cdc.gov/brfss/annual_data/annual_2024.html"
    assert (dataset_id, "HAS_AUDIT", audit_id) in edges
    assert (dataset_id, "FROM_SOURCE", source_id) in edges
    assert (dataset_id, "RECORDED_IN", "catalog:audit_index") in edges


def test_wdi_source_review_is_connected_to_audit_index_and_source():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    dataset_id = "dataset:world_bank_wdi_source_review"
    audit_id = "audit:world_bank_wdi_source_review"
    source_id = "source:World Bank World Development Indicators"

    assert nodes[dataset_id]["type"] == "dataset"
    assert nodes[dataset_id]["source"] == "World Bank World Development Indicators"
    assert nodes[audit_id]["type"] == "audit"
    assert nodes[audit_id]["status"] == "source_review_only_modeling_blocked"
    assert nodes[source_id]["type"] == "source"
    assert nodes[source_id]["url"] == (
        "https://databank.worldbank.org/source/world-development-indicators"
    )
    assert (dataset_id, "HAS_AUDIT", audit_id) in edges
    assert (dataset_id, "FROM_SOURCE", source_id) in edges
    assert (dataset_id, "RECORDED_IN", "catalog:audit_index") in edges


def test_ipums_cps_source_review_is_connected_to_audit_index_and_source():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    dataset_id = "dataset:ipums_cps_source_review"
    audit_id = "audit:ipums_cps_source_review"
    source_id = "source:IPUMS CPS harmonized Current Population Survey microdata"

    assert nodes[dataset_id]["type"] == "dataset"
    assert nodes[dataset_id]["source"] == (
        "IPUMS CPS harmonized Current Population Survey microdata"
    )
    assert nodes[audit_id]["type"] == "audit"
    assert nodes[audit_id]["status"] == "source_review_only_modeling_blocked"
    assert nodes[source_id]["type"] == "source"
    assert nodes[source_id]["url"] == "https://cps.ipums.org/cps/"
    assert (dataset_id, "HAS_AUDIT", audit_id) in edges
    assert (dataset_id, "FROM_SOURCE", source_id) in edges
    assert (dataset_id, "RECORDED_IN", "catalog:audit_index") in edges


def test_icpsr_openicpsr_source_review_is_connected_to_audit_index_and_source():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    dataset_id = "dataset:icpsr_openicpsr_source_review"
    audit_id = "audit:icpsr_openicpsr_source_review"
    source_id = "source:ICPSR and openICPSR research data repositories"

    assert nodes[dataset_id]["type"] == "dataset"
    assert nodes[dataset_id]["source"] == (
        "ICPSR and openICPSR research data repositories"
    )
    assert nodes[audit_id]["type"] == "audit"
    assert nodes[audit_id]["status"] == "source_review_only_modeling_blocked"
    assert nodes[source_id]["type"] == "source"
    assert nodes[source_id]["url"] == (
        "https://www.icpsr.umich.edu/sites/icpsr/find-data"
    )
    assert (dataset_id, "HAS_AUDIT", audit_id) in edges
    assert (dataset_id, "FROM_SOURCE", source_id) in edges
    assert (dataset_id, "RECORDED_IN", "catalog:audit_index") in edges


def test_datagov_source_review_is_connected_to_audit_index_and_source():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    dataset_id = "dataset:datagov_source_review"
    audit_id = "audit:datagov_source_review"
    source_id = "source:Data.gov catalog metadata portal"

    assert nodes[dataset_id]["type"] == "dataset"
    assert nodes[dataset_id]["source"] == "Data.gov catalog metadata portal"
    assert nodes[audit_id]["type"] == "audit"
    assert nodes[audit_id]["status"] == "source_review_only_modeling_blocked"
    assert nodes[source_id]["type"] == "source"
    assert nodes[source_id]["url"] == "https://catalog.data.gov/"
    assert (dataset_id, "HAS_AUDIT", audit_id) in edges
    assert (dataset_id, "FROM_SOURCE", source_id) in edges
    assert (dataset_id, "RECORDED_IN", "catalog:audit_index") in edges


def test_datagov_source_review_report_is_metadata_only_and_modeling_blocked():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:datagov_source_review"
    dataset_id = "dataset:datagov_source_review"
    audit_id = "audit:datagov_source_review"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["report_status"] == "source_review_report_modeling_blocked"
    assert nodes[report_id]["json_path"].endswith("source_review_report.json")
    assert nodes[report_id]["path"].endswith("source_review_report.md")
    assert (report_id, "SUMMARIZES_DATASET", dataset_id) in edges
    assert (report_id, "DERIVED_FROM", audit_id) in edges
    dataset_edge = edge_by_triple[(report_id, "SUMMARIZES_DATASET", dataset_id)]
    assert dataset_edge["evidence_path"].endswith("source_review_report.json")


def test_source_review_reports_are_metadata_only_and_not_method_reports():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    outgoing = {}
    for source, relation, target in edge_by_triple:
        outgoing.setdefault((source, relation), set()).add(target)

    dataset_ids = [
        "brfss_2024_llcp_source_review",
        "datagov_source_review",
        "icpsr_openicpsr_source_review",
        "ipums_cps_source_review",
        "world_bank_wdi_source_review",
    ]
    for dataset_id_value in dataset_ids:
        report_id = f"report:{dataset_id_value}"
        dataset_id = f"dataset:{dataset_id_value}"
        audit_id = f"audit:{dataset_id_value}"
        assert nodes[report_id]["type"] == "report"
        assert nodes[report_id]["report_status"] == "source_review_report_modeling_blocked"
        assert nodes[report_id]["json_path"].endswith("source_review_report.json")
        assert (report_id, "SUMMARIZES_DATASET", dataset_id) in edge_by_triple
        assert (report_id, "DERIVED_FROM", audit_id) in edge_by_triple
        assert outgoing.get((report_id, "EVALUATES_METHOD"), set()) == set()
        assert outgoing.get((report_id, "EVALUATES_METHOD_CONFIG"), set()) == set()
        assert outgoing.get((report_id, "EVALUATES_MODEL"), set()) == set()


def test_core_regression_methods_have_specs_and_stackoverflow_sidecars():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    spec_id = "method_spec:split_and_cqr_regression"
    assert nodes[spec_id]["type"] == "method_spec"
    for method_id in ["split_abs", "mondrian_abs", "normalized_abs", "cqr"]:
        assert (f"method:{method_id}", "SPECIFIED_BY", spec_id) in edges
    assert ("method:shrink_gamma", "SPECIFIED_BY", spec_id) in edges
    assert (
        "method:split_tail_grid_shortest",
        "SPECIFIED_BY",
        "method_spec:tail_specific_split_regression",
    ) in edges
    assert (
        "method:conformal_risk_control",
        "SPECIFIED_BY",
        "method_spec:risk_control_and_boundary_methods",
    ) in edges
    assert (
        "method:venn_abers_classification",
        "SPECIFIED_BY",
        "method_spec:risk_control_and_boundary_methods",
    ) in edges

    report_id = "report:model_family_sweep_stackoverflow_2025_compensation_log1p_age"
    assert report_id in nodes
    for sidecar in [
        "pre_run_profile",
        "split_profile",
        "feature_leakage_audit",
        "runtime_cap_audit",
        "experiment_notes",
    ]:
        sidecar_id = f"{report_id}:{sidecar}"
        assert nodes[sidecar_id]["type"] == "report"
        assert (sidecar_id, "SUPPORTS_REPORT", report_id) in edges

    assert (
        f"{report_id}:pre_run_profile",
        "SUMMARIZES_DATASET",
        "dataset:stackoverflow_2025_compensation",
    ) in edges


def test_method_literature_coverage_audit_links_boundary_method_families():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    spec_id = "method_spec:distributional_and_full_conformal_regression"
    audit_id = "report:method_literature_coverage_audit"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[spec_id]["type"] == "method_spec"
    assert nodes[spec_id]["path"].endswith(
        "experiments/regression/method_specs/distributional_and_full_conformal_regression.md"
    )
    for method_id in [
        "full_conformal_regression",
        "rank_one_out_conformal",
        "distributional_conformal_prediction",
        "conformal_predictive_system",
        "tail_allocation_shortest_interval",
    ]:
        node_id = f"method:{method_id}"
        assert nodes[node_id]["type"] == "method"
        assert (node_id, "SPECIFIED_BY", spec_id) in edges
        assert (audit_id, "EVALUATES_METHOD", node_id) in edges

    assert nodes[audit_id]["type"] == "report"
    assert nodes[audit_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/method_literature_coverage_audit.json"
    )
    assert (audit_id, "SUPPORTS_REPORT", methodology_id) in edges
    for catalog_id in [
        "catalog:method_registry",
        "catalog:regression_literature_notes",
        "catalog:manuscript_method_table",
        "catalog:publication_readiness_protocol",
    ]:
        assert nodes[catalog_id]["type"] == "catalog"
        assert (audit_id, "DERIVED_FROM", catalog_id) in edges
    assert (audit_id, "EVIDENCES", spec_id) in edges
    assert (
        audit_id,
        "EVALUATES_METHOD",
        "method:split_tail_grid_shortest",
    ) in edges
    assert (
        audit_id,
        "EVIDENCES",
        "method_spec:tail_specific_split_regression",
    ) in edges
    assert (gate_id, "DERIVED_FROM", audit_id) in edges
    assert (
        "catalog:method_registry",
        "CITES_SOURCES",
        "catalog:regression_literature_notes",
    ) in edges


def test_neutral_reporting_language_audit_links_sources_and_controls():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    report_id = "report:neutral_reporting_language_audit"
    control_id = (
        "methodology_control:neutral_reporting_language:"
        "no_unguarded_promotional_language"
    )
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/neutral_reporting_language_audit.json"
    )
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (gate_id, "DERIVED_FROM", report_id) in edges
    for source_id in [
        "report:paper_gate_closure_map",
        "report:post_experiment_publication_activation_audit",
        "report:publication_methodology_audit",
        "report:scientific_review_finding_register",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
    assert nodes[control_id]["type"] == "methodology_control"
    assert nodes[control_id]["status"] == "pass"
    assert nodes[control_id]["blocks_neutral_reporting"] is False
    assert (report_id, "SUMMARIZES_CONTROL", control_id) in edges


def test_neutral_experiment_closure_audit_links_sources_and_controls():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    report_id = "report:neutral_experiment_closure_audit"
    control_id = (
        "methodology_control:neutral_experiment_closure:"
        "all_paper_gates_have_final_dispositions"
    )
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/neutral_experiment_closure_audit.json"
    )
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (gate_id, "DERIVED_FROM", report_id) in edges
    for source_id in [
        "report:goal_completion_audit",
        "report:paper_gate_closure_map",
        "report:paper_gate_closure_execution_plan",
        "report:post_experiment_publication_activation_audit",
        "report:neutral_reporting_language_audit",
        "report:kg_publication_quality_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
    assert nodes[control_id]["type"] == "methodology_control"
    assert nodes[control_id]["status"] == "pass"
    assert nodes[control_id]["blocks_neutral_closure"] is False
    assert (report_id, "SUMMARIZES_CONTROL", control_id) in edges


def test_venn_abers_claim_gate_matrix_links_positive_claim_blockers():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    matrix_id = "report:venn_abers_claim_gate_matrix"
    requirement_id = (
        "claim_requirement:final_selection_and_fairness_claims_blocked:"
        "venn_abers_regression_validation_gate"
    )
    assert nodes[matrix_id]["type"] == "report"
    assert nodes[matrix_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/venn_abers_claim_gate_matrix.json"
    )
    assert (requirement_id, "SUPPORTED_BY", matrix_id) in edges
    assert (
        matrix_id,
        "DERIVED_FROM",
        "report:venn_abers_validation_readiness_audit",
    ) in edges
    assert (
        matrix_id,
        "DERIVED_FROM",
        "report:venn_abers_grid_ivapd_validation_protocol",
    ) in edges
    assert (
        matrix_id,
        "DERIVED_FROM",
        "report:venn_abers_grid_failure_mode_decomposition",
    ) in edges
    assert (
        "report:manuscript_readiness_map",
        "DERIVED_FROM",
        matrix_id,
    ) in edges
    assert (
        "report:retrospective_quality_gate",
        "DERIVED_FROM",
        matrix_id,
    ) in edges


def test_method_selection_alpha_expansion_batch_is_linked_to_plan_and_configs():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }

    batch_id = "report:method_selection_alpha_expansion_batch"
    plan_id = "report:method_selection_alpha_expansion_plan"
    config_id = (
        "config:regression_method_selection_alpha_expansion_"
        "stackoverflow_2025_compensation_v1"
    )

    assert nodes[batch_id]["type"] == "report"
    assert nodes[batch_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/method_selection_alpha_expansion_batch.json"
    )
    assert (batch_id, "DERIVED_FROM", plan_id) in edges
    assert (batch_id, "SUMMARIZES_CONFIG", config_id) in edges
    assert (
        batch_id,
        "SUMMARIZES_DATASET",
        "dataset:stackoverflow_2025_compensation",
    ) in edges
    for method_id in ["cqr", "cv_plus", "mondrian_abs"]:
        assert (batch_id, "EVALUATES_METHOD", f"method:{method_id}") in edges

    config_edge = edges[(batch_id, "SUMMARIZES_CONFIG", config_id)]
    assert config_edge["evidence"] == "generated_configs[4].experiment_id"
    assert config_edge["evidence_path"].endswith(
        "methodology_sanity_audit_20260627/method_selection_alpha_expansion_batch.json"
    )


def test_method_selection_alpha_expansion_execution_audit_is_linked():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }

    audit_id = "report:method_selection_alpha_expansion_execution_audit"
    batch_id = "report:method_selection_alpha_expansion_batch"
    plan_id = "report:method_selection_alpha_expansion_plan"
    results_id = "report:method_selection_post_selection_validation_results"
    gate_id = "report:retrospective_quality_gate"
    config_id = (
        "config:regression_method_selection_alpha_expansion_"
        "stackoverflow_2025_compensation_v1"
    )

    assert nodes[audit_id]["type"] == "report"
    assert nodes[audit_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/"
        "method_selection_alpha_expansion_execution_audit.json"
    )
    assert (audit_id, "DERIVED_FROM", plan_id) in edges
    assert (audit_id, "DERIVED_FROM", batch_id) in edges
    assert (audit_id, "DERIVED_FROM", results_id) in edges
    assert (gate_id, "DERIVED_FROM", audit_id) in edges
    assert (audit_id, "SUMMARIZES_CONFIG", config_id) in edges
    assert (
        audit_id,
        "SUMMARIZES_DATASET",
        "dataset:stackoverflow_2025_compensation",
    ) in edges
    for method_id in ["cqr", "cv_plus", "mondrian_abs"]:
        assert (audit_id, "EVALUATES_METHOD", f"method:{method_id}") in edges

    config_edge = edges[(audit_id, "SUMMARIZES_CONFIG", config_id)]
    assert config_edge["evidence"] == "ledger_rows[4].experiment_id"
    assert config_edge["evidence_path"].endswith(
        "methodology_sanity_audit_20260627/"
        "method_selection_alpha_expansion_execution_audit.json"
    )


def test_main_result_candidate_results_and_publication_program_are_linked():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }

    result_id = "report:main_result_candidate_bundle_results"
    closure_id = "report:main_result_candidate_post_run_closure_audit"
    plan_id = "report:main_result_candidate_bundle_plan"
    readiness_id = "report:manuscript_readiness_map"
    gate_closure_map_id = "report:paper_gate_closure_map"
    gate_execution_plan_id = "report:paper_gate_closure_execution_plan"
    protocol_design_bundle_id = "report:paper_gate_protocol_design_bundle"
    fairness_sampling_policy_id = "report:fairness_sampling_weight_policy"
    fairness_group_diagnostic_id = "report:fairness_group_diagnostic_audit"
    goal_completion_audit_id = "report:goal_completion_audit"
    goal_publication_requirement_id = (
        "methodology_control:goal_completion:"
        "post_experiment_publication_program"
    )
    venn_gate_disposition_id = (
        "methodology_control:paper_gate_closure:"
        "venn_abers_regression_validation_gate"
    )
    fairness_execution_action_id = (
        "methodology_control:paper_gate_execution:"
        "fairness_population_inference_gate_define_population_and_protected_scope"
    )
    fairness_protocol_design_id = (
        "methodology_control:paper_gate_protocol_design:"
        "fairness_population_inference_gate_define_population_and_protected_scope"
    )
    fairness_sampling_execution_action_id = (
        "methodology_control:paper_gate_execution:"
        "fairness_population_inference_gate_define_sampling_weight_policy"
    )
    fairness_group_gap_action_id = (
        "methodology_control:paper_gate_execution:"
        "fairness_population_inference_gate_compute_group_counts_missingness_and_gaps"
    )
    fairness_sampling_policy_row_id = (
        "methodology_control:fairness_sampling_weight_policy:"
        "main_result_candidate_bundle_nhanes_2017_2018_bmi"
    )
    fairness_group_diagnostic_row_id = (
        "methodology_control:fairness_group_diagnostic:"
        "main_result_candidate_bundle_nhanes_2017_2018_bmi"
    )
    publication_program_id = "catalog:post_experiment_publication_program"

    assert nodes[result_id]["type"] == "report"
    assert nodes[result_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/main_result_candidate_bundle_results.json"
    )
    assert (result_id, "DERIVED_FROM", plan_id) in edges
    assert (readiness_id, "DERIVED_FROM", result_id) in edges
    assert (result_id, "EVALUATES_METHOD", "method:cqr") in edges
    assert (
        result_id,
        "SUMMARIZES_DATASET",
        "dataset:stackoverflow_2025_compensation",
    ) in edges
    assert nodes[closure_id]["type"] == "report"
    assert nodes[closure_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/main_result_candidate_post_run_closure_audit.json"
    )
    assert (closure_id, "DERIVED_FROM", plan_id) in edges
    assert (closure_id, "DERIVED_FROM", result_id) in edges
    assert (readiness_id, "DERIVED_FROM", closure_id) in edges
    assert (
        closure_id,
        "SUMMARIZES_DATASET",
        "dataset:stackoverflow_2025_compensation",
    ) in edges
    assert nodes[gate_closure_map_id]["type"] == "report"
    assert nodes[gate_closure_map_id]["json_path"].endswith(
        "manuscript/paper_gate_closure_map.json"
    )
    assert nodes[venn_gate_disposition_id]["type"] == "methodology_control"
    assert (
        nodes[venn_gate_disposition_id]["positive_claim_ready"] is False
    )
    assert (
        nodes[venn_gate_disposition_id]["scoped_or_negative_path_ready"] is True
    )
    assert (
        gate_closure_map_id,
        "DERIVED_FROM",
        readiness_id,
    ) in edges
    assert (
        gate_closure_map_id,
        "SUMMARIZES_CONTROL",
        venn_gate_disposition_id,
    ) in edges
    assert nodes[gate_execution_plan_id]["type"] == "report"
    assert nodes[gate_execution_plan_id]["json_path"].endswith(
        "manuscript/paper_gate_closure_execution_plan.json"
    )
    assert nodes[fairness_execution_action_id]["type"] == "methodology_control"
    assert nodes[fairness_execution_action_id]["status"] == "protocol_design_complete"
    assert nodes[fairness_execution_action_id]["can_execute_now"] is False
    assert nodes[protocol_design_bundle_id]["type"] == "report"
    assert nodes[protocol_design_bundle_id]["json_path"].endswith(
        "manuscript/paper_gate_protocol_design_bundle.json"
    )
    assert nodes[fairness_protocol_design_id]["type"] == "methodology_control"
    assert nodes[fairness_protocol_design_id]["status"] == "protocol_design_complete"
    assert (
        protocol_design_bundle_id,
        "SUMMARIZES_CONTROL",
        fairness_protocol_design_id,
    ) in edges
    assert (
        protocol_design_bundle_id,
        "SUMMARIZES_CONTROL",
        fairness_execution_action_id,
    ) in edges
    assert nodes[fairness_sampling_policy_id]["type"] == "report"
    assert nodes[fairness_sampling_policy_id]["json_path"].endswith(
        "manuscript/fairness_sampling_weight_policy.json"
    )
    assert nodes[fairness_sampling_execution_action_id]["status"] == (
        "protocol_design_complete"
    )
    assert nodes[fairness_group_gap_action_id]["status"] == (
        "empirical_execution_complete"
    )
    assert nodes[fairness_group_diagnostic_id]["type"] == "report"
    assert nodes[fairness_group_diagnostic_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/fairness_group_diagnostic_audit.json"
    )
    assert nodes[fairness_group_diagnostic_row_id]["type"] == "methodology_control"
    assert nodes[fairness_group_diagnostic_row_id]["group_counts_recorded"] is True
    assert (
        nodes[fairness_group_diagnostic_row_id]["group_gap_uncertainty_recorded"]
        is True
    )
    assert (
        fairness_group_diagnostic_id,
        "SUMMARIZES_CONTROL",
        fairness_group_gap_action_id,
    ) in edges
    assert (
        fairness_group_diagnostic_id,
        "SUMMARIZES_CONTROL",
        fairness_group_diagnostic_row_id,
    ) in edges
    assert (
        fairness_group_diagnostic_id,
        "SUMMARIZES_DATASET",
        "dataset:nhanes_2017_2018_bmi",
    ) in edges
    assert nodes[fairness_sampling_policy_row_id]["type"] == "methodology_control"
    assert nodes[fairness_sampling_policy_row_id]["current_estimand_policy"] == (
        "unweighted_method_engineering_diagnostic_only"
    )
    assert (
        fairness_sampling_policy_id,
        "SUMMARIZES_CONTROL",
        fairness_sampling_execution_action_id,
    ) in edges
    assert (
        fairness_sampling_policy_id,
        "SUMMARIZES_CONTROL",
        fairness_sampling_policy_row_id,
    ) in edges
    assert (
        fairness_sampling_policy_id,
        "SUMMARIZES_DATASET",
        "dataset:nhanes_2017_2018_bmi",
    ) in edges
    assert (
        gate_execution_plan_id,
        "DERIVED_FROM",
        gate_closure_map_id,
    ) in edges
    assert (
        gate_execution_plan_id,
        "SUMMARIZES_CONTROL",
        fairness_execution_action_id,
    ) in edges
    assert (
        gate_execution_plan_id,
        "SUMMARIZES_CONTROL",
        "paper_gate:fairness_population_inference_gate",
    ) in edges
    assert nodes[goal_completion_audit_id]["type"] == "report"
    assert nodes[goal_completion_audit_id]["json_path"].endswith(
        "manuscript/goal_completion_audit.json"
    )
    assert nodes[goal_publication_requirement_id]["type"] == "methodology_control"
    assert (
        nodes[goal_publication_requirement_id]["completion_status"]
        == "in_progress"
    )
    assert (
        goal_completion_audit_id,
        "DERIVED_FROM",
        gate_closure_map_id,
    ) in edges
    assert (
        goal_completion_audit_id,
        "DERIVED_FROM",
        fairness_sampling_policy_id,
    ) in edges
    assert (
        goal_completion_audit_id,
        "DERIVED_FROM",
        gate_execution_plan_id,
    ) in edges
    assert (
        goal_completion_audit_id,
        "DERIVED_FROM",
        protocol_design_bundle_id,
    ) in edges
    assert (
        goal_completion_audit_id,
        "SUMMARIZES_CONTROL",
        goal_publication_requirement_id,
    ) in edges

    reviewer_id = "publication_reviewer:statistical_methodology_reviewer"
    deliverable_id = "publication_deliverable:main_article_latex"
    individual_report_id = "publication_deliverable:individual_experiment_report"
    sterile_repo_id = "publication_deliverable:sterile_publication_repository"
    article_section_id = "publication_surface:main_article:abstract"
    supplement_section_id = (
        "publication_surface:supplementary_document:extended_dataset_audits"
    )
    closure_check_id = (
        "publication_activation_check:01:"
        "all_configured_experiment_ledgers_are_complete_or_have_explicit_"
        "scientifically_justified_exclusion_records"
    )
    design_requirement_id = (
        "publication_design_requirement:"
        "knowledge_graph_citability_and_navigation_design"
    )
    visual_check_id = (
        "publication_quality_check:figure_answers_a_paper_relevant_question"
    )
    auditor_contract_rule_id = (
        "publication_auditor_contract_rule:scope_completeness_rule"
    )
    visual_artifact_id = "publication_audit_artifact:visual_table_audit_report_json"
    triptych_id = "publication_triptych_component:knowledge_graph_or_publication_site"

    assert nodes[reviewer_id]["type"] == "reviewer_perspective"
    assert nodes[deliverable_id]["type"] == "publication_deliverable"
    assert nodes[individual_report_id]["type"] == "publication_deliverable"
    assert nodes[sterile_repo_id]["type"] == "publication_deliverable"
    assert "Emre Tasar" in nodes[individual_report_id]["description"]
    assert "Separate clean repository" in nodes[sterile_repo_id]["description"]
    assert nodes[article_section_id]["type"] == "publication_surface"
    assert nodes[supplement_section_id]["type"] == "publication_surface"
    assert nodes[closure_check_id]["type"] == "publication_activation_check"
    assert nodes[design_requirement_id]["type"] == "publication_design_requirement"
    assert nodes[visual_check_id]["type"] == "publication_quality_check"
    assert (
        nodes[auditor_contract_rule_id]["type"]
        == "publication_auditor_contract_rule"
    )
    assert nodes[visual_artifact_id]["type"] == "publication_audit_artifact"
    assert nodes[triptych_id]["type"] == "publication_triptych_component"
    assert (
        publication_program_id,
        "SUMMARIZES_CONTROL",
        reviewer_id,
    ) in edges
    assert (
        publication_program_id,
        "SUMMARIZES_CONTROL",
        deliverable_id,
    ) in edges
    assert (
        publication_program_id,
        "SUMMARIZES_CONTROL",
        individual_report_id,
    ) in edges
    assert (
        publication_program_id,
        "SUMMARIZES_CONTROL",
        sterile_repo_id,
    ) in edges
    assert (
        publication_program_id,
        "SUMMARIZES_CONTROL",
        closure_check_id,
    ) in edges
    assert (
        publication_program_id,
        "SUMMARIZES_CONTROL",
        design_requirement_id,
    ) in edges
    assert (
        publication_program_id,
        "SUMMARIZES_CONTROL",
        visual_check_id,
    ) in edges
    assert (
        publication_program_id,
        "SUMMARIZES_CONTROL",
        auditor_contract_rule_id,
    ) in edges
    assert (
        publication_program_id,
        "SUMMARIZES_CONTROL",
        visual_artifact_id,
    ) in edges
    assert (
        publication_program_id,
        "SUMMARIZES_CONTROL",
        triptych_id,
    ) in edges


def test_method_selection_post_selection_validation_batch_is_linked_to_sources_and_configs():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }

    batch_id = "report:method_selection_post_selection_validation_batch"
    config_id = (
        "config:regression_method_selection_post_selection_validation_"
        "stackoverflow_2025_compensation_v1"
    )

    assert nodes[batch_id]["type"] == "report"
    assert nodes[batch_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/"
        "method_selection_post_selection_validation_batch.json"
    )
    for source_id in [
        "report:method_selection_alpha_expansion_batch",
        "report:method_selection_candidate_audit",
        "report:method_selection_robustness_audit",
        "report:method_selection_alpha_expansion_plan",
        "report:selection_multiplicity_protocol",
    ]:
        assert (batch_id, "DERIVED_FROM", source_id) in edges
    assert (batch_id, "SUMMARIZES_CONFIG", config_id) in edges
    assert (
        batch_id,
        "SUMMARIZES_DATASET",
        "dataset:stackoverflow_2025_compensation",
    ) in edges
    for method_id in ["cqr", "cv_plus", "mondrian_abs"]:
        assert (batch_id, "EVALUATES_METHOD", f"method:{method_id}") in edges

    config_edge = edges[(batch_id, "SUMMARIZES_CONFIG", config_id)]
    assert config_edge["evidence"] == "generated_configs[4].experiment_id"
    assert config_edge["evidence_path"].endswith(
        "methodology_sanity_audit_20260627/"
        "method_selection_post_selection_validation_batch.json"
    )


def test_method_selection_post_selection_validation_results_are_linked_to_batch_and_evidence():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }

    results_id = "report:method_selection_post_selection_validation_results"
    batch_id = "report:method_selection_post_selection_validation_batch"
    config_id = (
        "config:regression_method_selection_post_selection_validation_"
        "stackoverflow_2025_compensation_v1"
    )

    assert nodes[results_id]["type"] == "report"
    assert nodes[results_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/"
        "method_selection_post_selection_validation_results.json"
    )
    assert (results_id, "DERIVED_FROM", batch_id) in edges
    assert (results_id, "SUMMARIZES_CONFIG", config_id) in edges
    assert (
        results_id,
        "SUMMARIZES_DATASET",
        "dataset:stackoverflow_2025_compensation",
    ) in edges
    for method_id in ["cqr", "cv_plus", "mondrian_abs"]:
        assert (results_id, "EVALUATES_METHOD", f"method:{method_id}") in edges

    config_edge = edges[(results_id, "SUMMARIZES_CONFIG", config_id)]
    assert config_edge["evidence"] == "dataset_rows[4].experiment_id"
    assert config_edge["evidence_path"].endswith(
        "methodology_sanity_audit_20260627/"
        "method_selection_post_selection_validation_results.json"
    )


def test_method_selection_inferential_audit_links_sources_methods_and_claim_gates():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:method_selection_inferential_audit"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"
    final_requirement = (
        "claim_requirement:final_selection_and_fairness_claims_blocked:"
        "final_method_model_selection_gate"
    )
    multiplicity_requirement = (
        "claim_requirement:final_selection_and_fairness_claims_blocked:"
        "multiplicity_selection_record"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/"
        "method_selection_inferential_audit.json"
    )
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (gate_id, "DERIVED_FROM", report_id) in edges
    for source_id in [
        "report:method_performance_synthesis",
        "report:method_selection_candidate_audit",
        "report:method_selection_robustness_audit",
        "report:method_selection_post_selection_validation_results",
        "report:main_result_candidate_bundle_results",
        "report:selection_multiplicity_protocol",
        "report:final_selection_claim_boundary_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith(
            "method_selection_inferential_audit.json"
        )
        assert "source_artifacts" in edge["evidence"]

    for method_id in ["cqr", "cv_plus", "mondrian_abs"]:
        node_id = f"method:{method_id}"
        assert nodes[node_id]["type"] == "method"
        assert (report_id, "EVALUATES_METHOD", node_id) in edges
        edge = edge_by_triple[(report_id, "EVALUATES_METHOD", node_id)]
        assert edge["evidence_path"].endswith(
            "method_selection_inferential_audit.json"
        )
        assert "candidate_methods" in edge["evidence"]

    assert (final_requirement, "SUPPORTED_BY", report_id) in edges
    assert (multiplicity_requirement, "SUPPORTED_BY", report_id) in edges


def test_main_result_candidate_bundle_plan_links_sources_configs_and_gates():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }

    report_id = "report:main_result_candidate_bundle_plan"
    config_id = (
        "config:regression_main_result_candidate_bundle_"
        "nhanes_2017_2018_bmi_v1"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/"
        "main_result_candidate_bundle_plan.json"
    )
    for source_id in [
        "report:method_selection_post_selection_validation_results",
        "report:method_selection_post_selection_validation_batch",
        "report:dataset_specific_final_gate_audit",
        "report:selection_multiplicity_evidence_record",
        "report:manuscript_readiness_map",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
    for method_id in ["cqr", "cv_plus", "mondrian_abs"]:
        assert (report_id, "EVALUATES_METHOD", f"method:{method_id}") in edges
    assert (
        report_id,
        "SUMMARIZES_DATASET",
        "dataset:nhanes_2017_2018_bmi",
    ) in edges
    assert (report_id, "SUMMARIZES_CONFIG", config_id) in edges
    assert nodes[config_id]["path"].endswith(
        "experiments/regression/configs/"
        "main_result_candidate_bundle_nhanes_2017_2018_bmi.yaml"
    )
    assert (
        "paper_gate:dataset_specific_final_gates",
        "DERIVED_FROM",
        report_id,
    ) in edges
    assert (
        "paper_gate:final_method_model_selection_gate",
        "DERIVED_FROM",
        report_id,
    ) in edges
    assert (
        "report:retrospective_quality_gate",
        "DERIVED_FROM",
        report_id,
    ) in edges


def test_selection_multiplicity_evidence_record_links_validation_and_gates():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }

    report_id = "report:selection_multiplicity_evidence_record"
    methodology_id = "report:methodology_sanity_audit_20260627"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "experiments/regression/manuscript/"
        "selection_multiplicity_evidence_record.json"
    )
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    for source_id in [
        "catalog:manuscript_evidence_manifest_schema",
        "report:selection_multiplicity_protocol",
        "report:method_selection_candidate_audit",
        "report:method_selection_robustness_audit",
        "report:method_selection_post_selection_validation_results",
        "report:final_selection_claim_boundary_audit",
        "report:publication_methodology_audit",
        "report:manuscript_readiness_map",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
    for method_id in ["cqr", "cv_plus", "mondrian_abs"]:
        assert (report_id, "EVALUATES_METHOD", f"method:{method_id}") in edges
    assert (
        report_id,
        "SUMMARIZES_DATASET",
        "dataset:stackoverflow_2025_compensation",
    ) in edges
    assert (
        report_id,
        "SUMMARIZES_CONTROL",
        "paper_gate:final_method_model_selection_gate",
    ) in edges
    assert (
        "paper_gate:multiplicity_selection_record",
        "DERIVED_FROM",
        report_id,
    ) in edges
    assert (
        "paper_gate:multiplicity_selection_record",
        "DERIVED_FROM",
        "report:manuscript_manifest_completeness_audit",
    ) in edges
    assert (
        "report:retrospective_quality_gate",
        "DERIVED_FROM",
        report_id,
    ) in edges


def test_dataset_specific_final_gate_audit_links_sources_datasets_and_manifests():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }

    report_id = "report:dataset_specific_final_gate_audit"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/dataset_specific_final_gate_audit.json"
    )
    for source_id in [
        "catalog:manuscript_bundle_index",
        "catalog:manuscript_bundle_eligibility_matrix",
        "report:manuscript_manifest_completeness_audit",
        "report:bounded_support_dataset_audit",
        "report:fairness_population_readiness_audit",
        "report:final_selection_claim_boundary_audit",
        "report:manuscript_readiness_map",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
    assert (
        report_id,
        "SUMMARIZES_DATASET",
        "dataset:stackoverflow_2025_compensation",
    ) in edges
    assert (
        report_id,
        "SUMMARIZES_MANIFEST",
        "manifest:duplicate_cluster_sensitivity_uci_wine_quality_duplicate_sensitivity_model_visible:publication_readiness",
    ) in edges
    assert (
        "paper_gate:dataset_specific_final_gates",
        "DERIVED_FROM",
        report_id,
    ) in edges
    assert (
        "report:retrospective_quality_gate",
        "DERIVED_FROM",
        report_id,
    ) in edges


def test_dataset_final_gate_remediation_plan_links_sources_datasets_and_gates():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }

    report_id = "report:dataset_final_gate_remediation_plan"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/" "dataset_final_gate_remediation_plan.json"
    )
    remediation_summary = json.loads(
        (
            ROOT
            / "experiments/regression/reports/methodology_sanity_audit_20260627/"
            "dataset_final_gate_remediation_plan.json"
        ).read_text()
    )["summary"]
    assert (
        "Bounded-support remediation split: "
        f"{remediation_summary['bounded_support_endpoint_blocked_or_incomplete_dataset_count']} dataset(s) "
        "with endpoint blocked/incomplete bundles"
    ) in nodes[report_id]["summary"]
    assert (
        f"{remediation_summary['bounded_support_endpoint_policy_closed_dataset_count']} "
        "dataset(s) with endpoint-policy closure"
    ) in nodes[report_id]["summary"]
    assert (
        f"{remediation_summary['bounded_support_endpoint_requiring_local_remediation_dataset_count']} "
        "dataset(s) requiring local endpoint remediation"
    ) in nodes[report_id]["summary"]
    assert (
        f"{remediation_summary['bounded_support_global_no_claim_dataset_count']} dataset(s) "
        "under the global no-claim boundary"
    ) in nodes[report_id]["summary"]
    for source_id in [
        "report:dataset_specific_final_gate_audit",
        "report:method_selection_post_selection_validation_results",
        "report:dataset_final_gate_post_selection_validation_bridge",
        "report:dataset_final_gate_post_selection_validation_bridge_results",
        "report:main_result_candidate_bundle_plan",
        "report:main_result_candidate_bundle_results",
        "report:main_result_candidate_post_run_closure_audit",
        "report:bounded_support_dataset_audit",
        "report:bounded_support_endpoint_closure_audit",
        "report:manuscript_readiness_map",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
    assert (
        report_id,
        "SUMMARIZES_DATASET",
        "dataset:uci_wine_quality",
    ) in edges
    assert (
        "paper_gate:dataset_specific_final_gates",
        "DERIVED_FROM",
        report_id,
    ) in edges
    assert (
        "paper_gate:final_method_model_selection_gate",
        "DERIVED_FROM",
        report_id,
    ) in edges
    assert (
        "report:retrospective_quality_gate",
        "DERIVED_FROM",
        report_id,
    ) in edges


def test_dataset_final_gate_post_selection_validation_bridge_links_sources_and_config():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }

    report_id = "report:dataset_final_gate_post_selection_validation_bridge"
    config_id = (
        "config:regression_dataset_final_gate_post_selection_validation_bridge_"
        "uci_wine_quality_v1"
    )
    source_config_id = (
        "config:regression_model_family_sweep_uci_wine_quality_"
        "duplicate_sensitivity_v0"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/"
        "dataset_final_gate_post_selection_validation_bridge.json"
    )
    for source_id in [
        "report:dataset_final_gate_remediation_plan",
        "report:model_family_sweep_uci_wine_quality_duplicate_sensitivity",
        (
            "report:model_family_sweep_uci_wine_quality_duplicate_sensitivity:"
            "feature_leakage_audit"
        ),
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
    assert (
        report_id,
        "SUMMARIZES_DATASET",
        "dataset:uci_wine_quality",
    ) in edges
    assert (report_id, "SUMMARIZES_CONFIG", config_id) in edges
    assert (report_id, "SUMMARIZES_CONFIG", source_config_id) in edges
    for method_id in ["cqr", "cv_plus", "mondrian_abs"]:
        assert (report_id, "EVALUATES_METHOD", f"method:{method_id}") in edges
    assert (
        "paper_gate:dataset_specific_final_gates",
        "DERIVED_FROM",
        report_id,
    ) in edges
    assert (
        "paper_gate:final_method_model_selection_gate",
        "DERIVED_FROM",
        report_id,
    ) in edges


def test_dataset_final_gate_post_selection_validation_bridge_results_link_execution_evidence():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }

    report_id = "report:dataset_final_gate_post_selection_validation_bridge_results"
    bridge_id = "report:dataset_final_gate_post_selection_validation_bridge"
    config_id = (
        "config:regression_dataset_final_gate_post_selection_validation_bridge_"
        "uci_wine_quality_v1"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/"
        "dataset_final_gate_post_selection_validation_bridge_results.json"
    )
    assert (report_id, "DERIVED_FROM", bridge_id) in edges
    assert (
        report_id,
        "SUMMARIZES_DATASET",
        "dataset:uci_wine_quality",
    ) in edges
    assert (report_id, "SUMMARIZES_CONFIG", config_id) in edges
    for method_id in ["cqr", "cv_plus", "mondrian_abs"]:
        assert (report_id, "EVALUATES_METHOD", f"method:{method_id}") in edges
    assert (
        "paper_gate:dataset_specific_final_gates",
        "DERIVED_FROM",
        report_id,
    ) in edges
    assert (
        "paper_gate:final_method_model_selection_gate",
        "DERIVED_FROM",
        report_id,
    ) in edges


def test_manuscript_claim_register_links_claims_requirements_and_evidence():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    catalog_id = "catalog:manuscript_claim_register"
    md_id = "catalog:manuscript_claim_register_md"
    claim_id = "manuscript_claim:audited_cqr_cvplus_main_candidates"
    requirement_id = (
        "claim_requirement:audited_cqr_cvplus_main_candidates:" "dataset_specific_gates"
    )

    assert nodes[catalog_id]["type"] == "catalog"
    assert nodes[catalog_id]["path"].endswith(
        "experiments/regression/catalogs/manuscript_claim_register.json"
    )
    assert nodes[md_id]["type"] == "catalog"
    assert (md_id, "RENDERS", catalog_id) in edges
    assert ("catalog:knowledge_graph", "CITES_SOURCES", catalog_id) in edges

    assert nodes[claim_id]["type"] == "manuscript_claim"
    assert nodes[claim_id]["status"] == "main_candidate_with_dataset_gates"
    assert (claim_id, "RECORDED_IN", catalog_id) in edges
    assert (claim_id, "CONCERNS_METHOD", "method:cqr") in edges
    assert (claim_id, "CONCERNS_METHOD", "method:cv_plus") in edges
    assert (claim_id, "SUPPORTED_BY", "method_spec:split_and_cqr_regression") in edges
    assert (claim_id, "BLOCKED_BY", "report:integrity_remediation_backlog") in edges

    assert nodes[requirement_id]["type"] == "claim_requirement"
    assert nodes[requirement_id]["status"] == "blocked_until_each_dataset_bundle_passes"
    assert (claim_id, "HAS_REQUIREMENT", requirement_id) in edges
    assert (requirement_id, "RECORDED_IN", catalog_id) in edges
    assert (requirement_id, "SUPPORTED_BY", "report:cross_run_integrity_audit") in edges
    assert (
        requirement_id,
        "BLOCKED_BY",
        "report:integrity_remediation_backlog",
    ) in edges


def test_lawschool_manuscript_claim_links_retrospective_gate():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    claim_id = "manuscript_claim:lawschool_model_visible_duplicate_sensitivity_pending"
    gate_id = "report:retrospective_quality_gate"
    requirement_id = (
        "claim_requirement:lawschool_model_visible_duplicate_sensitivity_pending:"
        "methodology_gate_refresh"
    )

    assert nodes[gate_id]["type"] == "report"
    assert nodes[gate_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/retrospective_quality_gate.json"
    )
    assert (gate_id, "DERIVED_FROM", "report:cross_run_integrity_audit") in edges
    assert (gate_id, "DERIVED_FROM", "report:integrity_remediation_backlog") in edges

    assert nodes[claim_id]["type"] == "manuscript_claim"
    assert nodes[claim_id]["status"] == "robustness_evidence_gate_passed_with_caveats"
    assert (claim_id, "SUPPORTED_BY", gate_id) in edges
    assert (claim_id, "SUPPORTED_BY", "report:integrity_remediation_backlog") in edges
    assert nodes[requirement_id]["type"] == "claim_requirement"
    assert nodes[requirement_id]["status"] == "pass_with_caveats"
    assert (claim_id, "HAS_REQUIREMENT", requirement_id) in edges
    assert (requirement_id, "SUPPORTED_BY", gate_id) in edges


def test_claim_requirement_artifact_paths_resolve_to_support_edges():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    requirement_id = (
        "claim_requirement:stackoverflow_model_visible_duplicate_sensitivity_pending:"
        "post_run_sidecars"
    )
    report_prefix = (
        "report:duplicate_cluster_sensitivity_stackoverflow_2025_compensation_"
        "log1p_age_model_visible"
    )

    assert nodes[requirement_id]["type"] == "claim_requirement"
    for target_id in [
        report_prefix,
        f"{report_prefix}:feature_leakage_audit",
        f"{report_prefix}:runtime_cap_audit",
        f"{report_prefix}:sensitivity_comparison",
        f"{report_prefix}:endpoint_audit",
    ]:
        assert (requirement_id, "SUPPORTED_BY", target_id) in edges


def test_publication_methodology_audit_is_first_class_evidence():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    audit_id = "report:publication_methodology_audit"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[audit_id]["type"] == "report"
    assert nodes[audit_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/publication_methodology_audit.json"
    )
    assert (audit_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (audit_id, "DERIVED_FROM", "report:cross_run_integrity_audit") in edges
    assert (
        audit_id,
        "DERIVED_FROM",
        "report:final_selection_claim_boundary_audit",
    ) in edges
    assert (
        audit_id,
        "DERIVED_FROM",
        "report:fairness_population_readiness_audit",
    ) in edges
    assert (audit_id, "DERIVED_FROM", "catalog:manuscript_claim_register") in edges
    assert (audit_id, "DERIVED_FROM", "catalog:manuscript_bundle_index") in edges
    assert (gate_id, "DERIVED_FROM", audit_id) in edges


def test_fairness_population_readiness_audit_is_first_class_evidence():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    audit_id = "report:fairness_population_readiness_audit"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"
    requirement_id = (
        "claim_requirement:final_selection_and_fairness_claims_blocked:"
        "fairness_population_inference_gate"
    )

    assert nodes[audit_id]["type"] == "report"
    assert nodes[audit_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/fairness_population_readiness_audit.json"
    )
    assert (audit_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (audit_id, "DERIVED_FROM", "catalog:manuscript_claim_register") in edges
    assert (audit_id, "DERIVED_FROM", "catalog:manuscript_bundle_index") in edges
    assert (audit_id, "DERIVED_FROM", "catalog:manuscript_evidence_view") in edges
    assert (audit_id, "DERIVED_FROM", "catalog:publication_readiness_protocol") in edges
    assert (
        audit_id,
        "DERIVED_FROM",
        "report:final_selection_claim_boundary_audit",
    ) in edges
    assert (requirement_id, "SUPPORTED_BY", audit_id) in edges
    assert (gate_id, "DERIVED_FROM", audit_id) in edges


def test_venn_abers_validation_readiness_audit_is_first_class_evidence():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    audit_id = "report:venn_abers_validation_readiness_audit"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"
    requirement_id = (
        "claim_requirement:final_selection_and_fairness_claims_blocked:"
        "venn_abers_regression_validation_gate"
    )

    assert nodes[audit_id]["type"] == "report"
    assert nodes[audit_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/venn_abers_validation_readiness_audit.json"
    )
    assert (audit_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (audit_id, "DERIVED_FROM", "catalog:manuscript_claim_register") in edges
    assert (
        audit_id,
        "DERIVED_FROM",
        "report:final_selection_claim_boundary_audit",
    ) in edges
    assert (
        audit_id,
        "SUPPORTS_REPORT",
        "report:venn_abers_real_data_diagnostic",
    ) in edges
    assert (
        audit_id,
        "SUPPORTS_REPORT",
        "report:venn_abers_fairness_panel_diagnostic",
    ) in edges
    assert (
        audit_id,
        "SUPPORTS_REPORT",
        "report:venn_abers_biomarker_clinical_panel_diagnostic",
    ) in edges
    assert (audit_id, "EVALUATES_METHOD", "method:venn_abers_quantile") in edges
    assert (audit_id, "EVALUATES_METHOD", "method:venn_abers_split_fallback") in edges
    assert (audit_id, "USES_REFERENCE", "method:venn_abers_quantile_grid") in edges
    assert (audit_id, "EVIDENCES", "method_spec:venn_abers_regression") in edges
    assert (requirement_id, "SUPPORTED_BY", audit_id) in edges
    assert (requirement_id, "BLOCKED_BY", audit_id) in edges
    assert (gate_id, "DERIVED_FROM", audit_id) in edges


def test_venn_abers_grid_ivapd_validation_protocol_is_first_class_evidence():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    protocol_id = "report:venn_abers_grid_ivapd_validation_protocol"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"
    requirement_id = (
        "claim_requirement:final_selection_and_fairness_claims_blocked:"
        "venn_abers_regression_validation_gate"
    )

    assert nodes[protocol_id]["type"] == "report"
    assert nodes[protocol_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/venn_abers_grid_ivapd_validation_protocol.json"
    )
    assert (protocol_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (
        protocol_id,
        "DERIVED_FROM",
        "report:venn_abers_validation_readiness_audit",
    ) in edges
    assert (protocol_id, "DERIVED_FROM", "catalog:manuscript_claim_register") in edges
    assert (
        protocol_id,
        "SUPPORTS_REPORT",
        "report:venn_abers_real_data_diagnostic",
    ) in edges
    assert (
        protocol_id,
        "SUPPORTS_REPORT",
        "report:venn_abers_fairness_panel_diagnostic",
    ) in edges
    assert (
        protocol_id,
        "SUPPORTS_REPORT",
        "report:venn_abers_biomarker_clinical_panel_diagnostic",
    ) in edges
    assert (protocol_id, "USES_REFERENCE", "method:venn_abers_quantile_grid") in edges
    assert (protocol_id, "EVALUATES_METHOD", "method:ivapd_regression") in edges
    assert (protocol_id, "EVIDENCES", "method_spec:venn_abers_regression") in edges
    assert (requirement_id, "SUPPORTED_BY", protocol_id) in edges
    assert (requirement_id, "BLOCKED_BY", protocol_id) in edges
    assert (gate_id, "DERIVED_FROM", protocol_id) in edges


def test_venn_abers_grid_expansion_plan_is_first_class_evidence():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    plan_id = "report:venn_abers_grid_expansion_plan"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"
    requirement_id = (
        "claim_requirement:final_selection_and_fairness_claims_blocked:"
        "venn_abers_regression_validation_gate"
    )

    assert nodes[plan_id]["type"] == "report"
    assert nodes[plan_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/venn_abers_grid_expansion_plan.json"
    )
    assert (plan_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (
        plan_id,
        "DERIVED_FROM",
        "report:venn_abers_grid_ivapd_validation_protocol",
    ) in edges
    assert (
        plan_id,
        "DERIVED_FROM",
        "report:venn_abers_validation_readiness_audit",
    ) in edges
    for report_id in [
        "report:venn_abers_real_data_diagnostic",
        "report:venn_abers_fairness_panel_diagnostic",
        "report:venn_abers_biomarker_clinical_panel_diagnostic",
    ]:
        assert (plan_id, "SUPPORTS_REPORT", report_id) in edges
    assert (plan_id, "USES_REFERENCE", "method:venn_abers_quantile_grid") in edges
    assert (plan_id, "EVIDENCES", "method_spec:venn_abers_regression") in edges
    assert (requirement_id, "SUPPORTED_BY", plan_id) in edges
    assert (gate_id, "DERIVED_FROM", plan_id) in edges


def test_venn_abers_grid_failure_mode_decomposition_is_first_class_evidence():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    report_id = "report:venn_abers_grid_failure_mode_decomposition"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"
    requirement_id = (
        "claim_requirement:final_selection_and_fairness_claims_blocked:"
        "venn_abers_regression_validation_gate"
    )
    negative_requirement_id = (
        "claim_requirement:venn_abers_fast_bridge_negative_result:"
        "negative_evidence_preserved"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/"
        "venn_abers_grid_failure_mode_decomposition.json"
    )
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:venn_abers_grid_ivapd_validation_protocol",
    ) in edges
    assert (report_id, "DERIVED_FROM", "report:venn_abers_grid_expansion_plan") in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:venn_abers_validation_readiness_audit",
    ) in edges
    for source_report_id in [
        "report:venn_abers_real_data_diagnostic",
        "report:venn_abers_fairness_panel_diagnostic",
        "report:venn_abers_biomarker_clinical_panel_diagnostic",
    ]:
        assert (report_id, "SUPPORTS_REPORT", source_report_id) in edges
    assert (report_id, "USES_REFERENCE", "method:venn_abers_quantile_grid") in edges
    assert (report_id, "EVALUATES_METHOD", "method:ivapd_regression") in edges
    assert (report_id, "EVIDENCES", "method_spec:venn_abers_regression") in edges
    assert (requirement_id, "SUPPORTED_BY", report_id) in edges
    assert (negative_requirement_id, "SUPPORTED_BY", report_id) in edges
    assert (gate_id, "DERIVED_FROM", report_id) in edges


def test_venn_abers_grid_expansion_batch_is_first_class_evidence():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    batch_id = "report:venn_abers_grid_expansion_batch"
    plan_id = "report:venn_abers_grid_expansion_plan"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"
    requirement_id = (
        "claim_requirement:final_selection_and_fairness_claims_blocked:"
        "venn_abers_regression_validation_gate"
    )

    assert nodes[batch_id]["type"] == "report"
    assert nodes[batch_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/venn_abers_grid_expansion_batch.json"
    )
    assert (batch_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (batch_id, "DERIVED_FROM", plan_id) in edges
    assert (
        batch_id,
        "DERIVED_FROM",
        "report:venn_abers_grid_ivapd_validation_protocol",
    ) in edges
    for report_id in [
        "report:venn_abers_real_data_diagnostic",
        "report:venn_abers_fairness_panel_diagnostic",
        "report:venn_abers_biomarker_clinical_panel_diagnostic",
    ]:
        assert (batch_id, "SUPPORTS_REPORT", report_id) in edges
    assert (batch_id, "USES_REFERENCE", "method:venn_abers_quantile_grid") in edges
    assert (batch_id, "EVIDENCES", "method_spec:venn_abers_regression") in edges
    assert (requirement_id, "SUPPORTED_BY", batch_id) in edges
    assert (gate_id, "DERIVED_FROM", batch_id) in edges


def test_venn_abers_negative_evidence_disposition_is_first_class_evidence():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:venn_abers_negative_evidence_disposition_audit"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"
    scientific_register_id = "report:scientific_review_finding_register"
    claim_id = "manuscript_claim:venn_abers_fast_bridge_negative_result"
    requirement_id = (
        "claim_requirement:final_selection_and_fairness_claims_blocked:"
        "venn_abers_regression_validation_gate"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/"
        "venn_abers_negative_evidence_disposition_audit.json"
    )
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    for source_id in [
        "catalog:manuscript_claim_register",
        "report:venn_abers_validation_readiness_audit",
        "report:venn_abers_grid_ivapd_validation_protocol",
        "report:venn_abers_grid_failure_mode_decomposition",
        "report:venn_abers_claim_gate_matrix",
        "report:method_selection_candidate_audit",
        "report:method_performance_synthesis",
        "catalog:manuscript_bundle_eligibility_matrix",
        "report:final_selection_claim_boundary_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith(
            "venn_abers_negative_evidence_disposition_audit.json"
        )
        assert edge.get("evidence")

    for method_id in [
        "venn_abers_quantile",
        "venn_abers_split_fallback",
        "ivapd_regression",
    ]:
        assert (report_id, "EVALUATES_METHOD", f"method:{method_id}") in edges

    assert (claim_id, "SUPPORTED_BY", report_id) in edges
    assert (requirement_id, "SUPPORTED_BY", report_id) in edges
    assert (gate_id, "DERIVED_FROM", report_id) in edges
    assert (scientific_register_id, "DERIVED_FROM", report_id) in edges


def test_duplicate_sensitivity_closure_audit_is_first_class_evidence():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    audit_id = "report:duplicate_sensitivity_closure_audit"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"
    publication_id = "report:publication_methodology_audit"
    control_id = "methodology_control:duplicate_signature_sensitivity_tracking"

    assert nodes[audit_id]["type"] == "report"
    assert nodes[audit_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/duplicate_sensitivity_closure_audit.json"
    )
    assert (audit_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (audit_id, "DERIVED_FROM", "report:cross_run_integrity_audit") in edges
    assert (audit_id, "DERIVED_FROM", "report:duplicate_split_caveat_backlog") in edges
    assert (
        audit_id,
        "DERIVED_FROM",
        "report:paired_duplicate_sensitivity_audit",
    ) in edges
    assert (audit_id, "DERIVED_FROM", "report:integrity_remediation_backlog") in edges
    assert (
        audit_id,
        "DERIVED_FROM",
        "report:final_selection_claim_boundary_audit",
    ) in edges
    assert (audit_id, "DERIVED_FROM", publication_id) in edges
    assert (audit_id, "DERIVED_FROM", "catalog:manuscript_claim_register") in edges
    assert (audit_id, "DERIVED_FROM", "catalog:manuscript_bundle_index") in edges
    assert (audit_id, "SUMMARIZES_CONTROL", control_id) in edges
    assert (gate_id, "DERIVED_FROM", audit_id) in edges


def test_duplicate_content_quarantine_audit_is_first_class_evidence():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    audit_id = "report:duplicate_content_quarantine_audit"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"
    control_id = "methodology_control:duplicate_signature_sensitivity_tracking"

    assert nodes[audit_id]["type"] == "report"
    assert nodes[audit_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/duplicate_content_quarantine_audit.json"
    )
    assert (audit_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (
        audit_id,
        "DERIVED_FROM",
        "report:duplicate_sensitivity_closure_audit",
    ) in edges
    assert (
        audit_id,
        "DERIVED_FROM",
        "catalog:manuscript_bundle_eligibility_matrix",
    ) in edges
    assert (
        audit_id,
        "DERIVED_FROM",
        "report:final_selection_claim_boundary_audit",
    ) in edges
    assert (audit_id, "DERIVED_FROM", "catalog:manuscript_claim_register") in edges
    assert (audit_id, "SUMMARIZES_CONTROL", control_id) in edges
    assert (gate_id, "DERIVED_FROM", audit_id) in edges
    assert (
        "report:scientific_review_finding_register",
        "DERIVED_FROM",
        audit_id,
    ) in edges


def test_kg_publication_quality_audit_is_first_class_evidence():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    quality_id = "report:knowledge_graph_quality_summary"
    audit_id = "report:kg_publication_quality_audit"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[quality_id]["type"] == "report"
    assert nodes[quality_id]["json_path"].endswith(
        "knowledge_graph_quality/quality_summary.json"
    )
    assert nodes[audit_id]["type"] == "report"
    assert nodes[audit_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/kg_publication_quality_audit.json"
    )
    assert (quality_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (quality_id, "DERIVED_FROM", "catalog:knowledge_graph") in edges
    assert (audit_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (audit_id, "DERIVED_FROM", "catalog:knowledge_graph") in edges
    assert (audit_id, "DERIVED_FROM", quality_id) in edges
    assert (gate_id, "DERIVED_FROM", quality_id) in edges
    assert (gate_id, "DERIVED_FROM", audit_id) in edges


def test_scientific_review_finding_register_is_first_class_evidence():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    register_id = "report:scientific_review_finding_register"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[register_id]["type"] == "report"
    assert nodes[register_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/scientific_review_finding_register.json"
    )
    assert (register_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (
        register_id,
        "DERIVED_FROM",
        "report:knowledge_graph_quality_summary",
    ) in edges
    assert (register_id, "DERIVED_FROM", "report:kg_publication_quality_audit") in edges
    assert (
        register_id,
        "DERIVED_FROM",
        "report:publication_methodology_audit",
    ) in edges
    assert (
        register_id,
        "DERIVED_FROM",
        "report:final_selection_claim_boundary_audit",
    ) in edges
    assert (gate_id, "DERIVED_FROM", register_id) in edges


def test_graph_artifact_readiness_audit_links_mermaid_graph_nodes():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    audit_id = "report:graph_artifact_readiness_audit"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[audit_id]["type"] == "report"
    assert nodes[audit_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/graph_artifact_readiness_audit.json"
    )
    assert (audit_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (audit_id, "DERIVED_FROM", "catalog:knowledge_graph") in edges
    assert (gate_id, "DERIVED_FROM", audit_id) in edges
    for graph_id in [
        "system_ontology",
        "data_flow",
        "control_flow",
        "dependency_graph",
    ]:
        node_id = f"graph:{graph_id}"
        assert nodes[node_id]["type"] == "graph"
        assert (node_id, "DOCUMENTS_GRAPH", "catalog:knowledge_graph") in edges
        assert (audit_id, "AUDITS_GRAPH", node_id) in edges


def test_manuscript_readiness_map_links_claim_boundary_sources():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    catalog_id = "catalog:manuscript_paper_readiness_map"
    report_id = "report:manuscript_readiness_map"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[catalog_id]["type"] == "catalog"
    assert nodes[catalog_id]["json_path"].endswith(
        "experiments/regression/manuscript/paper_readiness_map.json"
    )
    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "experiments/regression/manuscript/paper_readiness_map.json"
    )
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (report_id, "DERIVED_FROM", catalog_id) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "catalog:selection_multiplicity_protocol",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:selection_multiplicity_protocol",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "catalog:bounded_support_protocol",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:bounded_support_protocol",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "catalog:bounded_support_dataset_audit",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:bounded_support_dataset_audit",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "catalog:target_domain_provenance",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:target_domain_provenance",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "catalog:bounded_support_posthandling_validation",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:bounded_support_posthandling_validation",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "catalog:publication_readiness_protocol",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "catalog:post_experiment_publication_program",
    ) in edges
    assert (report_id, "DERIVED_FROM", "catalog:manuscript_bundle_index") in edges
    assert (report_id, "DERIVED_FROM", "catalog:manuscript_evidence_view") in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:method_selection_inferential_audit",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:publication_methodology_audit",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:final_selection_claim_boundary_audit",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:fairness_population_readiness_audit",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:venn_abers_validation_readiness_audit",
    ) in edges
    endpoint_gate = "paper_gate:endpoint_bounded_support_gate"
    fairness_gate = "paper_gate:fairness_population_inference_gate"
    selection_gate = "paper_gate:final_method_model_selection_gate"
    venn_gate = "paper_gate:venn_abers_regression_validation_gate"
    endpoint_requirement = (
        "claim_requirement:final_selection_and_fairness_claims_blocked:"
        "endpoint_bounded_support_gate"
    )
    fairness_requirement = (
        "claim_requirement:final_selection_and_fairness_claims_blocked:"
        "fairness_population_inference_gate"
    )
    selection_requirement = (
        "claim_requirement:final_selection_and_fairness_claims_blocked:"
        "final_method_model_selection_gate"
    )
    venn_requirement = (
        "claim_requirement:final_selection_and_fairness_claims_blocked:"
        "venn_abers_regression_validation_gate"
    )
    assert nodes[endpoint_gate]["type"] == "paper_gate"
    assert nodes[endpoint_gate]["status"] == "blocked"
    assert (report_id, "SUMMARIZES_CONTROL", endpoint_gate) in edges
    assert (endpoint_requirement, "BLOCKED_BY", endpoint_gate) in edges
    assert (endpoint_gate, "DERIVED_FROM", "report:bounded_support_protocol") in edges
    assert (report_id, "SUMMARIZES_CONTROL", selection_gate) in edges
    assert (selection_requirement, "BLOCKED_BY", selection_gate) in edges
    assert (
        selection_gate,
        "DERIVED_FROM",
        "report:selection_multiplicity_protocol",
    ) in edges
    assert (report_id, "SUMMARIZES_CONTROL", fairness_gate) in edges
    assert (fairness_requirement, "BLOCKED_BY", fairness_gate) in edges
    assert (
        fairness_gate,
        "DERIVED_FROM",
        "report:fairness_population_readiness_audit",
    ) in edges
    assert (report_id, "SUMMARIZES_CONTROL", venn_gate) in edges
    assert (venn_requirement, "BLOCKED_BY", venn_gate) in edges
    assert (
        venn_gate,
        "DERIVED_FROM",
        "report:venn_abers_validation_readiness_audit",
    ) in edges
    assert (
        venn_gate,
        "DERIVED_FROM",
        "report:venn_abers_grid_failure_mode_decomposition",
    ) in edges
    fairness_gate_source_edge = edge_by_triple[
        (
            fairness_gate,
            "DERIVED_FROM",
            "report:fairness_population_readiness_audit",
        )
    ]
    assert "fairness_population_inference_gate" in fairness_gate_source_edge["evidence"]
    assert "source_artifacts" in fairness_gate_source_edge["evidence"]
    assert (
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "fairness_population_readiness_audit.json"
        in fairness_gate_source_edge["evidence"]
    )
    assert (
        "fairness_population_inference_gate"
        in edge_by_triple[(fairness_requirement, "BLOCKED_BY", fairness_gate)][
            "evidence"
        ]
    )
    assert (gate_id, "DERIVED_FROM", report_id) in edges


def test_bounded_support_dataset_audit_links_bundle_datasets_and_endpoint_audits():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    catalog_id = "catalog:bounded_support_dataset_audit"
    report_id = "report:bounded_support_dataset_audit"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"
    claim_requirement_id = (
        "claim_requirement:final_selection_and_fairness_claims_blocked:"
        "endpoint_bounded_support_gate"
    )

    assert nodes[catalog_id]["type"] == "catalog"
    assert nodes[catalog_id]["json_path"].endswith(
        "experiments/regression/manuscript/bounded_support_dataset_audit.json"
    )
    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "experiments/regression/manuscript/bounded_support_dataset_audit.json"
    )
    audit_path = ROOT / "experiments/regression/manuscript/bounded_support_dataset_audit.json"
    audit_summary = json.loads(
        audit_path.read_text()
    )["summary"]
    expected_endpoint_split = (
        "Endpoint support split: "
        f"{audit_summary['endpoint_support_clean_bundle_count']} clean, "
        f"{audit_summary['endpoint_support_not_applicable_bundle_count']} not applicable, "
        f"{audit_summary['endpoint_support_blocked_or_incomplete_bundle_count']} blocked or incomplete"
    )
    assert expected_endpoint_split in nodes[report_id]["summary"]
    assert (
        f"bounded-support-ready bundles: {audit_summary['bounded_support_ready_bundle_count']}"
        in nodes[report_id]["summary"]
    )
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (report_id, "DERIVED_FROM", catalog_id) in edges
    assert (report_id, "DERIVED_FROM", "catalog:bounded_support_protocol") in edges
    assert (report_id, "DERIVED_FROM", "report:bounded_support_protocol") in edges
    assert (report_id, "DERIVED_FROM", "catalog:target_domain_provenance") in edges
    assert (report_id, "DERIVED_FROM", "report:target_domain_provenance") in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "catalog:bounded_support_posthandling_validation",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:bounded_support_posthandling_validation",
    ) in edges
    assert (report_id, "DERIVED_FROM", "catalog:manuscript_bundle_index") in edges
    assert (report_id, "DERIVED_FROM", "catalog:manuscript_evidence_view") in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:final_selection_claim_boundary_audit",
    ) in edges
    assert (claim_requirement_id, "SUPPORTED_BY", report_id) in edges
    assert (gate_id, "DERIVED_FROM", report_id) in edges
    assert (report_id, "SUMMARIZES_DATASET", "dataset:nhanes_2017_2018_bmi") in edges
    assert (report_id, "SUMMARIZES_DATASET", "dataset:uci_wine_quality_dedup") in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:duplicate_cluster_sensitivity_nhanes_2017_2018_bmi_identity_ridreth3_model_visible:endpoint_audit",
    ) in edges


def test_target_domain_provenance_links_sources_and_datasets():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    catalog_id = "catalog:target_domain_provenance"
    report_id = "report:target_domain_provenance"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[catalog_id]["type"] == "catalog"
    assert nodes[catalog_id]["json_path"].endswith(
        "experiments/regression/catalogs/target_domain_provenance.json"
    )
    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "experiments/regression/catalogs/target_domain_provenance.json"
    )
    assert (catalog_id, "CITES_SOURCES", "catalog:source_registry") in edges
    assert ("catalog:knowledge_graph", "CITES_SOURCES", catalog_id) in edges
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (report_id, "DERIVED_FROM", catalog_id) in edges
    assert (report_id, "DERIVED_FROM", "catalog:source_registry") in edges
    assert (report_id, "DERIVED_FROM", "catalog:bounded_support_protocol") in edges
    assert (report_id, "DERIVED_FROM", "report:bounded_support_protocol") in edges
    assert (report_id, "SUMMARIZES_DATASET", "dataset:uci_wine_quality") in edges
    assert (gate_id, "DERIVED_FROM", report_id) in edges


def test_bounded_support_posthandling_validation_links_sources_and_datasets():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    catalog_id = "catalog:bounded_support_posthandling_validation"
    report_id = "report:bounded_support_posthandling_validation"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[catalog_id]["type"] == "catalog"
    assert nodes[catalog_id]["json_path"].endswith(
        "experiments/regression/manuscript/bounded_support_posthandling_validation.json"
    )
    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "experiments/regression/manuscript/bounded_support_posthandling_validation.json"
    )
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (report_id, "DERIVED_FROM", catalog_id) in edges
    assert (report_id, "DERIVED_FROM", "catalog:target_domain_provenance") in edges
    assert (report_id, "DERIVED_FROM", "report:target_domain_provenance") in edges
    assert (report_id, "DERIVED_FROM", "catalog:bounded_support_protocol") in edges
    assert (report_id, "DERIVED_FROM", "report:bounded_support_protocol") in edges
    assert (report_id, "SUMMARIZES_DATASET", "dataset:uci_wine_quality") in edges
    assert (gate_id, "DERIVED_FROM", report_id) in edges


def test_bounded_support_protocol_links_endpoint_claim_sources():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    catalog_id = "catalog:bounded_support_protocol"
    report_id = "report:bounded_support_protocol"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"
    claim_requirement_id = (
        "claim_requirement:final_selection_and_fairness_claims_blocked:"
        "endpoint_bounded_support_gate"
    )

    assert nodes[catalog_id]["type"] == "catalog"
    assert nodes[catalog_id]["json_path"].endswith(
        "experiments/regression/manuscript/bounded_support_protocol.json"
    )
    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "experiments/regression/manuscript/bounded_support_protocol.json"
    )
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (report_id, "DERIVED_FROM", catalog_id) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "catalog:publication_readiness_protocol",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "catalog:manuscript_evidence_manifest_schema",
    ) in edges
    assert (report_id, "DERIVED_FROM", "catalog:manuscript_evidence_view") in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:publication_methodology_audit",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:final_selection_claim_boundary_audit",
    ) in edges
    assert (claim_requirement_id, "SUPPORTED_BY", report_id) in edges
    assert (gate_id, "DERIVED_FROM", report_id) in edges


def test_selection_multiplicity_protocol_links_manifest_schema_and_claim_sources():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    catalog_id = "catalog:selection_multiplicity_protocol"
    report_id = "report:selection_multiplicity_protocol"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[catalog_id]["type"] == "catalog"
    assert nodes[catalog_id]["json_path"].endswith(
        "experiments/regression/manuscript/selection_multiplicity_protocol.json"
    )
    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "experiments/regression/manuscript/selection_multiplicity_protocol.json"
    )
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (report_id, "DERIVED_FROM", catalog_id) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "catalog:publication_readiness_protocol",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "catalog:manuscript_evidence_manifest_schema",
    ) in edges
    assert (report_id, "DERIVED_FROM", "catalog:manuscript_bundle_index") in edges
    assert (report_id, "DERIVED_FROM", "catalog:manuscript_evidence_view") in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:publication_methodology_audit",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:final_selection_claim_boundary_audit",
    ) in edges
    bundle_index = json.loads(
        (
            ROOT / "experiments/regression/catalogs/manuscript_bundle_index.json"
        ).read_text()
    )
    for bundle in bundle_index["bundles"]:
        manifest_path = Path(bundle["manifest_path"])
        manifest_id = f"manifest:{manifest_path.parent.name}:publication_readiness"
        assert (report_id, "SUMMARIZES_MANIFEST", manifest_id) in edges
    assert (gate_id, "DERIVED_FROM", report_id) in edges


def test_bike_sharing_core_endpoint_audit_is_partial_sidecar():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    report_id = "report:model_family_sweep_uci_bike_sharing_day_ordered"
    sidecar_id = f"{report_id}:endpoint_audit_core_methods"
    assert nodes[sidecar_id]["type"] == "report"
    assert nodes[sidecar_id]["json_path"].endswith(
        "model_family_sweep_uci_bike_sharing_day_ordered/"
        "endpoint_audit_core_methods.json"
    )
    assert (sidecar_id, "SUPPORTS_REPORT", report_id) in edges


def test_acs_endpoint_audit_links_report_config_and_dataset():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    report_id = "report:full_literature_sweep_acs_income_log1p"
    sidecar_id = f"{report_id}:endpoint_audit"
    config_id = "config:regression_literature_sweep_acs_income_log1p_v0"
    dataset_id = "dataset:fairlearn_acs_income_wy"

    assert nodes[sidecar_id]["type"] == "report"
    assert nodes[sidecar_id]["json_path"].endswith(
        "full_literature_sweep_acs_income_log1p/endpoint_audit.json"
    )
    assert (sidecar_id, "SUPPORTS_REPORT", report_id) in edges
    assert (sidecar_id, "SUMMARIZES_CONFIG", config_id) in edges
    assert (sidecar_id, "SUMMARIZES_DATASET", dataset_id) in edges


def test_acs_row_signature_partial_report_sidecars_are_first_class():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    report_id = "report:duplicate_cluster_sensitivity_acs_income_log1p_row_signature"
    config_id = "config:regression_duplicate_cluster_sensitivity_acs_income_log1p_row_signature_v0"
    dataset_id = "dataset:fairlearn_acs_income_wy"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["report_status"] in {"partial_run", "completed_report"}
    assert (report_id, "SUMMARIZES_CONFIG", config_id) in edges
    assert (report_id, "SUMMARIZES_DATASET", dataset_id) in edges

    for sidecar in [
        "split_profile",
        "feature_leakage_audit_seed0_partial",
        "experiment_notes",
    ]:
        sidecar_id = f"{report_id}:{sidecar}"
        assert nodes[sidecar_id]["type"] == "report"
        assert (sidecar_id, "SUPPORTS_REPORT", report_id) in edges
        assert (sidecar_id, "SUMMARIZES_CONFIG", config_id) in edges
        assert (sidecar_id, "SUMMARIZES_DATASET", dataset_id) in edges


def test_legacy_endpoint_audit_uses_report_name_config_fallback():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    report_id = "report:model_family_sweep_openml_auto_price_symboling_log1p"
    sidecar_id = f"{report_id}:endpoint_audit"
    result_id = (
        "endpoint_result:model_family_sweep_openml_auto_price_symboling_log1p:"
        "split_abs"
    )
    config_id = (
        "config:regression_model_family_sweep_openml_auto_price_symboling_log1p_v0"
    )

    assert nodes[sidecar_id]["type"] == "report"
    assert nodes[result_id]["type"] == "endpoint_result"
    assert (sidecar_id, "SUMMARIZES_CONFIG", config_id) in edges
    assert (result_id, "SUMMARIZES_CONFIG", config_id) in edges


def test_duplicate_split_caveat_backlog_links_datasets_reports_and_configs():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    backlog_id = "report:duplicate_split_caveat_backlog"
    methodology_id = "report:methodology_sanity_audit_20260627"

    assert nodes[backlog_id]["type"] == "report"
    assert nodes[backlog_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/duplicate_split_caveat_backlog.json"
    )
    assert (backlog_id, "SUPPORTS_REPORT", methodology_id) in edges
    for dataset_id in [
        "aif360_lawschool_gpa",
        "fairlearn_acs_income_wy",
        "openml_analcatdata_hiroshima_rate",
        "openml_arsenic_event_rate_panel",
        "openml_delta_elevators_se",
        "uci_wine_quality",
    ]:
        assert (backlog_id, "SUMMARIZES_DATASET", f"dataset:{dataset_id}") in edges
    assert (
        backlog_id,
        "SUPPORTS_REPORT",
        "report:model_family_sweep_aif360_lawschool_gpa_duplicate_sensitivity",
    ) in edges
    assert (
        backlog_id,
        "SUMMARIZES_CONFIG",
        "config:regression_model_family_sweep_aif360_lawschool_gpa_duplicate_sensitivity_v0",
    ) in edges


def test_paired_duplicate_sensitivity_audit_links_raw_and_dedup_evidence():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    audit_id = "report:paired_duplicate_sensitivity_audit"

    assert nodes[audit_id]["type"] == "report"
    assert nodes[audit_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/paired_duplicate_sensitivity_audit.json"
    )
    assert (
        audit_id,
        "SUPPORTS_REPORT",
        "report:duplicate_split_caveat_backlog",
    ) in edges
    for dataset_id in [
        "aif360_lawschool_gpa",
        "aif360_lawschool_gpa_dedup",
        "uci_wine_quality",
        "uci_wine_quality_dedup",
        "openml_analcatdata_hiroshima_rate",
        "openml_analcatdata_hiroshima_rate_dedup",
    ]:
        assert (audit_id, "SUMMARIZES_DATASET", f"dataset:{dataset_id}") in edges
    assert (
        audit_id,
        "SUPPORTS_REPORT",
        "report:model_family_sweep_uci_wine_quality_duplicate_sensitivity",
    ) in edges


def test_cross_run_integrity_audit_links_reports_sidecars_and_configs():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    audit_id = "report:cross_run_integrity_audit"
    report_id = "report:full_literature_sweep_acs_income_log1p"
    config_id = "config:regression_literature_sweep_acs_income_log1p_v0"
    dataset_id = "dataset:fairlearn_acs_income_wy"

    assert nodes[audit_id]["type"] == "report"
    assert nodes[audit_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/cross_run_integrity_audit.json"
    )
    assert (
        audit_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (audit_id, "SUPPORTS_REPORT", report_id) in edges
    assert (audit_id, "SUPPORTS_REPORT", f"{report_id}:split_profile") in edges
    assert (audit_id, "SUPPORTS_REPORT", f"{report_id}:endpoint_audit") in edges
    assert (audit_id, "SUPPORTS_REPORT", f"{report_id}:feature_leakage_audit") in edges
    assert (audit_id, "SUMMARIZES_CONFIG", config_id) in edges
    assert (audit_id, "SUMMARIZES_DATASET", dataset_id) in edges


def test_experiment_accounting_audit_links_scope_sources():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    audit_id = "report:experiment_accounting_audit"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[audit_id]["type"] == "report"
    assert nodes[audit_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/experiment_accounting_audit.json"
    )
    assert (
        audit_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    for source_id in [
        "report:cross_run_integrity_audit",
        "report:publication_methodology_audit",
        "report:selection_multiplicity_protocol",
        "report:bounded_support_posthandling_validation",
        "report:venn_abers_grid_expansion_plan",
        "report:venn_abers_grid_ivapd_validation_protocol",
    ]:
        assert (audit_id, "DERIVED_FROM", source_id) in edges
    assert (gate_id, "DERIVED_FROM", audit_id) in edges


def test_duplicate_cluster_sensitivity_comparison_is_first_class_sidecar():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    report_id = (
        "report:duplicate_cluster_sensitivity_openml_chlamydia_count_log1p_gender"
    )
    sidecar_id = f"{report_id}:sensitivity_comparison"
    config_id = "config:regression_duplicate_cluster_sensitivity_openml_chlamydia_count_log1p_gender_v0"
    dataset_id = "dataset:openml_analcatdata_chlamydia"

    assert nodes[sidecar_id]["type"] == "report"
    assert nodes[sidecar_id]["json_path"].endswith(
        "duplicate_cluster_sensitivity_openml_chlamydia_count_log1p_gender/"
        "sensitivity_comparison.json"
    )
    assert (sidecar_id, "SUPPORTS_REPORT", report_id) in edges
    assert (sidecar_id, "SUMMARIZES_CONFIG", config_id) in edges
    assert (sidecar_id, "SUMMARIZES_DATASET", dataset_id) in edges


def test_retrospective_methodology_controls_links_control_nodes():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    report_id = "report:retrospective_methodology_controls"
    control_id = "methodology_control:hard_split_leakage_absence"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/retrospective_methodology_controls.json"
    )
    assert nodes[control_id]["type"] == "methodology_control"
    assert (
        report_id,
        "DERIVED_FROM",
        "report:cross_run_integrity_audit",
    ) in edges
    assert (report_id, "SUMMARIZES_CONTROL", control_id) in edges


def test_integrity_remediation_backlog_links_cross_run_sources():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    backlog_id = "report:integrity_remediation_backlog"
    report_id = "report:full_literature_sweep_acs_income_log1p"
    config_id = "config:regression_literature_sweep_acs_income_log1p_v0"
    dataset_id = "dataset:fairlearn_acs_income_wy"

    assert nodes[backlog_id]["type"] == "report"
    assert nodes[backlog_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/integrity_remediation_backlog.json"
    )
    assert (
        backlog_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (
        backlog_id,
        "SUPPORTS_REPORT",
        "report:cross_run_integrity_audit",
    ) in edges
    assert (backlog_id, "SUPPORTS_REPORT", report_id) in edges
    assert (backlog_id, "SUMMARIZES_CONFIG", config_id) in edges
    assert (backlog_id, "SUMMARIZES_DATASET", dataset_id) in edges


def test_feature_leakage_backfill_links_generated_sidecars():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    backfill_id = "report:feature_leakage_sidecar_backfill"
    report_id = "report:fairness_smoke_hmda_interest_rate"
    config_id = "config:regression_fairness_smoke_hmda_2025_wy_interest_rate_v0"
    dataset_id = "dataset:hmda_2025_wy_interest_rate"

    assert nodes[backfill_id]["type"] == "report"
    assert nodes[backfill_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/feature_leakage_sidecar_backfill.json"
    )
    assert (
        backfill_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (
        backfill_id,
        "SUPPORTS_REPORT",
        "report:integrity_remediation_backlog",
    ) in edges
    assert (backfill_id, "SUPPORTS_REPORT", report_id) in edges
    assert (
        backfill_id,
        "SUPPORTS_REPORT",
        f"{report_id}:feature_leakage_audit",
    ) in edges
    assert (backfill_id, "SUMMARIZES_CONFIG", config_id) in edges
    assert (backfill_id, "SUMMARIZES_DATASET", dataset_id) in edges


def test_legacy_claim_guard_backfill_links_updated_configs():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    backfill_id = "report:legacy_claim_guard_backfill"
    report_id = "report:fairness_smoke_hmda_interest_rate"
    config_id = "config:regression_fairness_smoke_hmda_2025_wy_interest_rate_v0"

    assert nodes[backfill_id]["type"] == "report"
    assert nodes[backfill_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/legacy_claim_guard_backfill.json"
    )
    assert (
        backfill_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (
        backfill_id,
        "SUPPORTS_REPORT",
        "report:integrity_remediation_backlog",
    ) in edges
    assert (backfill_id, "SUPPORTS_REPORT", report_id) in edges
    assert (backfill_id, "SUMMARIZES_CONFIG", config_id) in edges


def test_feature_metadata_triage_links_caveated_sidecars():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    triage = json.loads(
        (
            ROOT
            / "experiments/regression/reports/methodology_sanity_audit_20260627/feature_leakage_metadata_completeness_triage.json"
        ).read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    triage_id = "report:feature_leakage_metadata_completeness_triage"
    assert nodes[triage_id]["type"] == "report"
    assert nodes[triage_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/feature_leakage_metadata_completeness_triage.json"
    )
    assert (
        triage_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (
        triage_id,
        "SUPPORTS_REPORT",
        "report:cross_run_integrity_audit",
    ) in edges
    assert (
        triage_id,
        "SUPPORTS_REPORT",
        "report:integrity_remediation_backlog",
    ) in edges
    if triage["rows"]:
        caveated_row = triage["rows"][0]
        report_id = caveated_row["report_id"]
        config = yaml.safe_load((ROOT / caveated_row["config_path"]).read_text())
        config_id = f"config:{config['experiment_id']}"
        dataset_id = f"dataset:{caveated_row['dataset_ids'][0]}"

        assert (triage_id, "SUPPORTS_REPORT", report_id) in edges
        assert (
            triage_id,
            "SUPPORTS_REPORT",
            f"{report_id}:feature_leakage_audit",
        ) in edges
        assert (triage_id, "SUMMARIZES_CONFIG", config_id) in edges
        assert (triage_id, "SUMMARIZES_DATASET", dataset_id) in edges
    else:
        assert triage["summary"]["caveat_rows_triaged"] == 0
        assert not any(
            edge[0] == triage_id
            and edge[1] == "SUPPORTS_REPORT"
            and edge[2].endswith(":feature_leakage_audit")
            for edge in edges
        )


def test_feature_provenance_label_backfill_links_updated_sidecars():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    backfill = json.loads(
        (
            ROOT
            / "experiments/regression/reports/methodology_sanity_audit_20260627/feature_leakage_provenance_label_backfill.json"
        ).read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    backfill_id = "report:feature_leakage_provenance_label_backfill"
    assert nodes[backfill_id]["type"] == "report"
    assert nodes[backfill_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/feature_leakage_provenance_label_backfill.json"
    )
    assert (
        backfill_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (
        backfill_id,
        "SUPPORTS_REPORT",
        "report:cross_run_integrity_audit",
    ) in edges

    updated_rows = [row for row in backfill["rows"] if row.get("status") == "updated"]
    assert updated_rows
    row = updated_rows[0]
    report_id = row["report_id"]
    config = yaml.safe_load((ROOT / row["config_path"]).read_text())
    config_id = f"config:{config['experiment_id']}"

    assert (backfill_id, "SUPPORTS_REPORT", report_id) in edges
    assert (
        backfill_id,
        "SUPPORTS_REPORT",
        f"{report_id}:feature_leakage_audit",
    ) in edges
    assert (backfill_id, "SUMMARIZES_CONFIG", config_id) in edges


def test_feature_prediction_metadata_repair_links_repaired_sidecar():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    repair_payload = json.loads(
        (
            ROOT
            / "experiments/regression/reports/methodology_sanity_audit_20260627/feature_leakage_prediction_metadata_repair.json"
        ).read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    repair_id = "report:feature_leakage_prediction_metadata_repair"
    assert nodes[repair_id]["type"] == "report"
    assert nodes[repair_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/feature_leakage_prediction_metadata_repair.json"
    )
    assert (
        repair_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (
        repair_id,
        "SUPPORTS_REPORT",
        "report:cross_run_integrity_audit",
    ) in edges
    assert (
        repair_id,
        "SUPPORTS_REPORT",
        "report:feature_leakage_metadata_completeness_triage",
    ) in edges

    repaired_rows = [
        row for row in repair_payload["rows"] if row.get("status") == "repaired"
    ]
    assert repaired_rows
    row = repaired_rows[0]
    report_id = row["report_id"]
    config = yaml.safe_load((ROOT / row["config_path"]).read_text())
    config_id = f"config:{config['experiment_id']}"
    dataset_id = row["dataset_ids"][0]

    assert (repair_id, "SUPPORTS_REPORT", report_id) in edges
    assert (
        repair_id,
        "SUPPORTS_REPORT",
        f"{report_id}:feature_leakage_audit",
    ) in edges
    assert (repair_id, "SUMMARIZES_CONFIG", config_id) in edges
    assert (repair_id, "SUMMARIZES_DATASET", f"dataset:{dataset_id}") in edges


def test_endpoint_method_coverage_backfill_links_endpoint_sidecars():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    backfill_id = "report:endpoint_method_coverage_backfill"
    report_id = "report:model_family_sweep_stackoverflow_2025_compensation_log1p_age"
    config_id = "config:regression_model_family_sweep_stackoverflow_2025_compensation_log1p_age_v0"
    dataset_id = "dataset:stackoverflow_2025_compensation"

    assert nodes[backfill_id]["type"] == "report"
    assert nodes[backfill_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/endpoint_method_coverage_backfill.json"
    )
    assert (
        backfill_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (
        backfill_id,
        "SUPPORTS_REPORT",
        "report:cross_run_integrity_audit",
    ) in edges
    assert (
        backfill_id,
        "SUPPORTS_REPORT",
        "report:integrity_remediation_backlog",
    ) in edges
    assert (backfill_id, "SUPPORTS_REPORT", report_id) in edges
    assert (backfill_id, "SUPPORTS_REPORT", f"{report_id}:endpoint_audit") in edges
    assert (backfill_id, "SUMMARIZES_CONFIG", config_id) in edges
    assert (backfill_id, "SUMMARIZES_DATASET", dataset_id) in edges


def test_endpoint_schema_feasibility_links_endpoint_sidecars():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    feasibility = json.loads(
        (
            ROOT / "experiments/regression/reports/methodology_sanity_audit_20260627/"
            "endpoint_schema_backfill_feasibility.json"
        ).read_text()
    )

    audit_id = "report:endpoint_schema_backfill_feasibility"
    assert nodes[audit_id]["type"] == "report"
    assert nodes[audit_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/endpoint_schema_backfill_feasibility.json"
    )
    assert (
        audit_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (
        audit_id,
        "SUPPORTS_REPORT",
        "report:cross_run_integrity_audit",
    ) in edges
    assert (
        audit_id,
        "SUPPORTS_REPORT",
        "report:integrity_remediation_backlog",
    ) in edges

    if not feasibility["rows"]:
        assert feasibility["summary"]["ready_count"] == 0
        assert feasibility["summary"]["blocked_count"] == 0
        assert feasibility["summary"]["completed_ledger_rows_ready"] == 0
        return

    row = feasibility["rows"][0]
    config = yaml.safe_load((ROOT / row["config_path"]).read_text())

    report_id = row["report_id"]
    config_id = f"config:{config['experiment_id']}"
    dataset_id = f"dataset:{row['dataset_ids'][0]}"

    assert (audit_id, "SUPPORTS_REPORT", report_id) in edges
    assert (audit_id, "SUPPORTS_REPORT", f"{report_id}:endpoint_audit") in edges
    assert (audit_id, "SUMMARIZES_CONFIG", config_id) in edges
    assert (audit_id, "SUMMARIZES_DATASET", dataset_id) in edges


def test_split_profile_schema_backfill_links_split_sidecars():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    backfill_id = "report:split_profile_schema_backfill"
    report_id = "report:model_family_sweep_openml_auto_price_symboling_log1p"
    config_id = (
        "config:regression_model_family_sweep_openml_auto_price_symboling_log1p_v0"
    )
    dataset_id = "dataset:openml_auto_price"

    assert nodes[backfill_id]["type"] == "report"
    assert nodes[backfill_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/split_profile_schema_backfill.json"
    )
    assert (
        backfill_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (
        backfill_id,
        "SUPPORTS_REPORT",
        "report:cross_run_integrity_audit",
    ) in edges
    assert (
        backfill_id,
        "SUPPORTS_REPORT",
        "report:integrity_remediation_backlog",
    ) in edges
    assert (backfill_id, "SUPPORTS_REPORT", report_id) in edges
    assert (backfill_id, "SUPPORTS_REPORT", f"{report_id}:split_profile") in edges
    assert (backfill_id, "SUMMARIZES_CONFIG", config_id) in edges
    assert (backfill_id, "SUMMARIZES_DATASET", dataset_id) in edges


def test_endpoint_audit_exports_queryable_result_and_caveat_nodes():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    report_name = "model_family_sweep_nhanes_2017_2018_bmi_identity_ridreth3"
    report_id = f"report:{report_name}"
    sidecar_id = f"{report_id}:endpoint_audit"
    config_id = f"config:regression_{report_name}_v0"
    dataset_id = "dataset:nhanes_2017_2018_bmi"

    cqr_result_id = f"endpoint_result:{report_name}:cqr"
    cqr_state_id = f"endpoint_state:{report_name}:cqr"
    assert nodes[cqr_result_id]["type"] == "endpoint_result"
    assert nodes[cqr_result_id]["support_status"] == "clean_endpoint_support_diagnostic"
    assert nodes[cqr_result_id]["runs"] == 153
    assert nodes[cqr_result_id]["lower_below_floor"] == 0
    assert nodes[cqr_result_id]["upper_above_warning"] == 0
    assert nodes[cqr_result_id]["json_path"].endswith(
        f"{report_name}/endpoint_audit.json"
    )
    assert nodes[cqr_state_id]["type"] == "endpoint_state"
    assert nodes[cqr_state_id]["endpoint_state"] == "clean_no_caveat_endpoint_state"
    assert nodes[cqr_state_id]["has_caveat"] is False

    normalized_result_id = f"endpoint_result:{report_name}:normalized_abs"
    normalized_caveat_id = f"endpoint_caveat:{report_name}:normalized_abs"
    normalized_state_id = f"endpoint_state:{report_name}:normalized_abs"
    assert (
        nodes[normalized_result_id]["support_status"] == "boundary_pathology_diagnostic"
    )
    assert nodes[normalized_result_id]["lower_below_floor"] == 2160
    assert nodes[normalized_result_id]["upper_above_warning"] == 2111
    assert nodes[normalized_result_id]["max_width"] > 7_000_000_000
    assert nodes[normalized_caveat_id]["type"] == "endpoint_caveat"
    assert nodes[normalized_caveat_id]["floor_warning_excursions"] == 4271
    assert nodes[normalized_caveat_id]["extreme_width_excursions"] == 2107
    assert nodes[normalized_state_id]["type"] == "endpoint_state"
    assert nodes[normalized_state_id]["endpoint_state"] == "caveated_endpoint_state"
    assert nodes[normalized_state_id]["has_caveat"] is True

    assert (sidecar_id, "SUMMARIZES_ENDPOINT_RESULT", cqr_result_id) in edges
    assert (cqr_result_id, "SUPPORTED_BY_ENDPOINT_AUDIT", sidecar_id) in edges
    assert (cqr_result_id, "EVALUATES_METHOD", "method:cqr") in edges
    assert (cqr_result_id, "SUMMARIZES_DATASET", dataset_id) in edges
    assert (cqr_result_id, "SUMMARIZES_CONFIG", config_id) in edges
    assert (cqr_result_id, "HAS_ENDPOINT_STATE", cqr_state_id) in edges
    assert (cqr_state_id, "SUPPORTED_BY_ENDPOINT_AUDIT", sidecar_id) in edges
    assert (cqr_result_id, "REPORTS_METRIC", "metric:endpoint_crossings") in edges
    assert (normalized_result_id, "HAS_ENDPOINT_STATE", normalized_state_id) in edges
    assert (normalized_result_id, "HAS_CAVEAT", normalized_caveat_id) in edges
    assert (normalized_caveat_id, "SUPPORTED_BY_ENDPOINT_AUDIT", sidecar_id) in edges


def test_legacy_endpoint_audit_aliases_count_fields():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    report_name = "model_family_sweep_openml_sensory_score_method_judges_grouped"
    result_id = f"endpoint_result:{report_name}:mondrian_abs"
    caveat_id = f"endpoint_caveat:{report_name}:mondrian_abs"

    assert nodes[result_id]["type"] == "endpoint_result"
    assert nodes[result_id]["intervals"] == 48960
    assert nodes[result_id]["support_status"] == "observed_support_excursion_diagnostic"
    assert nodes[result_id]["lower_below_floor"] == 0
    assert nodes[result_id]["lower_below_observed_min"] == 1116
    assert nodes[result_id]["upper_above_observed_max"] == 607
    assert nodes[caveat_id]["type"] == "endpoint_caveat"
    assert nodes[caveat_id]["floor_warning_excursions"] == 0
    assert nodes[caveat_id]["observed_support_excursions"] == 1723
    assert (result_id, "HAS_CAVEAT", caveat_id) in edges


def test_catalog_triage_decisions_qualify_non_executed_datasets():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    audit_queued_decision = (
        "decision:dataset_candidate:acs_personal_income_regression:queued_manual_audit"
    )
    source_review_decision = (
        "decision:dataset_candidate:openml_veteran_survival:"
        "audit_passed_source_review_not_runner_queued"
    )

    assert nodes[audit_queued_decision]["type"] == "decision"
    assert nodes[audit_queued_decision]["decision"] == "queued_manual_audit"
    assert (
        audit_queued_decision,
        "DECIDES_DATASET",
        "dataset:acs_personal_income_regression",
    ) in edges
    assert (
        audit_queued_decision,
        "RECORDED_IN",
        "catalog:dataset_candidates",
    ) in edges

    assert nodes[source_review_decision]["type"] == "decision"
    assert (
        source_review_decision,
        "DECIDES_DATASET",
        "dataset:openml_veteran_survival",
    ) in edges


def test_null_openml_exclusions_review_source_without_faking_dataset():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    assert (
        "openml_review:1193",
        "REVIEWS_SOURCE",
        "source:openml_review:1193",
    ) in edges
    assert not any(
        edge[0] == "openml_review:1193" and edge[1] == "DECIDES_DATASET"
        for edge in edges
    )


def test_audit_index_student_variants_have_inherited_source_links():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    for dataset_id in [
        "dataset:uci_student_performance_no_prior_grades",
        "dataset:uci_student_performance_with_prior_grades",
    ]:
        assert nodes[dataset_id]["source"] == "UCI Machine Learning Repository"
        assert (
            dataset_id,
            "FROM_SOURCE",
            "source:UCI Machine Learning Repository",
        ) in edges


def test_publication_readiness_manifest_is_first_class_evidence():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    schema_id = "catalog:manuscript_evidence_manifest_schema"
    report_id = (
        "report:duplicate_cluster_sensitivity_nhanes_2017_2018_bmi_identity_"
        "ridreth3_model_visible"
    )
    manifest_id = (
        "manifest:duplicate_cluster_sensitivity_nhanes_2017_2018_bmi_identity_"
        "ridreth3_model_visible:publication_readiness"
    )

    assert nodes[schema_id]["type"] == "catalog"
    assert nodes[manifest_id]["type"] == "manifest"
    assert nodes[manifest_id]["ledger_path"]
    assert nodes[manifest_id]["target"] == "BMXBMI"
    assert nodes[manifest_id]["target_transform"] == "identity"
    assert nodes[manifest_id]["diagnostic_group"] == "RIDRETH3"
    assert nodes[manifest_id]["planned_atomic_rows"] == 2142
    assert nodes[manifest_id]["completed_rows"] == 1683
    assert nodes[manifest_id]["controlled_skip_count"] == 459
    assert nodes[manifest_id]["failure_count"] == 0
    assert (manifest_id, "MANIFESTS_REPORT", report_id) in edges
    assert (manifest_id, "USES_SCHEMA", schema_id) in edges
    assert (
        manifest_id,
        "SUMMARIZES_DATASET",
        "dataset:nhanes_2017_2018_bmi",
    ) in edges
    assert (
        manifest_id,
        "SUPPORTED_BY",
        f"{report_id}:feature_leakage_audit",
    ) in edges
    assert (manifest_id, "REPORTS_METRIC", "metric:median_width") in edges
    assert (manifest_id, "REPORTS_METRIC", "metric:failure_count") in edges


def test_stackoverflow_publication_manifest_records_completed_ledger_counts():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    report_id = (
        "report:duplicate_cluster_sensitivity_stackoverflow_2025_compensation_"
        "log1p_age_row_signature"
    )
    manifest_id = (
        "manifest:duplicate_cluster_sensitivity_stackoverflow_2025_compensation_"
        "log1p_age_row_signature:publication_readiness"
    )

    assert nodes[manifest_id]["type"] == "manifest"
    assert nodes[manifest_id]["target"] == "ConvertedCompYearly"
    assert nodes[manifest_id]["target_transform"] == "log1p"
    assert nodes[manifest_id]["diagnostic_group"] == "Age"
    assert nodes[manifest_id]["planned_atomic_rows"] == 2184
    assert nodes[manifest_id]["completed_rows"] == 1404
    assert nodes[manifest_id]["controlled_skip_count"] == 780
    assert nodes[manifest_id]["failure_count"] == 0
    assert (manifest_id, "MANIFESTS_REPORT", report_id) in edges
    assert (
        manifest_id,
        "SUMMARIZES_DATASET",
        "dataset:stackoverflow_2025_compensation",
    ) in edges


def test_manuscript_packaging_index_links_extraction_scaffolds():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    bundle_index = "catalog:manuscript_bundle_index"
    protocol = "catalog:publication_readiness_protocol"
    assert nodes[bundle_index]["type"] == "catalog"
    assert nodes[bundle_index]["path"].endswith("manuscript_bundle_index.json")
    assert nodes[protocol]["type"] == "catalog"
    assert nodes[protocol]["path"].endswith("PUBLICATION_READINESS_PROTOCOL.md")
    assert (
        "catalog:knowledge_graph",
        "CITES_SOURCES",
        bundle_index,
    ) in edges
    assert (
        "catalog:knowledge_graph",
        "CITES_SOURCES",
        protocol,
    ) in edges
    post_program = "catalog:post_experiment_publication_program"
    assert nodes[post_program]["type"] == "catalog"
    assert nodes[post_program]["json_path"].endswith(
        "post_experiment_publication_program.json"
    )
    assert (
        "catalog:knowledge_graph",
        "CITES_SOURCES",
        post_program,
    ) in edges
    assert (
        post_program,
        "DERIVED_FROM",
        "catalog:manuscript_paper_readiness_map",
    ) in edges
    assert (
        protocol,
        "CITES_SOURCES",
        "catalog:manuscript_evidence_manifest_schema",
    ) in edges
    assert (
        "catalog:manuscript_bundle_index_md",
        "RENDERS",
        bundle_index,
    ) in edges

    for table_id in [
        "catalog:manuscript_workspace_readme",
        "catalog:manuscript_dataset_table",
        "catalog:manuscript_method_table",
        "catalog:manuscript_main_results_table",
        "catalog:manuscript_robustness_results_table",
        "catalog:manuscript_negative_results_table",
        "catalog:manuscript_evidence_view",
        "catalog:manuscript_figure_index",
        "catalog:manuscript_figure_specs_readme",
        "catalog:post_experiment_publication_program",
    ]:
        assert nodes[table_id]["type"] == "catalog"
        assert (table_id, "DERIVED_FROM", bundle_index) in edges
        assert (table_id, "CITES_SOURCES", protocol) in edges

    assert (
        "catalog:manuscript_dataset_table",
        "CITES_SOURCES",
        "catalog:source_registry",
    ) in edges
    assert (
        "catalog:manuscript_method_table",
        "CITES_SOURCES",
        "catalog:method_registry",
    ) in edges
    bundle_payload = json.loads(
        (
            ROOT / "experiments/regression/catalogs/manuscript_bundle_index.json"
        ).read_text()
    )
    for bundle in bundle_payload["bundles"]:
        manifest_path = Path(bundle["manifest_path"])
        manifest_id = f"manifest:{manifest_path.parent.name}:publication_readiness"
        assert nodes[manifest_id]["type"] == "manifest"
        assert (bundle_index, "INDEXES_MANIFEST", manifest_id) in edges


def test_post_experiment_publication_activation_audit_is_traceable_stop_go():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    catalog_id = "catalog:post_experiment_publication_activation_audit"
    report_id = "report:post_experiment_publication_activation_audit"
    blocked_gate_check_id = (
        "methodology_control:post_experiment_publication_activation:"
        "positive_claim_blockers_guarded_for_neutral_route"
    )
    goal_completion_id = "report:goal_completion_audit"

    assert nodes[catalog_id]["type"] == "catalog"
    assert nodes[catalog_id]["json_path"].endswith(
        "post_experiment_publication_activation_audit.json"
    )
    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "post_experiment_publication_activation_audit.json"
    )
    assert nodes[blocked_gate_check_id]["type"] == "methodology_control"
    assert nodes[blocked_gate_check_id]["status"] == "pass"
    assert nodes[blocked_gate_check_id]["blocks_activation"] is False
    assert (
        "catalog:knowledge_graph",
        "CITES_SOURCES",
        catalog_id,
    ) in edges
    assert (catalog_id, "RENDERS", report_id) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "catalog:post_experiment_publication_program",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:manuscript_readiness_map",
    ) in edges
    assert (report_id, "DERIVED_FROM", goal_completion_id) in edges
    assert (goal_completion_id, "DERIVED_FROM", report_id) in edges
    assert (report_id, "SUMMARIZES_CONTROL", blocked_gate_check_id) in edges


def test_publication_preparation_packets_are_traceable_pre_prose_controls():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {
        (edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]
    }

    report_id = "report:publication_preparation_packets"
    reviewer_id = "publication_reviewer:statistical_methodology_reviewer"
    visual_family_id = (
        "methodology_control:publication_preparation_visual_inventory:"
        "venn_abers_failure_mode_evidence"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "publication_preparation_packets.json"
    )
    assert nodes[reviewer_id]["type"] == "reviewer_perspective"
    assert nodes[visual_family_id]["type"] == "methodology_control"
    assert nodes[visual_family_id]["final_retain_decision"] == "not_started"
    assert "candidate-only" in nodes[visual_family_id]["summary"]
    for source_id in [
        "catalog:post_experiment_publication_program",
        "report:post_experiment_publication_activation_audit",
        "report:goal_completion_audit",
        "report:kg_publication_quality_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
    assert (report_id, "SUMMARIZES_CONTROL", reviewer_id) in edges
    assert (report_id, "SUMMARIZES_CONTROL", visual_family_id) in edges


def test_reviewer_design_reconciliation_is_traceable_design_only_control():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:reviewer_design_reconciliation"
    advice_id = (
        "methodology_control:reviewer_design_advice:"
        "statistical_methodology_reviewer_r01"
    )
    content_id = (
        "methodology_control:reviewer_design_content_matrix:"
        "venn_abers_failure_mode_evidence"
    )
    site_id = "methodology_control:reviewer_design_publication_site_decision"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith("reviewer_design_brief.json")
    assert "positive claims blocked" in nodes[report_id]["summary"]
    assert nodes[advice_id]["type"] == "methodology_control"
    assert (
        nodes[advice_id]["decision_scope"]
        == "publication_design_only_no_final_prose_no_retained_visuals"
    )
    assert nodes[content_id]["type"] == "methodology_control"
    assert nodes[content_id]["final_placement_decision"] == "not_started"
    assert nodes[content_id]["retained_visual_or_table_decision"] == "not_started"
    assert nodes[site_id]["type"] == "methodology_control"
    assert nodes[site_id]["site_decision_status"] == (
        "deferred_until_release_gates_pass"
    )
    assert nodes[site_id]["site_deployment_authorized"] is False
    for source_id in [
        "report:publication_preparation_packets",
        "catalog:post_experiment_publication_program",
        "report:post_experiment_publication_activation_audit",
        "report:neutral_reporting_language_audit",
        "report:goal_completion_audit",
        "report:paper_gate_closure_map",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith("reviewer_design_brief.json")
        assert edge["evidence"].startswith("$.sources.")
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (report_id, "SUMMARIZES_CONTROL", advice_id) in edges
    assert (report_id, "SUMMARIZES_CONTROL", content_id) in edges
    assert (report_id, "SUMMARIZES_CONTROL", site_id) in edges


def test_publication_visual_audit_plan_links_candidates_and_triptych_controls():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:publication_visual_table_audit_plan"
    triptych_report_id = "report:article_supplement_kg_triptych_decision"
    item_id = (
        "methodology_control:publication_visual_audit_item:"
        "venn_abers_failure_mode_evidence"
    )
    quality_check_id = (
        "methodology_control:publication_visual_quality_check:"
        "no_overlapping_text_or_marks"
    )
    component_id = (
        "methodology_control:article_supplement_kg_triptych_component:"
        "knowledge_graph_or_publication_site"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith("visual_table_audit_plan.json")
    assert "no retained visuals" in nodes[report_id]["summary"]
    assert nodes[item_id]["type"] == "methodology_control"
    assert nodes[item_id]["audit_status"] == "planned_not_started"
    assert nodes[item_id]["auditor_decision"] == "not_started"
    assert nodes[item_id]["final_retention_authorized"] is False
    assert nodes[item_id]["retained_visual_or_table_decision"] == "not_started"
    assert nodes[quality_check_id]["type"] == "methodology_control"
    assert nodes[triptych_report_id]["type"] == "report"
    assert nodes[triptych_report_id]["json_path"].endswith(
        "article_supplement_kg_triptych_decision.json"
    )
    assert nodes[component_id]["type"] == "methodology_control"
    assert nodes[component_id]["decision_status"] == (
        "candidate_deferred_until_kg_usability_release_gates"
    )
    assert nodes[component_id]["final_release_authorized"] is False
    assert nodes[component_id]["citable_component_authorized"] is False
    for source_id in [
        "catalog:post_experiment_publication_program",
        "report:reviewer_design_reconciliation",
        "report:neutral_reporting_language_audit",
        "report:knowledge_graph_quality_summary",
        "report:kg_publication_quality_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith("visual_table_audit_plan.json")
        assert edge["evidence"].startswith("$.sources.")
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (
        triptych_report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (report_id, "SUMMARIZES_CONTROL", item_id) in edges
    assert (report_id, "SUMMARIZES_CONTROL", quality_check_id) in edges
    assert (triptych_report_id, "SUMMARIZES_CONTROL", component_id) in edges
    assert (triptych_report_id, "DERIVED_FROM", report_id) in edges


def test_visual_table_audit_report_links_pre_retention_controls_and_sidecars():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:publication_visual_table_audit_report"
    item_id = (
        "methodology_control:publication_visual_table_audit_execution:"
        "venn_abers_failure_mode_evidence"
    )
    sidecar_ids = {
        "report:visual_table_inventory",
        "report:visual_table_iteration_register",
        "report:kg_navigation_usability_audit",
    }

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith("visual_table_audit_report.json")
    assert "Pre-retention visual/table audit report" in nodes[report_id]["summary"]
    assert nodes[item_id]["type"] == "methodology_control"
    assert nodes[item_id]["pre_retention_audit_status"] == "completed"
    assert nodes[item_id]["pre_retention_auditor_decision"] == (
        "revise_claim_boundary_before_main_article_use"
    )
    assert nodes[item_id]["source_traceability_status"] == "pass"
    assert nodes[item_id]["layout_overlap_check_status"] == (
        "deferred_until_rendered_artifact"
    )
    assert nodes[item_id]["iteration_required"] is True
    assert nodes[item_id]["final_retention_authorized"] is False
    assert nodes[item_id]["retained_visual_or_table_decision"] == "not_started"
    for source_id in [
        "report:publication_visual_table_audit_plan",
        "report:reviewer_design_reconciliation",
        "report:neutral_reporting_language_audit",
        "report:knowledge_graph_quality_summary",
        "report:kg_publication_quality_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith("visual_table_audit_report.json")
        assert edge["evidence"].startswith("$.sources.")
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (report_id, "SUMMARIZES_CONTROL", item_id) in edges
    for sidecar_id in sidecar_ids:
        assert nodes[sidecar_id]["type"] == "report"
        assert (sidecar_id, "DERIVED_FROM", report_id) in edges
        assert (
            sidecar_id,
            "SUPPORTS_REPORT",
            "report:methodology_sanity_audit_20260627",
        ) in edges


def test_visual_table_render_candidate_audit_links_layout_controls_and_sidecars():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:publication_visual_table_render_candidate_audit"
    control_id = (
        "methodology_control:publication_visual_table_render_candidate:"
        "venn_abers_failure_mode_evidence"
    )
    pre_retention_control_id = (
        "methodology_control:publication_visual_table_audit_execution:"
        "venn_abers_failure_mode_evidence"
    )
    sidecar_ids = {
        "report:visual_table_render_candidate_inventory",
        "report:visual_table_layout_quality_audit",
    }

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "visual_table_render_candidate_audit.json"
    )
    assert "Draft visual/table render candidate audit" in nodes[report_id]["summary"]
    assert nodes[control_id]["type"] == "methodology_control"
    assert nodes[control_id]["render_kind"] == "svg_bar_chart_plus_markdown_table"
    assert nodes[control_id]["draft_render_status"] == "rendered_draft_candidate"
    assert nodes[control_id]["layout_quality_status"] == "pass"
    assert nodes[control_id]["caption_quality_status"] == "pass"
    assert nodes[control_id]["source_traceability_status"] == "pass"
    assert nodes[control_id]["svg_static_text_overlap_detected"] is False
    assert nodes[control_id]["final_retention_authorized"] is False
    assert nodes[control_id]["positive_claim_promotion_authorized"] is False
    assert nodes[control_id]["primary_rendered_artifact_path"].endswith(
        "venn_abers_failure_mode_evidence.svg"
    )
    for source_id in [
        "report:publication_visual_table_audit_report",
        "report:visual_table_inventory",
        "report:visual_table_iteration_register",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith(
            "visual_table_render_candidate_audit.json"
        )
        assert edge["evidence"].startswith("$.sources.")
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (report_id, "SUMMARIZES_CONTROL", control_id) in edges
    assert (control_id, "DERIVED_FROM", pre_retention_control_id) in edges
    for sidecar_id in sidecar_ids:
        assert nodes[sidecar_id]["type"] == "report"
        assert (sidecar_id, "DERIVED_FROM", report_id) in edges
        assert (
            sidecar_id,
            "SUPPORTS_REPORT",
            "report:methodology_sanity_audit_20260627",
        ) in edges


def test_publication_retention_readiness_links_recommendation_controls():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:publication_retention_readiness_audit"
    matrix_id = "report:article_supplement_retention_recommendation_matrix"
    control_id = (
        "methodology_control:publication_retention_recommendation:"
        "method_performance_descriptive_summary"
    )
    render_control_id = (
        "methodology_control:publication_visual_table_render_candidate:"
        "method_performance_descriptive_summary"
    )
    methodology_report_id = "report:methodology_sanity_audit_20260627"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "publication_retention_readiness_audit.json"
    )
    assert "retention-readiness" in nodes[report_id]["summary"]
    assert nodes[control_id]["type"] == "methodology_control"
    assert nodes[control_id]["recommendation_status"] == (
        "recommendation_ready_no_final_retention"
    )
    assert nodes[control_id]["recommended_surface"] == (
        "main_article_candidate_after_final_prose_gate"
    )
    assert nodes[control_id]["retention_readiness_decision"] == (
        "candidate_ready_for_final_prose_stage_review"
    )
    assert nodes[control_id]["final_retention_authorized"] is False
    assert nodes[control_id]["final_visual_table_retention_authorized"] is False
    assert nodes[control_id]["final_manuscript_prose_permission"] is False
    assert nodes[control_id]["positive_claim_promotion_authorized"] is False
    assert nodes[control_id]["source_traceability_artifact_status"] == "pass"
    assert nodes[matrix_id]["type"] == "report"
    assert nodes[matrix_id]["json_path"].endswith(
        "article_supplement_retention_recommendation_matrix.json"
    )

    for source_id in [
        "report:publication_visual_table_render_candidate_audit",
        "report:visual_table_layout_quality_audit",
        "report:reviewer_design_reconciliation",
        "report:neutral_result_ledger",
        "report:neutral_reporting_language_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith(
            "publication_retention_readiness_audit.json"
        )
        assert edge["evidence"].startswith("$.sources.")

    assert (report_id, "SUPPORTS_REPORT", methodology_report_id) in edges
    assert (report_id, "SUMMARIZES_CONTROL", control_id) in edges
    assert (control_id, "DERIVED_FROM", render_control_id) in edges
    assert (matrix_id, "DERIVED_FROM", report_id) in edges
    assert (matrix_id, "SUPPORTS_REPORT", report_id) in edges
    assert (matrix_id, "SUPPORTS_REPORT", methodology_report_id) in edges
    assert edge_by_triple[
        (matrix_id, "SUPPORTS_REPORT", methodology_report_id)
    ]["evidence_path"].endswith(
        "article_supplement_retention_recommendation_matrix.json"
    )


def test_final_publication_visual_auditor_readiness_links_feedback_controls():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:final_publication_visual_auditor_readiness"
    control_id = (
        "methodology_control:final_publication_visual_auditor:"
        "method_performance_descriptive_summary"
    )
    retention_control_id = (
        "methodology_control:publication_retention_recommendation:"
        "method_performance_descriptive_summary"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "final_publication_visual_auditor_readiness.json"
    )
    assert "feedback-loop readiness" in nodes[report_id]["summary"]
    assert nodes[control_id]["type"] == "methodology_control"
    assert nodes[control_id]["visual_auditor_feedback_status"] == (
        "feedback_ready_no_final_retention"
    )
    assert nodes[control_id]["feedback_item_count"] >= 3
    assert nodes[control_id]["layout_quality_status"] == "pass"
    assert nodes[control_id]["caption_quality_status"] == "pass"
    assert nodes[control_id]["source_traceability_status"] == "pass"
    assert nodes[control_id]["svg_static_text_overlap_detected"] is False
    assert nodes[control_id]["final_retention_authorized"] is False
    assert nodes[control_id]["final_visual_table_retention_authorized"] is False
    assert nodes[control_id]["final_manuscript_prose_permission"] is False
    assert nodes[control_id]["method_recommendation_authorized"] is False
    assert nodes[control_id]["positive_claim_promotion_authorized"] is False

    for source_id in [
        "report:publication_visual_table_render_candidate_audit",
        "report:publication_retention_readiness_audit",
        "report:publication_visual_table_audit_report",
        "report:reviewer_design_reconciliation",
        "report:section_claim_boundary_audit",
        "report:neutral_reporting_language_audit",
        "report:publication_release_gap_register",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith(
            "final_publication_visual_auditor_readiness.json"
        )
        assert edge["evidence"].startswith("$.sources.")

    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (report_id, "SUMMARIZES_CONTROL", control_id) in edges
    assert (control_id, "DERIVED_FROM", retention_control_id) in edges
    assert (
        control_id,
        "DERIVED_FROM",
        "report:publication_retention_readiness_audit",
    ) in edges


def test_final_publication_output_authorization_protocol_links_blocker_controls():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:final_publication_output_authorization_protocol"
    control_id = (
        "methodology_control:final_publication_output_authorization:"
        "method_recommendation_not_authorized"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "final_publication_output_authorization_protocol.json"
    )
    assert "active final-output blockers" in nodes[report_id]["summary"]
    assert nodes[control_id]["type"] == "methodology_control"
    assert nodes[control_id]["authorization_status"] == (
        "blocked_no_final_authorization"
    )
    assert nodes[control_id]["output_family"] == "method_recommendation"
    assert nodes[control_id]["ready_to_authorize"] is False
    assert nodes[control_id]["final_output_authorized"] is False
    assert nodes[control_id]["method_recommendation_authorized"] is False
    assert nodes[control_id]["positive_claim_promotion_authorized"] is False

    for source_id in [
        "report:goal_completion_audit",
        "report:publication_phase_progress_reconciliation_audit",
        "report:publication_release_gap_register",
        "report:scientific_neutrality_interpretation_lock",
        "report:final_publication_visual_auditor_readiness",
        "report:section_claim_boundary_audit",
        "report:article_supplement_kg_navigation_index",
        "report:paper_gate_closure_map",
        "report:kg_publication_quality_audit",
        "report:knowledge_graph_quality_summary",
        "report:neutral_reporting_language_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith(
            "final_publication_output_authorization_protocol.json"
        )
        assert edge["evidence"].startswith("$.sources.")

    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (report_id, "SUMMARIZES_CONTROL", control_id) in edges
    assert (
        control_id,
        "DERIVED_FROM",
        "report:publication_phase_progress_reconciliation_audit",
    ) in edges
    assert (
        control_id,
        "DERIVED_FROM",
        "report:scientific_neutrality_interpretation_lock",
    ) in edges


def test_publication_claim_evidence_verification_matrix_links_evidence_controls():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:publication_claim_evidence_verification_matrix"
    main_id = (
        "methodology_control:publication_claim_evidence_verification:"
        "paper_main_results_blocked_evidence"
    )
    venn_id = (
        "methodology_control:publication_claim_evidence_verification:"
        "supplement_venn_abers_negative_evidence"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "publication_claim_evidence_verification_matrix.json"
    )
    assert "no-method-advocacy reporting" in nodes[report_id]["summary"]
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (
        "report:retrospective_quality_gate",
        "DERIVED_FROM",
        report_id,
    ) in edges

    for source_id in [
        "report:claim_safe_result_extraction_matrix",
        "report:manuscript_section_evidence_packet",
        "report:section_claim_boundary_audit",
        "report:article_supplement_kg_navigation_index",
        "report:final_publication_output_authorization_protocol",
        "report:scientific_neutrality_interpretation_lock",
        "report:publication_release_gap_register",
        "report:neutral_reporting_language_audit",
        "report:knowledge_graph_quality_summary",
        "report:publication_citation_registry",
        "report:main_article_draft",
        "report:supplementary_document_draft",
        "report:individual_experiment_report_draft",
        "report:sterile_repository_readme_draft",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith(
            "publication_claim_evidence_verification_matrix.json"
        )
        assert edge["evidence"].startswith("$.sources.")

    control_nodes = [
        node_id
        for node_id in nodes
        if node_id.startswith(
            "methodology_control:publication_claim_evidence_verification:"
        )
    ]
    assert len(control_nodes) == 8

    draft_nodes = [
        node_id
        for node_id in nodes
        if node_id.startswith(
            "methodology_control:publication_claim_evidence_draft_artifact:"
        )
    ]
    assert len(draft_nodes) == 6

    main_draft_id = (
        "methodology_control:publication_claim_evidence_draft_artifact:"
        "main_article_draft"
    )
    sterile_readme_id = (
        "methodology_control:publication_claim_evidence_draft_artifact:"
        "sterile_repository_readme_draft"
    )
    research_document_id = (
        "methodology_control:publication_claim_evidence_draft_artifact:"
        "research_document"
    )
    assert nodes[main_draft_id]["verification_status"] == "pass"
    assert nodes[main_draft_id]["source_traceability_status"] == "pass"
    assert nodes[main_draft_id]["method_champion_authorized"] is False
    assert nodes[main_draft_id]["positive_claim_promotion_authorized"] is False
    assert (report_id, "SUMMARIZES_CONTROL", main_draft_id) in edges
    assert (main_draft_id, "DERIVED_FROM", "report:main_article_draft") in edges
    assert (
        main_draft_id,
        "DERIVED_FROM",
        "report:publication_citation_registry",
    ) in edges
    assert nodes[sterile_readme_id]["verification_status"] == "pass"
    assert nodes[research_document_id]["verification_status"] == "pass"
    assert (
        research_document_id,
        "DERIVED_FROM",
        "report:publication_claim_evidence_verification_matrix",
    ) in edges
    assert (research_document_id, "DERIVED_FROM", "report:main_article_draft") in edges
    assert (
        sterile_readme_id,
        "DERIVED_FROM",
        "report:sterile_repository_staging_manifest",
    ) in edges

    assert nodes[main_id]["verification_status"] == "pass"
    assert nodes[main_id]["safe_pre_prose_evidence_packet"] is False
    assert nodes[main_id]["positive_claim_packet_blocked"] is True
    assert nodes[main_id]["main_results_positive_boundary_blocked"] is True
    assert nodes[main_id]["method_champion_authorized"] is False
    assert nodes[main_id]["method_advocacy_authorized"] is False
    assert nodes[main_id]["positive_claim_promotion_authorized"] is False
    assert (report_id, "SUMMARIZES_CONTROL", main_id) in edges
    main_edge = edge_by_triple[(report_id, "SUMMARIZES_CONTROL", main_id)]
    assert main_edge["evidence"] == "verification_rows[2].verification_id"
    for target_id in [
        "methodology_control:manuscript_section_evidence_packet:paper_main_results_blocked_evidence",
        "methodology_control:section_claim_boundary_audit:paper_main_results_blocked_evidence",
        "methodology_control:article_supplement_kg_navigation_index:paper_main_results_blocked_evidence",
        "methodology_control:claim_safe_result_extraction:main_results_table",
        "methodology_control:neutral_result_ledger:selection_multiplicity_robustness_diagnostic",
        "report:final_selection_claim_boundary_audit",
    ]:
        assert (main_id, "DERIVED_FROM", target_id) in edges

    assert nodes[venn_id]["verification_status"] == "pass"
    assert nodes[venn_id]["safe_pre_prose_evidence_packet"] is True
    assert nodes[venn_id]["positive_claim_packet_blocked"] is False
    assert nodes[venn_id]["venn_abers_negative_boundary_preserved"] is True
    assert nodes[venn_id]["method_champion_authorized"] is False
    assert nodes[venn_id]["method_advocacy_authorized"] is False
    assert nodes[venn_id]["positive_claim_promotion_authorized"] is False
    assert (report_id, "SUMMARIZES_CONTROL", venn_id) in edges
    venn_edge = edge_by_triple[(report_id, "SUMMARIZES_CONTROL", venn_id)]
    assert venn_edge["evidence"] == "verification_rows[4].verification_id"
    for target_id in [
        "methodology_control:claim_safe_result_extraction:negative_results_table",
        "methodology_control:neutral_result_ledger:venn_abers_regression_negative_evidence",
        "report:venn_abers_negative_evidence_disposition_audit",
        "report:neutral_reporting_language_audit",
    ]:
        assert (venn_id, "DERIVED_FROM", target_id) in edges


def test_reader_method_primer_citation_map_links_concepts_and_sources():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:reader_method_primer_citation_map"
    cqr_id = (
        "methodology_control:reader_method_primer:"
        "conformalized_quantile_regression_cqr"
    )
    cv_id = "methodology_control:reader_method_primer:jackknife_plus_and_cv_plus"
    venn_id = (
        "methodology_control:reader_method_primer:"
        "venn_abers_predictive_distributions"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "reader_method_primer_citation_map.json"
    )
    assert "non-specialist conformal prediction" in nodes[report_id]["summary"]
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    for source_id in [
        "report:method_literature_coverage_audit",
        "report:publication_claim_evidence_verification_matrix",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith(
            "reader_method_primer_citation_map.json"
        )

    control_nodes = [
        node_id
        for node_id in nodes
        if node_id.startswith("methodology_control:reader_method_primer:")
    ]
    assert len(control_nodes) == 12

    assert nodes[cqr_id]["primary_source_urls"] == [
        "https://arxiv.org/abs/1905.03222"
    ]
    assert nodes[cqr_id]["reader_explanation_outline_count"] == 3
    assert any(
        "calibration score" in item
        for item in nodes[cqr_id]["reader_explanation_outline"]
    )
    assert nodes[cqr_id]["method_champion_authorized"] is False
    assert nodes[cqr_id]["positive_claim_promotion_authorized"] is False
    assert nodes[cv_id]["primary_source_url_count"] == 2
    assert "https://arxiv.org/abs/1905.02928" in nodes[cv_id][
        "primary_source_urls"
    ]
    assert nodes[venn_id]["primary_source_url_count"] == 4
    assert "not to imply a validated regression-interval recommendation" in nodes[
        venn_id
    ]["citation_use_note"]
    assert nodes[venn_id]["method_recommendation_authorized"] is False
    assert (report_id, "SUMMARIZES_CONTROL", cqr_id) in edges
    assert (report_id, "SUMMARIZES_CONTROL", cv_id) in edges
    assert (report_id, "SUMMARIZES_CONTROL", venn_id) in edges


def test_publication_citation_registry_links_bibtex_sources_and_primer_concepts():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:publication_citation_registry"
    cqr_id = (
        "methodology_control:publication_citation_registry:"
        "romano2019conformalized_quantile_regression"
    )
    cv_id = (
        "methodology_control:publication_citation_registry:"
        "barber2020jackknife_plus"
    )
    venn_id = "methodology_control:publication_citation_registry:nouretdinov2018ivapd"
    crc_id = (
        "methodology_control:publication_citation_registry:"
        "angelopoulos2025conformal_risk_control"
    )
    cqr_concept_id = (
        "methodology_control:reader_method_primer:"
        "conformalized_quantile_regression_cqr"
    )
    cv_concept_id = (
        "methodology_control:reader_method_primer:jackknife_plus_and_cv_plus"
    )
    venn_concept_id = (
        "methodology_control:reader_method_primer:"
        "venn_abers_predictive_distributions"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "publication_citation_registry.json"
    )
    assert "stable citation keys and BibTeX entries" in nodes[report_id]["summary"]
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    for source_id in [
        "report:reader_method_primer_citation_map",
        "report:method_literature_coverage_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith("publication_citation_registry.json")

    citation_nodes = [
        node_id
        for node_id in nodes
        if node_id.startswith("methodology_control:publication_citation_registry:")
    ]
    assert len(citation_nodes) == 15

    assert nodes[cqr_id]["entry_type"] == "misc"
    assert nodes[cqr_id]["url"] == "https://arxiv.org/abs/1905.03222"
    assert nodes[cqr_id]["source_role"] == "primer_and_literature"
    assert "conformalized_quantile_regression_cqr" in nodes[cqr_id][
        "covered_primer_concept_ids"
    ]
    assert nodes[cqr_id]["method_champion_authorized"] is False
    assert nodes[cqr_id]["positive_claim_promotion_authorized"] is False
    assert (report_id, "SUMMARIZES_CONTROL", cqr_id) in edges
    assert (cqr_id, "DERIVED_FROM", cqr_concept_id) in edges

    assert nodes[cv_id]["source_role"] == "primer_and_literature"
    assert nodes[cv_id]["covered_literature_requirement_ids"] == [
        "plus_family_and_resampling"
    ]
    assert (cv_id, "DERIVED_FROM", cv_concept_id) in edges

    assert nodes[venn_id]["source_role"] == "primer_and_literature"
    assert nodes[venn_id]["covered_primer_concept_ids"] == [
        "venn_abers_predictive_distributions"
    ]
    assert (venn_id, "DERIVED_FROM", venn_concept_id) in edges

    assert nodes[crc_id]["source_role"] == "literature"
    assert nodes[crc_id]["covered_primer_concept_ids"] == []
    assert nodes[crc_id]["method_recommendation_authorized"] is False


def test_individual_experiment_report_draft_links_sections_and_sources():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:individual_experiment_report_draft"
    primer_section_id = (
        "methodology_control:individual_experiment_report_draft:reader_primer"
    )
    method_section_id = (
        "methodology_control:individual_experiment_report_draft:method_findings"
    )
    blocked_section_id = (
        "methodology_control:individual_experiment_report_draft:"
        "negative_and_blocked_claims"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "individual_experiment_report_draft.json"
    )
    assert "Evidence-linked individual experiment report draft" in nodes[
        report_id
    ]["summary"]
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    for source_id in [
        "report:experiment_accounting_audit",
        "report:method_performance_synthesis",
        "report:method_selection_robustness_audit",
        "report:venn_abers_negative_evidence_disposition_audit",
        "report:bounded_support_endpoint_closure_audit",
        "report:fairness_population_readiness_audit",
        "report:publication_citation_registry",
        "report:reader_primer_section_alignment",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith("individual_experiment_report_draft.json")

    section_nodes = [
        node_id
        for node_id in nodes
        if node_id.startswith(
            "methodology_control:individual_experiment_report_draft:"
        )
    ]
    assert len(section_nodes) == 6

    assert nodes[primer_section_id]["evidence_source_count"] == 2
    assert nodes[primer_section_id]["method_recommendation_authorized"] is False
    assert (report_id, "SUMMARIZES_CONTROL", primer_section_id) in edges
    assert (
        primer_section_id,
        "DERIVED_FROM",
        "report:publication_citation_registry",
    ) in edges
    assert (
        primer_section_id,
        "DERIVED_FROM",
        "report:reader_primer_section_alignment",
    ) in edges

    assert nodes[method_section_id]["evidence_source_count"] == 2
    assert (
        method_section_id,
        "DERIVED_FROM",
        "report:method_performance_synthesis",
    ) in edges
    assert (
        method_section_id,
        "DERIVED_FROM",
        "report:method_selection_robustness_audit",
    ) in edges

    assert nodes[blocked_section_id]["positive_claim_promotion_authorized"] is False
    assert (
        blocked_section_id,
        "DERIVED_FROM",
        "report:venn_abers_grid_failure_mode_decomposition",
    ) in edges
    assert (
        blocked_section_id,
        "DERIVED_FROM",
        "report:fairness_population_readiness_audit",
    ) in edges


def test_manuscript_claim_citation_readiness_audit_links_documents_concepts_and_citations():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:manuscript_claim_citation_readiness_audit"
    main_id = (
        "methodology_control:manuscript_claim_citation_readiness:"
        "main_article_draft"
    )
    supplement_id = (
        "methodology_control:manuscript_claim_citation_readiness:"
        "supplementary_document_draft"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "manuscript_claim_citation_readiness_audit.json"
    )
    assert "claim/citation readiness" in nodes[report_id]["summary"]
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    for source_id in [
        "report:main_article_draft",
        "report:supplementary_document_draft",
        "report:publication_citation_registry",
        "report:reader_method_primer_citation_map",
        "report:publication_claim_evidence_verification_matrix",
        "report:final_publication_output_authorization_protocol",
        "report:knowledge_graph_quality_summary",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith(
            "manuscript_claim_citation_readiness_audit.json"
        )
        assert edge["evidence"].startswith("$.sources.")

    assert nodes[main_id]["readiness_status"] == "pass"
    assert nodes[main_id]["used_citation_key_count"] == 8
    assert nodes[main_id]["missing_concept_count"] == 0
    assert nodes[main_id]["final_manuscript_prose_permission"] is False
    assert nodes[main_id]["method_champion_authorized"] is False
    assert nodes[main_id]["positive_claim_promotion_authorized"] is False
    assert (report_id, "SUMMARIZES_CONTROL", main_id) in edges
    assert (main_id, "DERIVED_FROM", "report:main_article_draft") in edges
    assert (
        main_id,
        "DERIVED_FROM",
        "methodology_control:reader_method_primer:"
        "conformalized_quantile_regression_cqr",
    ) in edges
    assert (
        main_id,
        "DERIVED_FROM",
        "methodology_control:publication_citation_registry:"
        "romano2019conformalized_quantile_regression",
    ) in edges

    assert nodes[supplement_id]["readiness_status"] == "pass"
    assert nodes[supplement_id]["used_citation_key_count"] == 9
    assert nodes[supplement_id]["missing_concept_count"] == 0
    assert nodes[supplement_id]["method_advocacy_authorized"] is False
    assert nodes[supplement_id]["positive_claim_promotion_authorized"] is False
    assert (report_id, "SUMMARIZES_CONTROL", supplement_id) in edges
    assert (
        supplement_id,
        "DERIVED_FROM",
        "report:supplementary_document_draft",
    ) in edges
    assert (
        supplement_id,
        "DERIVED_FROM",
        "methodology_control:reader_method_primer:"
        "weighted_conformal_covariate_shift",
    ) in edges
    assert (
        supplement_id,
        "DERIVED_FROM",
        "methodology_control:publication_citation_registry:"
        "tibshirani2020covariate_shift",
    ) in edges
    assert (
        supplement_id,
        "DERIVED_FROM",
        "methodology_control:publication_citation_registry:"
        "vanderlaan2025generalized_venn_abers",
    ) in edges


def test_neutral_publication_release_cut_links_private_packaging_actions():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:neutral_publication_release_cut_decision"
    private_repo_id = (
        "methodology_control:neutral_publication_release_cut:"
        "prepare_private_sterile_repository"
    )
    article_id = (
        "methodology_control:neutral_publication_release_cut:"
        "assemble_neutral_article_and_supplement_outputs"
    )
    kg_id = (
        "methodology_control:neutral_publication_release_cut:"
        "export_citable_knowledge_graph_snapshot"
    )
    site_id = (
        "methodology_control:neutral_publication_release_cut:"
        "prepare_latex_html_and_static_site_package"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "neutral_publication_release_cut_decision.json"
    )
    assert "private sterile packaging" in nodes[report_id]["summary"]
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    for source_id in [
        "report:final_publication_output_authorization_protocol",
        "report:manuscript_claim_citation_readiness_audit",
        "report:publication_claim_evidence_verification_matrix",
        "report:main_article_draft",
        "report:supplementary_document_draft",
        "report:individual_experiment_report_draft",
        "report:sterile_repository_staging_manifest",
        "report:sterile_repository_readme_draft",
        "report:knowledge_graph_quality_summary",
        "report:graph_artifact_readiness_audit",
        "report:neutral_reporting_language_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith(
            "neutral_publication_release_cut_decision.json"
        )
        assert edge["evidence"].startswith("$.sources.")

    for node_id in [private_repo_id, article_id, kg_id, site_id]:
        assert nodes[node_id]["type"] == "methodology_control"
        assert nodes[node_id]["private_packaging_authorized"] is True
        assert nodes[node_id]["public_release_authorized"] is False
        assert nodes[node_id]["working_repository_final_citable"] is False
        assert nodes[node_id]["method_recommendation_authorized"] is False
        assert nodes[node_id]["method_champion_authorized"] is False
        assert nodes[node_id]["method_advocacy_authorized"] is False
        assert nodes[node_id]["positive_claim_promotion_authorized"] is False
        assert nodes[node_id]["raw_data_or_secret_inclusion_authorized"] is False
        assert (report_id, "SUMMARIZES_CONTROL", node_id) in edges

    assert (
        private_repo_id,
        "DERIVED_FROM",
        "report:sterile_repository_staging_manifest",
    ) in edges
    assert (
        private_repo_id,
        "DERIVED_FROM",
        "report:sterile_repository_readme_draft",
    ) in edges
    assert (article_id, "DERIVED_FROM", "report:main_article_draft") in edges
    assert (
        article_id,
        "DERIVED_FROM",
        "report:supplementary_document_draft",
    ) in edges
    assert (
        article_id,
        "DERIVED_FROM",
        "report:publication_claim_evidence_verification_matrix",
    ) in edges
    assert (kg_id, "DERIVED_FROM", "report:knowledge_graph_quality_summary") in edges
    assert (kg_id, "DERIVED_FROM", "report:graph_artifact_readiness_audit") in edges
    assert (site_id, "DERIVED_FROM", "report:neutral_reporting_language_audit") in edges


def test_private_latex_html_review_outputs_link_drafts_and_citations():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:private_latex_html_review_outputs_manifest"
    manifest_id = "manifest:private_latex_html_review_outputs"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "private_latex_html_review_outputs_manifest.json"
    )
    assert "Private LaTeX/HTML review output manifest" in nodes[report_id]["summary"]
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    for source_id in [
        "report:neutral_publication_release_cut_decision",
        "report:main_article_draft",
        "report:supplementary_document_draft",
        "report:publication_citation_registry",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
    assert (report_id, "SUMMARIZES_MANIFEST", manifest_id) in edges

    assert nodes[manifest_id]["type"] == "manifest"
    assert nodes[manifest_id]["output_count"] == 6
    assert nodes[manifest_id]["latex_output_count"] == 2
    assert nodes[manifest_id]["html_output_count"] == 3
    assert nodes[manifest_id]["bibtex_output_count"] == 1
    assert nodes[manifest_id]["secret_pattern_hit_count"] == 0
    assert nodes[manifest_id]["public_release_authorized"] is False
    assert nodes[manifest_id]["final_manuscript_prose_permission"] is False
    assert nodes[manifest_id]["method_recommendation_authorized"] is False
    assert nodes[manifest_id]["positive_claim_promotion_authorized"] is False
    for source_id in [
        "report:neutral_publication_release_cut_decision",
        "report:main_article_draft",
        "report:supplementary_document_draft",
        "report:publication_citation_registry",
    ]:
        assert (manifest_id, "SUPPORTED_BY", source_id) in edges


def test_private_sterile_publication_package_links_release_cut_and_manifest():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:private_sterile_publication_package_manifest"
    package_id = "manifest:private_sterile_publication_review_package"
    render_audit_id = "report:private_latex_html_review_output_audit"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "private_sterile_publication_package_manifest.json"
    )
    assert "Private sterile publication package manifest" in nodes[report_id]["summary"]
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:neutral_publication_release_cut_decision",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:sterile_repository_staging_manifest",
    ) in edges
    assert (
        report_id,
        "DERIVED_FROM",
        "report:private_latex_html_review_outputs_manifest",
    ) in edges
    assert (report_id, "DERIVED_FROM", render_audit_id) in edges
    assert (report_id, "SUMMARIZES_MANIFEST", package_id) in edges

    assert nodes[render_audit_id]["type"] == "report"
    assert nodes[render_audit_id]["json_path"].endswith(
        "private_latex_html_review_output_audit.json"
    )
    assert (
        render_audit_id,
        "DERIVED_FROM",
        "report:private_latex_html_review_outputs_manifest",
    ) in edges

    assert nodes[package_id]["type"] == "manifest"
    assert nodes[package_id]["local_git_initialized"] is True
    assert nodes[package_id]["local_git_commit_recorded"] is True
    assert nodes[package_id]["copied_file_count"] > 100
    assert nodes[package_id]["private_latex_html_output_audit_status"] == (
        "private_latex_html_review_output_audit_pass"
    )
    assert nodes[package_id]["path_risk_hit_count"] == 0
    assert nodes[package_id]["secret_pattern_hit_count"] == 0
    assert nodes[package_id]["public_release_authorized"] is False
    assert nodes[package_id]["working_repository_final_citable"] is False
    assert nodes[package_id]["method_recommendation_authorized"] is False
    assert nodes[package_id]["positive_claim_promotion_authorized"] is False
    assert nodes[package_id]["raw_data_or_secret_inclusion_authorized"] is False
    assert (
        package_id,
        "SUPPORTED_BY",
        "report:neutral_publication_release_cut_decision",
    ) in edges
    assert (
        package_id,
        "SUPPORTED_BY",
        "report:sterile_repository_staging_manifest",
    ) in edges
    assert (
        package_id,
        "SUPPORTED_BY",
        "report:private_latex_html_review_outputs_manifest",
    ) in edges
    assert (package_id, "SUPPORTED_BY", render_audit_id) in edges
    assert (package_id, "SUPPORTED_BY", "report:knowledge_graph_quality_summary") in edges


def test_main_article_draft_links_sections_and_sources():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:main_article_draft"
    results_section_id = "methodology_control:main_article_draft:results"
    methods_section_id = (
        "methodology_control:main_article_draft:background_and_methods"
    )
    traceability_section_id = (
        "methodology_control:main_article_draft:reproducibility_and_traceability"
    )
    conclusion_section_id = "methodology_control:main_article_draft:conclusion"
    evidence_ladder_section_id = (
        "methodology_control:main_article_draft:evidence_to_claim_ladder"
    )
    research_questions_section_id = (
        "methodology_control:main_article_draft:research_questions"
    )
    concept_bridge_section_id = (
        "methodology_control:main_article_draft:concept_bridge"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith("main_article_draft.json")
    assert "Evidence-linked main article draft" in nodes[report_id]["summary"]
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    for source_id in [
        "report:individual_experiment_report_draft",
        "report:article_supplement_blueprint_alignment",
        "report:manuscript_section_evidence_packet",
        "report:section_claim_boundary_audit",
        "report:publication_claim_evidence_verification_matrix",
        "report:publication_citation_registry",
        "report:publication_exemplar_review",
        "report:knowledge_graph_quality_summary",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith("main_article_draft.json")

    section_nodes = [
        node_id
        for node_id in nodes
        if node_id.startswith("methodology_control:main_article_draft:")
    ]
    assert len(section_nodes) == 14
    assert "methodology_control:main_article_draft:reader_orientation" in section_nodes
    assert research_questions_section_id in section_nodes
    assert concept_bridge_section_id in section_nodes
    assert "methodology_control:main_article_draft:study_design_summary" in section_nodes
    assert (
        "methodology_control:main_article_draft:notation_and_evaluation_protocol"
        in section_nodes
    )
    assert evidence_ladder_section_id in section_nodes
    assert conclusion_section_id in section_nodes

    assert nodes[methods_section_id]["evidence_source_count"] == 2
    assert nodes[methods_section_id]["method_recommendation_authorized"] is False
    assert (
        methods_section_id,
        "DERIVED_FROM",
        "report:publication_citation_registry",
    ) in edges

    assert nodes[results_section_id]["role"] == (
        "descriptive_method_behavior_and_negative_evidence"
    )
    assert nodes[results_section_id]["positive_claim_promotion_authorized"] is False
    assert (
        results_section_id,
        "DERIVED_FROM",
        "report:publication_claim_evidence_verification_matrix",
    ) in edges
    assert (
        results_section_id,
        "DERIVED_FROM",
        "report:individual_experiment_report_draft",
    ) in edges

    assert nodes[research_questions_section_id]["role"] == (
        "compact_article_questions_answers_and_closed_readings"
    )
    assert nodes[research_questions_section_id]["evidence_source_count"] == 3
    assert nodes[research_questions_section_id]["positive_claim_promotion_authorized"] is False
    for source_id in [
        "report:individual_experiment_report_draft",
        "report:publication_claim_evidence_verification_matrix",
        "report:knowledge_graph_quality_summary",
    ]:
        assert (research_questions_section_id, "DERIVED_FROM", source_id) in edges

    assert nodes[concept_bridge_section_id]["role"] == (
        "citation_backed_non_specialist_concept_bridge"
    )
    assert nodes[concept_bridge_section_id]["evidence_source_count"] == 3
    assert nodes[concept_bridge_section_id]["method_recommendation_authorized"] is False
    assert nodes[concept_bridge_section_id]["positive_claim_promotion_authorized"] is False
    for source_id in [
        "report:publication_citation_registry",
        "report:publication_claim_evidence_verification_matrix",
        "report:section_claim_boundary_audit",
    ]:
        assert (concept_bridge_section_id, "DERIVED_FROM", source_id) in edges

    assert nodes[evidence_ladder_section_id]["role"] == (
        "maps_empirical_objects_to_allowed_claims_and_blocked_upgrades"
    )
    assert nodes[evidence_ladder_section_id]["evidence_source_count"] == 3
    assert nodes[evidence_ladder_section_id]["positive_claim_promotion_authorized"] is False
    assert (
        evidence_ladder_section_id,
        "DERIVED_FROM",
        "report:individual_experiment_report_draft",
    ) in edges
    assert (
        evidence_ladder_section_id,
        "DERIVED_FROM",
        "report:publication_claim_evidence_verification_matrix",
    ) in edges
    assert (
        evidence_ladder_section_id,
        "DERIVED_FROM",
        "report:section_claim_boundary_audit",
    ) in edges

    assert nodes[traceability_section_id]["release_authorized"] is False
    assert (
        traceability_section_id,
        "DERIVED_FROM",
        "report:knowledge_graph_quality_summary",
    ) in edges

    assert nodes[conclusion_section_id]["role"] == (
        "descriptive_takeaway_and_closed_claim_recap"
    )
    assert nodes[conclusion_section_id]["evidence_source_count"] == 3
    assert nodes[conclusion_section_id]["method_recommendation_authorized"] is False
    assert nodes[conclusion_section_id]["release_authorized"] is False
    assert (
        conclusion_section_id,
        "DERIVED_FROM",
        "report:publication_claim_evidence_verification_matrix",
    ) in edges
    assert (
        conclusion_section_id,
        "DERIVED_FROM",
        "report:section_claim_boundary_audit",
    ) in edges


def test_supplementary_document_draft_links_sections_and_sources():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:supplementary_document_draft"
    robustness_section_id = (
        "methodology_control:supplementary_document_draft:"
        "method_selection_robustness"
    )
    bounded_section_id = (
        "methodology_control:supplementary_document_draft:"
        "bounded_support_endpoint_policy"
    )
    fairness_section_id = (
        "methodology_control:supplementary_document_draft:"
        "fairness_group_diagnostics"
    )
    traceability_section_id = (
        "methodology_control:supplementary_document_draft:"
        "traceability_and_release"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith("supplementary_document_draft.json")
    assert "Evidence-linked supplementary document draft" in nodes[report_id]["summary"]
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    for source_id in [
        "report:main_article_draft",
        "report:individual_experiment_report_draft",
        "report:article_supplement_blueprint_alignment",
        "report:method_selection_robustness_audit",
        "report:method_selection_inferential_audit",
        "report:method_selection_post_selection_validation_results",
        "report:dataset_final_gate_post_selection_validation_bridge_results",
        "report:bounded_support_endpoint_closure_audit",
        "report:bounded_support_positive_validation_protocol",
        "report:fairness_group_diagnostic_audit",
        "report:fairness_population_readiness_audit",
        "report:fairness_group_multiplicity_scope",
        "report:duplicate_sensitivity_closure_audit",
        "report:duplicate_content_quarantine_audit",
        "report:cross_run_integrity_audit",
        "report:publication_citation_registry",
        "report:knowledge_graph_quality_summary",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith("supplementary_document_draft.json")

    section_nodes = [
        node_id
        for node_id in nodes
        if node_id.startswith("methodology_control:supplementary_document_draft:")
    ]
    assert len(section_nodes) == 6

    assert nodes[robustness_section_id]["role"] == (
        "selection_robustness_diagnostic_no_final_winner"
    )
    assert nodes[robustness_section_id]["method_recommendation_authorized"] is False
    assert (
        robustness_section_id,
        "DERIVED_FROM",
        "report:method_selection_robustness_audit",
    ) in edges
    assert (
        robustness_section_id,
        "DERIVED_FROM",
        "report:method_selection_inferential_audit",
    ) in edges

    assert nodes[bounded_section_id]["positive_claim_promotion_authorized"] is False
    assert (
        bounded_section_id,
        "DERIVED_FROM",
        "report:bounded_support_endpoint_closure_audit",
    ) in edges

    assert nodes[fairness_section_id]["claim_boundary"] == (
        "Diagnostic group comparison only; no population fairness claim."
    )
    assert (
        fairness_section_id,
        "DERIVED_FROM",
        "report:fairness_population_readiness_audit",
    ) in edges

    assert nodes[traceability_section_id]["release_authorized"] is False
    assert (
        traceability_section_id,
        "DERIVED_FROM",
        "report:knowledge_graph_quality_summary",
    ) in edges


def test_sterile_repository_readme_draft_links_sections_and_sources():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:sterile_repository_readme_draft"
    status_section_id = "methodology_control:sterile_repository_readme_draft:status"
    claim_section_id = (
        "methodology_control:sterile_repository_readme_draft:claim_boundaries"
    )
    kg_section_id = (
        "methodology_control:sterile_repository_readme_draft:knowledge_graph"
    )
    private_package_section_id = (
        "methodology_control:sterile_repository_readme_draft:private_review_package"
    )
    reviewer_decision_section_id = (
        "methodology_control:sterile_repository_readme_draft:reviewer_decision_matrix"
    )
    method_reading_section_id = (
        "methodology_control:sterile_repository_readme_draft:method_reading_guide"
    )
    guarantee_boundary_section_id = (
        "methodology_control:sterile_repository_readme_draft:"
        "guarantee_boundary_snapshot"
    )
    contribution_finding_section_id = (
        "methodology_control:sterile_repository_readme_draft:"
        "contribution_finding_snapshot"
    )
    research_question_section_id = (
        "methodology_control:sterile_repository_readme_draft:"
        "research_question_answer_map"
    )
    evidence_notes_section_id = (
        "methodology_control:sterile_repository_readme_draft:"
        "evidence_snapshot_reading_notes"
    )
    claim_safe_section_id = (
        "methodology_control:sterile_repository_readme_draft:"
        "claim_safe_reading_map"
    )
    finalization_blocker_section_id = (
        "methodology_control:sterile_repository_readme_draft:"
        "finalization_blocker_snapshot"
    )
    first_ten_minute_section_id = (
        "methodology_control:sterile_repository_readme_draft:"
        "first_ten_minute_review_protocol"
    )
    provenance_graph_log_section_id = (
        "methodology_control:sterile_repository_readme_draft:"
        "provenance_graph_and_log_entry_points"
    )
    private_review_contract_section_id = (
        "methodology_control:sterile_repository_readme_draft:"
        "private_review_contract"
    )
    research_document_entry_point_section_id = (
        "methodology_control:sterile_repository_readme_draft:"
        "research_document_entry_point"
    )
    review_handoff_section_id = (
        "methodology_control:sterile_repository_readme_draft:review_handoff"
    )
    reader_mode_selector_section_id = (
        "methodology_control:sterile_repository_readme_draft:reader_mode_selector"
    )
    evidence_to_claim_ladder_section_id = (
        "methodology_control:sterile_repository_readme_draft:"
        "evidence_to_claim_ladder"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "sterile_repository_readme_draft.json"
    )
    assert "Evidence-linked draft README" in nodes[report_id]["summary"]
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    for source_id in [
        "report:sterile_repository_staging_manifest",
        "report:main_article_draft",
        "report:supplementary_document_draft",
        "report:individual_experiment_report_draft",
        "methodology_control:publication_claim_evidence_draft_artifact:research_document",
        "report:publication_citation_registry",
        "report:publication_claim_evidence_verification_matrix",
        "report:knowledge_graph_quality_summary",
        "report:final_publication_output_authorization_protocol",
        "report:private_sterile_publication_package_manifest",
        "report:private_latex_html_review_output_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith("sterile_repository_readme_draft.json")

    section_nodes = [
        node_id
        for node_id in nodes
        if node_id.startswith("methodology_control:sterile_repository_readme_draft:")
    ]
    assert len(section_nodes) == 25
    assert (
        "methodology_control:sterile_repository_readme_draft:publication_design_basis"
        in nodes
    )
    assert "methodology_control:sterile_repository_readme_draft:review_path" in nodes
    assert method_reading_section_id in nodes
    assert research_question_section_id in nodes
    assert contribution_finding_section_id in nodes
    assert guarantee_boundary_section_id in nodes
    assert evidence_notes_section_id in nodes
    assert reviewer_decision_section_id in nodes
    assert claim_safe_section_id in nodes
    assert finalization_blocker_section_id in nodes
    assert first_ten_minute_section_id in nodes
    assert provenance_graph_log_section_id in nodes
    assert private_review_contract_section_id in nodes
    assert research_document_entry_point_section_id in nodes
    assert review_handoff_section_id in nodes
    assert reader_mode_selector_section_id in nodes
    assert evidence_to_claim_ladder_section_id in nodes

    assert nodes[status_section_id]["release_authorized"] is False
    assert (
        status_section_id,
        "DERIVED_FROM",
        "report:final_publication_output_authorization_protocol",
    ) in edges

    assert nodes[method_reading_section_id]["evidence_source_count"] == 2
    assert (
        method_reading_section_id,
        "DERIVED_FROM",
        "report:main_article_draft",
    ) in edges
    assert (
        method_reading_section_id,
        "DERIVED_FROM",
        "report:publication_citation_registry",
    ) in edges

    assert nodes[first_ten_minute_section_id]["evidence_source_count"] == 6
    for source_id in [
        "methodology_control:publication_claim_evidence_draft_artifact:research_document",
        "report:main_article_draft",
        "report:supplementary_document_draft",
        "report:knowledge_graph_quality_summary",
        "report:private_publication_repository_remote_audit",
        "report:final_publication_output_authorization_protocol",
    ]:
        assert (first_ten_minute_section_id, "DERIVED_FROM", source_id) in edges

    assert nodes[private_review_contract_section_id]["evidence_source_count"] == 5
    for source_id in [
        "methodology_control:publication_claim_evidence_draft_artifact:research_document",
        "report:private_sterile_publication_package_manifest",
        "report:private_publication_repository_remote_audit",
        "report:knowledge_graph_quality_summary",
        "report:final_publication_output_authorization_protocol",
    ]:
        assert (private_review_contract_section_id, "DERIVED_FROM", source_id) in edges

    assert nodes[reader_mode_selector_section_id]["evidence_source_count"] == 5
    for source_id in [
        "methodology_control:publication_claim_evidence_draft_artifact:research_document",
        "report:private_sterile_publication_package_manifest",
        "report:knowledge_graph_quality_summary",
        "report:final_publication_output_authorization_protocol",
        "report:private_publication_repository_remote_audit",
    ]:
        assert (reader_mode_selector_section_id, "DERIVED_FROM", source_id) in edges

    assert nodes[evidence_to_claim_ladder_section_id]["evidence_source_count"] == 3
    for source_id in [
        "methodology_control:publication_claim_evidence_draft_artifact:research_document",
        "report:publication_claim_evidence_verification_matrix",
        "report:final_publication_output_authorization_protocol",
    ]:
        assert (
            evidence_to_claim_ladder_section_id,
            "DERIVED_FROM",
            source_id,
        ) in edges

    assert nodes[research_document_entry_point_section_id]["evidence_source_count"] == 3
    for source_id in [
        "methodology_control:publication_claim_evidence_draft_artifact:research_document",
        "report:publication_authoring_decision_record",
        "report:private_sterile_publication_package_manifest",
    ]:
        assert (
            research_document_entry_point_section_id,
            "DERIVED_FROM",
            source_id,
        ) in edges

    assert nodes[review_handoff_section_id]["evidence_source_count"] == 3
    for source_id in [
        "report:private_sterile_publication_package_manifest",
        "report:private_publication_repository_remote_audit",
        "report:final_publication_output_authorization_protocol",
    ]:
        assert (review_handoff_section_id, "DERIVED_FROM", source_id) in edges

    assert nodes[research_question_section_id]["evidence_source_count"] == 5
    for source_id in [
        "methodology_control:publication_claim_evidence_draft_artifact:research_document",
        "report:main_article_draft",
        "report:supplementary_document_draft",
        "report:publication_claim_evidence_verification_matrix",
        "report:knowledge_graph_quality_summary",
    ]:
        assert (research_question_section_id, "DERIVED_FROM", source_id) in edges

    assert nodes[contribution_finding_section_id]["evidence_source_count"] == 6
    for source_id in [
        "methodology_control:publication_claim_evidence_draft_artifact:research_document",
        "report:main_article_draft",
        "report:supplementary_document_draft",
        "report:publication_claim_evidence_verification_matrix",
        "report:knowledge_graph_quality_summary",
        "report:private_sterile_publication_package_manifest",
    ]:
        assert (contribution_finding_section_id, "DERIVED_FROM", source_id) in edges

    assert nodes[guarantee_boundary_section_id]["evidence_source_count"] == 3
    assert (
        guarantee_boundary_section_id,
        "DERIVED_FROM",
        "report:main_article_draft",
    ) in edges
    assert (
        guarantee_boundary_section_id,
        "DERIVED_FROM",
        "methodology_control:publication_claim_evidence_draft_artifact:research_document",
    ) in edges
    assert (
        guarantee_boundary_section_id,
        "DERIVED_FROM",
        "report:publication_claim_evidence_verification_matrix",
    ) in edges

    assert nodes[evidence_notes_section_id]["evidence_source_count"] == 2
    assert (
        evidence_notes_section_id,
        "DERIVED_FROM",
        "report:main_article_draft",
    ) in edges
    assert (
        evidence_notes_section_id,
        "DERIVED_FROM",
        "report:publication_claim_evidence_verification_matrix",
    ) in edges

    assert nodes[claim_safe_section_id]["evidence_source_count"] == 2
    assert (
        claim_safe_section_id,
        "DERIVED_FROM",
        "methodology_control:publication_claim_evidence_draft_artifact:research_document",
    ) in edges
    assert (
        claim_safe_section_id,
        "DERIVED_FROM",
        "report:publication_claim_evidence_verification_matrix",
    ) in edges

    assert nodes[provenance_graph_log_section_id]["evidence_source_count"] == 5
    assert nodes[provenance_graph_log_section_id]["evidence_sources"] == [
        "data_scientist_log",
        "data_flow_graph",
        "control_flow_graph",
        "dependency_graph",
        "system_ontology_graph",
    ]
    assert (
        "log:data_scientist_diary",
        "NOTES",
        "catalog:dataset_candidates",
    ) in edges
    for source_id in [
        "graph:data_flow",
        "graph:control_flow",
        "graph:dependency_graph",
        "graph:system_ontology",
    ]:
        assert (source_id, "DOCUMENTS_GRAPH", "catalog:knowledge_graph") in edges

    assert nodes[claim_section_id]["method_recommendation_authorized"] is False
    assert (
        claim_section_id,
        "DERIVED_FROM",
        "report:sterile_repository_staging_manifest",
    ) in edges

    assert nodes[kg_section_id]["evidence_source_count"] == 2
    assert (
        kg_section_id,
        "DERIVED_FROM",
        "report:knowledge_graph_quality_summary",
    ) in edges
    assert (
        kg_section_id,
        "DERIVED_FROM",
        "report:private_sterile_publication_package_manifest",
    ) in edges

    assert nodes[reviewer_decision_section_id]["evidence_source_count"] == 4
    assert (
        reviewer_decision_section_id,
        "DERIVED_FROM",
        "report:publication_authoring_decision_record",
    ) in edges
    assert (
        reviewer_decision_section_id,
        "DERIVED_FROM",
        "report:publication_claim_evidence_verification_matrix",
    ) in edges
    assert (
        reviewer_decision_section_id,
        "DERIVED_FROM",
        "report:private_publication_repository_remote_audit",
    ) in edges

    assert nodes[finalization_blocker_section_id]["evidence_source_count"] == 3
    assert nodes[finalization_blocker_section_id]["release_authorized"] is False
    assert (
        finalization_blocker_section_id,
        "DERIVED_FROM",
        "report:final_publication_output_authorization_protocol",
    ) in edges
    assert (
        finalization_blocker_section_id,
        "DERIVED_FROM",
        "report:publication_authoring_decision_record",
    ) in edges
    assert (
        finalization_blocker_section_id,
        "DERIVED_FROM",
        "report:publication_claim_evidence_verification_matrix",
    ) in edges

    assert nodes[private_package_section_id]["evidence_source_count"] == 2
    assert (
        private_package_section_id,
        "DERIVED_FROM",
        "report:private_sterile_publication_package_manifest",
    ) in edges
    assert (
        private_package_section_id,
        "DERIVED_FROM",
        "report:private_latex_html_review_output_audit",
    ) in edges


def test_reader_primer_section_alignment_links_sections_to_concepts():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:reader_primer_section_alignment"
    method_scope_id = (
        "methodology_control:reader_primer_section_alignment:"
        "individual_experiment_report_model_and_conformal_method_scope"
    )
    venn_id = (
        "methodology_control:reader_primer_section_alignment:"
        "article_supplement_blueprint_alignment_venn_abers_failure_mode_evidence"
    )
    cqr_concept_id = (
        "methodology_control:reader_method_primer:"
        "conformalized_quantile_regression_cqr"
    )
    cv_concept_id = (
        "methodology_control:reader_method_primer:jackknife_plus_and_cv_plus"
    )
    venn_concept_id = (
        "methodology_control:reader_method_primer:"
        "venn_abers_predictive_distributions"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "reader_primer_section_alignment.json"
    )
    assert "concept primer checklist" in nodes[report_id]["summary"]
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    for source_id in [
        "report:reader_method_primer_citation_map",
        "report:article_supplement_blueprint_alignment",
        "report:individual_experiment_report_blueprint",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges

    control_nodes = [
        node_id
        for node_id in nodes
        if node_id.startswith(
            "methodology_control:reader_primer_section_alignment:"
        )
    ]
    assert len(control_nodes) == 20

    assert nodes[method_scope_id]["concept_alignment_status"] == "pass"
    assert nodes[method_scope_id]["required_concept_count"] == 10
    assert nodes[method_scope_id]["method_champion_authorized"] is False
    assert (report_id, "SUMMARIZES_CONTROL", method_scope_id) in edges
    assert (method_scope_id, "DERIVED_FROM", cqr_concept_id) in edges
    assert (method_scope_id, "DERIVED_FROM", cv_concept_id) in edges
    assert (method_scope_id, "DERIVED_FROM", venn_concept_id) in edges

    assert nodes[venn_id]["concept_alignment_status"] == "pass"
    assert nodes[venn_id]["required_concept_ids"] == [
        "venn_abers_predictive_distributions",
        "result_metrics_and_claim_boundaries",
    ]
    assert nodes[venn_id]["positive_claim_promotion_authorized"] is False
    assert (venn_id, "DERIVED_FROM", venn_concept_id) in edges


def test_sterile_repository_staging_manifest_links_content_and_exclusion_controls():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:sterile_repository_staging_manifest"
    content_id = (
        "methodology_control:sterile_repository_required_content:"
        "knowledge_graph_export"
    )
    readme_content_id = (
        "methodology_control:sterile_repository_required_content:polished_readme"
    )
    main_content_id = (
        "methodology_control:sterile_repository_required_content:"
        "main_article_outputs"
    )
    supplement_content_id = (
        "methodology_control:sterile_repository_required_content:"
        "supplementary_document_outputs"
    )
    individual_content_id = (
        "methodology_control:sterile_repository_required_content:"
        "individual_experiment_report"
    )
    citation_content_id = (
        "methodology_control:sterile_repository_required_content:"
        "citation_metadata_and_release_notes"
    )
    exclusion_id = (
        "methodology_control:sterile_repository_exclusion_policy:"
        "secrets_credentials_and_local_env"
    )
    blocker_id = (
        "methodology_control:sterile_repository_blocking_gate:"
        "kg_citable_component_not_authorized"
    )
    final_auth_id = (
        "methodology_control:final_publication_output_authorization:"
        "kg_citable_component_not_authorized"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "sterile_repository_staging_manifest.json"
    )
    assert "Sterile final-repository staging manifest" in nodes[report_id]["summary"]
    assert nodes[content_id]["type"] == "methodology_control"
    assert nodes[content_id]["package_family"] == "knowledge_graph"
    assert nodes[content_id]["staging_status"] == (
        "kg_snapshot_available_citation_blocked"
    )
    assert nodes[content_id]["candidate_exclusion_risk_hit_count"] == 0
    assert nodes[content_id]["final_content_authorized"] is False
    assert nodes[content_id]["release_authorized"] is False
    assert nodes[exclusion_id]["type"] == "methodology_control"
    assert nodes[exclusion_id]["pattern_count"] == 6
    assert nodes[exclusion_id]["source_traceability_status"] == "pass"

    for source_id in [
        "catalog:post_experiment_publication_program",
        "report:publication_release_gap_register",
        "report:final_publication_output_authorization_protocol",
        "report:goal_completion_audit",
        "report:neutral_reporting_language_audit",
        "report:knowledge_graph_quality_summary",
        "report:kg_publication_quality_audit",
        "report:graph_artifact_readiness_audit",
        "report:section_claim_boundary_audit",
        "report:article_supplement_kg_navigation_index",
        "report:final_publication_visual_auditor_readiness",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith(
            "sterile_repository_staging_manifest.json"
        )

    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert (report_id, "SUMMARIZES_CONTROL", content_id) in edges
    assert (report_id, "SUMMARIZES_CONTROL", exclusion_id) in edges
    assert (content_id, "DERIVED_FROM", blocker_id) in edges
    assert (blocker_id, "DERIVED_FROM", final_auth_id) in edges
    assert (
        content_id,
        "DERIVED_FROM",
        "report:knowledge_graph_quality_summary",
    ) in edges
    assert (
        readme_content_id,
        "DERIVED_FROM",
        "report:sterile_repository_readme_draft",
    ) in edges
    assert (main_content_id, "DERIVED_FROM", "report:main_article_draft") in edges
    assert (
        supplement_content_id,
        "DERIVED_FROM",
        "report:supplementary_document_draft",
    ) in edges
    assert (
        individual_content_id,
        "DERIVED_FROM",
        "report:individual_experiment_report_draft",
    ) in edges
    assert (
        citation_content_id,
        "DERIVED_FROM",
        "report:publication_citation_registry",
    ) in edges
    assert (
        exclusion_id,
        "DERIVED_FROM",
        "report:final_publication_output_authorization_protocol",
    ) in edges


def test_article_supplement_blueprint_alignment_links_neutral_controls():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:article_supplement_blueprint_alignment"
    control_id = (
        "methodology_control:article_supplement_blueprint_alignment:"
        "venn_abers_failure_mode_evidence"
    )
    retention_control_id = (
        "methodology_control:publication_retention_recommendation:"
        "venn_abers_failure_mode_evidence"
    )
    ledger_control_id = (
        "methodology_control:neutral_result_ledger:"
        "venn_abers_regression_negative_evidence"
    )
    surface_id = (
        "methodology_control:article_supplement_blueprint_surface:"
        "main_article"
    )
    methodology_report_id = "report:methodology_sanity_audit_20260627"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "article_supplement_blueprint_alignment.json"
    )
    assert "without final prose" in nodes[report_id]["summary"]
    assert nodes[control_id]["type"] == "methodology_control"
    assert nodes[control_id]["scientific_reporting_role"] == (
        "negative_failure_mode_no_validated_regression_claim"
    )
    assert nodes[control_id]["reviewer_alignment_status"] == (
        "direct_reviewer_advice_linked"
    )
    assert nodes[control_id]["linked_neutral_result_count"] == 1
    assert nodes[control_id]["final_manuscript_prose_permission"] is False
    assert nodes[control_id]["method_recommendation_authorized"] is False
    assert nodes[control_id]["positive_claim_promotion_authorized"] is False
    assert nodes[surface_id]["type"] == "methodology_control"
    assert nodes[surface_id]["final_manuscript_prose_permission"] is False
    assert nodes[surface_id]["positive_claim_promotion_authorized"] is False

    for source_id in [
        "report:reviewer_design_reconciliation",
        "report:publication_retention_readiness_audit",
        "report:article_supplement_retention_recommendation_matrix",
        "report:neutral_result_ledger",
        "report:post_experiment_publication_activation_audit",
        "report:manuscript_readiness_map",
        "report:paper_gate_closure_map",
        "report:neutral_reporting_language_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith(
            "article_supplement_blueprint_alignment.json"
        )

    assert (report_id, "SUPPORTS_REPORT", methodology_report_id) in edges
    assert (report_id, "SUMMARIZES_CONTROL", control_id) in edges
    assert (report_id, "SUMMARIZES_CONTROL", surface_id) in edges
    assert (control_id, "DERIVED_FROM", retention_control_id) in edges
    assert (control_id, "DERIVED_FROM", ledger_control_id) in edges


def test_publication_release_gap_register_links_blocked_deliverables():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:publication_release_gap_register"
    control_id = (
        "methodology_control:publication_release_gap:"
        "sterile_publication_repository"
    )
    deliverable_id = "publication_deliverable:sterile_publication_repository"
    blocker_id = (
        "methodology_control:publication_release_blocker:"
        "working_repository_not_final_citable"
    )
    methodology_report_id = "report:methodology_sanity_audit_20260627"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "publication_release_gap_register.json"
    )
    assert "without final prose" in nodes[report_id]["summary"]
    assert nodes[control_id]["type"] == "methodology_control"
    assert nodes[control_id]["family"] == "sterile_publication_repository"
    assert nodes[control_id]["release_status"] == (
        "release_blocked_pre_prose_candidate_ready"
    )
    assert nodes[control_id]["release_authorized"] is False
    assert nodes[control_id]["sterile_repository_creation_authorized"] is False
    assert nodes[control_id]["method_recommendation_authorized"] is False
    assert nodes[control_id]["positive_claim_promotion_authorized"] is False
    assert nodes[control_id]["working_repository_final_citable"] is False
    assert nodes[blocker_id]["type"] == "methodology_control"

    for source_id in [
        "catalog:post_experiment_publication_program",
        "report:goal_completion_audit",
        "report:post_experiment_publication_activation_audit",
        "report:manuscript_readiness_map",
        "report:paper_gate_closure_map",
        "report:article_supplement_blueprint_alignment",
        "report:publication_retention_readiness_audit",
        "report:publication_visual_table_audit_report",
        "report:kg_publication_quality_audit",
        "report:neutral_reporting_language_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(report_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith(
            "publication_release_gap_register.json"
        )

    assert (report_id, "SUPPORTS_REPORT", methodology_report_id) in edges
    assert (report_id, "SUMMARIZES_CONTROL", control_id) in edges
    assert (report_id, "SUMMARIZES_CONTROL", deliverable_id) in edges
    assert (control_id, "DERIVED_FROM", blocker_id) in edges


def test_neutral_result_ledger_links_claim_bounded_result_controls():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:neutral_result_ledger"
    cqr_control_id = (
        "methodology_control:neutral_result_ledger:"
        "method_performance_descriptive_frontier"
    )
    va_control_id = (
        "methodology_control:neutral_result_ledger:"
        "venn_abers_regression_negative_evidence"
    )

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith("neutral_result_ledger.json")
    assert "without final method selection" in nodes[report_id]["summary"]
    assert (
        report_id,
        "SUPPORTS_REPORT",
        "report:methodology_sanity_audit_20260627",
    ) in edges
    assert nodes[cqr_control_id]["type"] == "methodology_control"
    assert nodes[cqr_control_id]["result_family"] == "method_performance"
    assert nodes[cqr_control_id]["claim_status"] == "descriptive_no_final_selection"
    assert nodes[cqr_control_id]["positive_claim_promotion_authorized"] is False
    assert nodes[cqr_control_id]["final_method_selection_authorized"] is False
    assert nodes[va_control_id]["type"] == "methodology_control"
    assert nodes[va_control_id]["result_family"] == "venn_abers"
    assert (
        nodes[va_control_id]["claim_status"]
        == "accepted_negative_result_for_current_manuscript"
    )
    assert nodes[va_control_id]["positive_claim_promotion_authorized"] is False
    for control_id, source_id in [
        (cqr_control_id, "report:method_performance_synthesis"),
        (va_control_id, "report:venn_abers_claim_gate_matrix"),
        (va_control_id, "report:venn_abers_negative_evidence_disposition_audit"),
    ]:
        assert (report_id, "SUMMARIZES_CONTROL", control_id) in edges
        assert (control_id, "DERIVED_FROM", source_id) in edges
        edge = edge_by_triple[(control_id, "DERIVED_FROM", source_id)]
        assert edge["evidence_path"].endswith("neutral_result_ledger.json")


def test_manifest_schema_requires_selection_multiplicity_evidence():
    schema = json.loads(
        (
            ROOT
            / "experiments/regression/catalogs/manuscript_evidence_manifest_schema.json"
        ).read_text()
    )

    assert "selection_multiplicity_evidence" in schema["required_sections"]
    selection_fields = set(schema["selection_multiplicity_evidence_fields"])
    assert {
        "predeclared_operating_criterion",
        "ranking_scope",
        "multiplicity_scope",
        "tie_break_rule",
        "post_selection_claim_boundary",
        "exploratory_ranking_label",
    } <= selection_fields
    assert "predeclared_selection_rule_present" in schema["promotion_gates"]
    assert "multiplicity_scope_declared" in schema["promotion_gates"]
    assert "exploratory_rankings_not_promoted" in schema["promotion_gates"]


def test_method_performance_synthesis_links_publication_scope_and_methods():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:method_performance_synthesis"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/method_performance_synthesis.json"
    )
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (report_id, "DERIVED_FROM", "report:cross_run_integrity_audit") in edges
    assert (gate_id, "DERIVED_FROM", report_id) in edges

    for method_id in [
        "cqr",
        "cv_plus",
        "mondrian_abs",
        "venn_abers_quantile",
        "venn_abers_split_fallback",
    ]:
        node_id = f"method:{method_id}"
        assert nodes[node_id]["type"] == "method"
        assert (report_id, "EVALUATES_METHOD", node_id) in edges
        edge = edge_by_triple[(report_id, "EVALUATES_METHOD", node_id)]
        assert edge["evidence_path"].endswith("method_performance_synthesis.json")
        assert "method_rows" in edge["evidence"]


def test_method_selection_candidate_audit_links_shortlist_sources_and_methods():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:method_selection_candidate_audit"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/method_selection_candidate_audit.json"
    )
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (gate_id, "DERIVED_FROM", report_id) in edges
    for source_id in [
        "report:method_performance_synthesis",
        "report:selection_multiplicity_protocol",
        "report:final_selection_claim_boundary_audit",
        "report:venn_abers_validation_readiness_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges

    for method_id in ["cqr", "cv_plus", "mondrian_abs"]:
        node_id = f"method:{method_id}"
        assert nodes[node_id]["type"] == "method"
        assert (report_id, "EVALUATES_METHOD", node_id) in edges
        edge = edge_by_triple[(report_id, "EVALUATES_METHOD", node_id)]
        assert edge["evidence_path"].endswith("method_selection_candidate_audit.json")
        assert "shortlist_methods" in edge["evidence"]

    venn_edge = edge_by_triple[
        (report_id, "EVALUATES_METHOD", "method:venn_abers_quantile")
    ]
    assert venn_edge["evidence_path"].endswith("method_selection_candidate_audit.json")
    assert "excluded_methods" in venn_edge["evidence"]


def test_method_selection_robustness_audit_links_sources_and_methods():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:method_selection_robustness_audit"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/method_selection_robustness_audit.json"
    )
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (gate_id, "DERIVED_FROM", report_id) in edges
    for source_id in [
        "report:method_performance_synthesis",
        "report:method_selection_candidate_audit",
        "report:selection_multiplicity_protocol",
        "report:final_selection_claim_boundary_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges

    for method_id in ["cqr", "cv_plus", "mondrian_abs"]:
        node_id = f"method:{method_id}"
        assert nodes[node_id]["type"] == "method"
        assert (report_id, "EVALUATES_METHOD", node_id) in edges
        edge = edge_by_triple[(report_id, "EVALUATES_METHOD", node_id)]
        assert edge["evidence_path"].endswith("method_selection_robustness_audit.json")
        assert "candidate_methods" in edge["evidence"]


def test_method_selection_alpha_expansion_plan_links_sources_tasks_and_methods():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:method_selection_alpha_expansion_plan"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "methodology_sanity_audit_20260627/method_selection_alpha_expansion_plan.json"
    )
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (gate_id, "DERIVED_FROM", report_id) in edges
    for source_id in [
        "report:method_performance_synthesis",
        "report:method_selection_candidate_audit",
        "report:method_selection_robustness_audit",
        "report:cross_run_integrity_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges

    for method_id in ["cqr", "cv_plus", "mondrian_abs"]:
        node_id = f"method:{method_id}"
        assert nodes[node_id]["type"] == "method"
        assert (report_id, "EVALUATES_METHOD", node_id) in edges
        edge = edge_by_triple[(report_id, "EVALUATES_METHOD", node_id)]
        assert edge["evidence_path"].endswith(
            "method_selection_alpha_expansion_plan.json"
        )
        assert "candidate_methods" in edge["evidence"]

    assert any(
        edge["source"] == report_id and edge["relation"] == "SUMMARIZES_DATASET"
        for edge in graph["edges"]
    )
    assert any(
        edge["source"] == report_id and edge["relation"] == "SUMMARIZES_CONFIG"
        for edge in graph["edges"]
    )


def test_individual_experiment_report_blueprint_links_sources_sections_and_deliverable():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:individual_experiment_report_blueprint"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "experiments/regression/manuscript/individual_experiment_report_blueprint.json"
    )
    assert "without final prose" in nodes[report_id]["summary"]
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (gate_id, "DERIVED_FROM", report_id) in edges
    assert (
        report_id,
        "SUMMARIZES_CONTROL",
        "publication_deliverable:individual_experiment_report",
    ) in edges
    for source_id in [
        "catalog:post_experiment_publication_program",
        "report:publication_release_gap_register",
        "report:goal_completion_audit",
        "report:post_experiment_publication_activation_audit",
        "report:manuscript_readiness_map",
        "report:article_supplement_blueprint_alignment",
        "report:neutral_result_ledger",
        "report:experiment_accounting_audit",
        "report:method_performance_synthesis",
        "report:knowledge_graph_quality_summary",
        "report:kg_publication_quality_audit",
        "report:neutral_reporting_language_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges

    section_id = (
        "methodology_control:individual_experiment_report_blueprint:"
        "venn_abers_negative_evidence"
    )
    assert nodes[section_id]["type"] == "methodology_control"
    assert (
        nodes[section_id]["section_role"]
        == "negative_failure_mode_no_validated_regression_claim"
    )
    assert nodes[section_id]["positive_claim_promotion_authorized"] is False
    assert nodes[section_id]["method_recommendation_authorized"] is False
    assert (report_id, "SUMMARIZES_CONTROL", section_id) in edges
    edge = edge_by_triple[(report_id, "SUMMARIZES_CONTROL", section_id)]
    assert edge["evidence_path"].endswith("individual_experiment_report_blueprint.json")
    assert edge["evidence"] == "section_rows[6].section_id"
    assert (
        section_id,
        "DERIVED_FROM",
        "methodology_control:neutral_result_ledger:"
        "venn_abers_regression_negative_evidence",
    ) in edges


def test_claim_safe_result_extraction_matrix_links_surfaces_and_claim_boundaries():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:claim_safe_result_extraction_matrix"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "experiments/regression/manuscript/claim_safe_result_extraction_matrix.json"
    )
    assert "pre-prose result extraction matrix" in nodes[report_id]["summary"]
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (gate_id, "DERIVED_FROM", report_id) in edges
    for source_id in [
        "report:manuscript_readiness_map",
        "report:paper_gate_closure_map",
        "report:neutral_result_ledger",
        "report:article_supplement_blueprint_alignment",
        "report:individual_experiment_report_blueprint",
        "report:publication_release_gap_register",
        "report:publication_retention_readiness_audit",
        "report:publication_visual_table_render_candidate_audit",
        "report:kg_publication_quality_audit",
        "report:neutral_reporting_language_audit",
        "report:experiment_accounting_audit",
        "report:method_performance_synthesis",
        "report:venn_abers_negative_evidence_disposition_audit",
        "report:final_selection_claim_boundary_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges

    surface_prefix = "methodology_control:claim_safe_result_extraction:"
    surface_nodes = [
        node_id for node_id in nodes if node_id.startswith(surface_prefix)
    ]
    assert len(surface_nodes) == 8

    main_id = surface_prefix + "main_results_table"
    assert nodes[main_id]["type"] == "methodology_control"
    assert nodes[main_id]["pre_prose_extraction_status"] == (
        "blocked_positive_claim_surface"
    )
    assert nodes[main_id]["positive_claim_surface_blocked"] is True
    assert nodes[main_id]["safe_pre_prose_extraction_candidate"] is False
    assert nodes[main_id]["positive_claim_promotion_authorized"] is False
    assert nodes[main_id]["method_recommendation_authorized"] is False
    assert (report_id, "SUMMARIZES_CONTROL", main_id) in edges

    negative_id = surface_prefix + "negative_results_table"
    assert nodes[negative_id]["pre_prose_extraction_status"] == (
        "candidate_negative_result_surface"
    )
    assert nodes[negative_id]["claim_scope"] == (
        "venn_abers_negative_failure_mode_no_validated_claim"
    )
    assert nodes[negative_id]["safe_pre_prose_extraction_candidate"] is True
    assert nodes[negative_id]["positive_claim_promotion_authorized"] is False
    assert nodes[negative_id]["method_recommendation_authorized"] is False
    assert (report_id, "SUMMARIZES_CONTROL", negative_id) in edges
    edge = edge_by_triple[(report_id, "SUMMARIZES_CONTROL", negative_id)]
    assert edge["evidence_path"].endswith("claim_safe_result_extraction_matrix.json")
    assert edge["evidence"] == "surface_rows[4].surface_id"
    assert (
        negative_id,
        "DERIVED_FROM",
        "methodology_control:neutral_result_ledger:"
        "venn_abers_regression_negative_evidence",
    ) in edges


def test_manuscript_section_evidence_packet_links_packets_to_claim_safe_surfaces():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:manuscript_section_evidence_packet"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "experiments/regression/manuscript/manuscript_section_evidence_packet.json"
    )
    assert "section evidence packet" in nodes[report_id]["summary"]
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (gate_id, "DERIVED_FROM", report_id) in edges
    for source_id in [
        "report:claim_safe_result_extraction_matrix",
        "report:neutral_result_ledger",
        "report:article_supplement_blueprint_alignment",
        "report:individual_experiment_report_blueprint",
        "report:publication_release_gap_register",
        "report:publication_retention_readiness_audit",
        "report:publication_visual_table_render_candidate_audit",
        "report:reader_method_primer_citation_map",
        "report:reader_primer_section_alignment",
        "report:neutral_reporting_language_audit",
        "report:kg_publication_quality_audit",
        "report:experiment_accounting_audit",
        "report:method_performance_synthesis",
        "report:venn_abers_negative_evidence_disposition_audit",
        "report:goal_completion_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges

    packet_prefix = "methodology_control:manuscript_section_evidence_packet:"
    packet_nodes = [node_id for node_id in nodes if node_id.startswith(packet_prefix)]
    assert len(packet_nodes) == 8

    main_id = packet_prefix + "paper_main_results_blocked_evidence"
    assert nodes[main_id]["type"] == "methodology_control"
    assert nodes[main_id]["packet_status"] == "blocked_positive_claim_packet"
    assert nodes[main_id]["positive_claim_packet_blocked"] is True
    assert nodes[main_id]["safe_pre_prose_evidence_packet"] is False
    assert nodes[main_id]["paragraph_blueprint_step_count"] == 3
    assert "result_metrics_and_claim_boundaries" in nodes[main_id][
        "reader_concept_ids"
    ]
    assert nodes[main_id]["final_section_prose_authorized"] is False
    assert nodes[main_id]["method_recommendation_authorized"] is False
    assert nodes[main_id]["positive_claim_promotion_authorized"] is False
    assert (report_id, "SUMMARIZES_CONTROL", main_id) in edges
    assert (
        main_id,
        "DERIVED_FROM",
        "methodology_control:claim_safe_result_extraction:main_results_table",
    ) in edges

    negative_id = packet_prefix + "supplement_venn_abers_negative_evidence"
    assert nodes[negative_id]["packet_status"] == "pre_prose_negative_evidence_ready"
    assert nodes[negative_id]["claim_safe_surface_id"] == "negative_results_table"
    assert nodes[negative_id]["claim_safe_surface_status"] == (
        "candidate_negative_result_surface"
    )
    assert nodes[negative_id]["safe_pre_prose_evidence_packet"] is True
    assert nodes[negative_id]["positive_claim_packet_blocked"] is False
    assert nodes[negative_id]["paragraph_blueprint_step_count"] == 3
    assert "venn_abers_predictive_distributions" in nodes[negative_id][
        "reader_concept_ids"
    ]
    assert nodes[negative_id]["final_section_prose_authorized"] is False
    assert nodes[negative_id]["method_recommendation_authorized"] is False
    assert nodes[negative_id]["positive_claim_promotion_authorized"] is False
    edge = edge_by_triple[(report_id, "SUMMARIZES_CONTROL", negative_id)]
    assert edge["evidence_path"].endswith("manuscript_section_evidence_packet.json")
    assert edge["evidence"] == "section_packet_rows[4].packet_id"
    assert (
        negative_id,
        "DERIVED_FROM",
        "methodology_control:claim_safe_result_extraction:negative_results_table",
    ) in edges
    assert (
        negative_id,
        "DERIVED_FROM",
        "methodology_control:neutral_result_ledger:"
        "venn_abers_regression_negative_evidence",
    ) in edges
    assert (
        negative_id,
        "DERIVED_FROM",
        "methodology_control:reader_method_primer:"
        "venn_abers_predictive_distributions",
    ) in edges


def test_section_claim_boundary_audit_links_boundaries_to_release_targets():
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text()
    )
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_by_triple = {
        (edge["source"], edge["relation"], edge["target"]): edge
        for edge in graph["edges"]
    }
    edges = set(edge_by_triple)

    report_id = "report:section_claim_boundary_audit"
    methodology_id = "report:methodology_sanity_audit_20260627"
    gate_id = "report:retrospective_quality_gate"

    assert nodes[report_id]["type"] == "report"
    assert nodes[report_id]["json_path"].endswith(
        "experiments/regression/manuscript/section_claim_boundary_audit.json"
    )
    assert "claim-boundary audit" in nodes[report_id]["summary"]
    assert (report_id, "SUPPORTS_REPORT", methodology_id) in edges
    assert (gate_id, "DERIVED_FROM", report_id) in edges
    for source_id in [
        "report:manuscript_section_evidence_packet",
        "report:claim_safe_result_extraction_matrix",
        "report:neutral_result_ledger",
        "report:publication_release_gap_register",
        "catalog:post_experiment_publication_program",
        "report:neutral_reporting_language_audit",
        "report:venn_abers_negative_evidence_disposition_audit",
    ]:
        assert (report_id, "DERIVED_FROM", source_id) in edges

    boundary_prefix = "methodology_control:section_claim_boundary_audit:"
    boundary_nodes = [
        node_id for node_id in nodes if node_id.startswith(boundary_prefix)
    ]
    assert len(boundary_nodes) == 8

    main_id = boundary_prefix + "paper_main_results_blocked_evidence"
    assert nodes[main_id]["type"] == "methodology_control"
    assert nodes[main_id]["boundary_status"] == "blocked_positive_boundary_preserved"
    assert nodes[main_id]["scientific_reporting_role"] == (
        "positive_main_result_claim_blocked"
    )
    assert nodes[main_id]["main_positive_boundary_blocked"] is True
    assert nodes[main_id]["release_targets_blocked"] is True
    assert nodes[main_id]["release_target_deliverable_ids"] == [
        "main_article_latex",
        "main_article_html",
    ]
    assert nodes[main_id]["linked_release_target_count"] == 2
    assert nodes[main_id]["method_recommendation_authorized"] is False
    assert nodes[main_id]["positive_claim_promotion_authorized"] is False
    assert (report_id, "SUMMARIZES_CONTROL", main_id) in edges
    assert (
        main_id,
        "DERIVED_FROM",
        "methodology_control:manuscript_section_evidence_packet:"
        "paper_main_results_blocked_evidence",
    ) in edges
    assert (
        main_id,
        "DERIVED_FROM",
        "methodology_control:claim_safe_result_extraction:main_results_table",
    ) in edges

    negative_id = boundary_prefix + "supplement_venn_abers_negative_evidence"
    assert nodes[negative_id]["boundary_status"] == (
        "negative_failure_mode_boundary_preserved"
    )
    assert nodes[negative_id]["scientific_reporting_role"] == (
        "venn_abers_negative_failure_mode_no_validation"
    )
    assert nodes[negative_id]["venn_abers_negative_boundary_preserved"] is True
    assert nodes[negative_id]["release_target_deliverable_ids"] == [
        "supplementary_document",
        "supplementary_document_latex",
        "supplementary_document_html",
    ]
    assert nodes[negative_id]["linked_release_target_count"] == 3
    assert nodes[negative_id]["method_recommendation_authorized"] is False
    assert nodes[negative_id]["positive_claim_promotion_authorized"] is False
    edge = edge_by_triple[(report_id, "SUMMARIZES_CONTROL", negative_id)]
    assert edge["evidence_path"].endswith("section_claim_boundary_audit.json")
    assert edge["evidence"] == "boundary_rows[4].packet_id"
    assert (
        negative_id,
        "DERIVED_FROM",
        "methodology_control:manuscript_section_evidence_packet:"
        "supplement_venn_abers_negative_evidence",
    ) in edges
    assert (
        negative_id,
        "DERIVED_FROM",
        "methodology_control:neutral_result_ledger:"
        "venn_abers_regression_negative_evidence",
    ) in edges
