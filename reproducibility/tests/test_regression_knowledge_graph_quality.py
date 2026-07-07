import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = ROOT / "experiments/regression/scripts/audit_knowledge_graph_quality.py"


def load_audit_module():
    spec = importlib.util.spec_from_file_location(
        "audit_knowledge_graph_quality", AUDIT_SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_regression_knowledge_graph_quality_audit_exports_core_metrics():
    audit = load_audit_module()
    graph_path = ROOT / "experiments/regression/catalogs/knowledge_graph.json"
    graph = json.loads(graph_path.read_text())

    report = audit.audit_graph(graph_path=graph_path, repo_root=ROOT, max_examples=3)

    assert report["graph"]["node_count"] == len(graph["nodes"])
    assert report["graph"]["edge_count"] == len(graph["edges"])
    assert report["graph"]["edge_node_ratio"] > 0
    assert "graph_density" in report["graph"]
    assert "missing_endpoint_edge_count" in report["referential_integrity"]
    assert "explicit_edge_provenance_coverage" in report["traceability"]
    assert "edge_confidence_coverage" in report["traceability"]
    assert "edge_selector_provenance_coverage" in report["traceability"]
    assert "distinct_edge_confidence_value_count" in report["traceability"]
    assert "provenance_granularity_counts" in report["traceability"]
    assert (
        "high_multiplicity_edges_without_evidence_samples_count"
        in report["traceability"]
    )
    assert "claim_edge_selector_provenance_coverage" in report["claim_traceability"]
    assert "claim_relation_selector_coverage" in report["claim_traceability"]
    assert "fully_traceable_gate_coverage" in report["paper_gate_traceability"]
    assert "exact_selector_coverage" in report["paper_gate_traceability"]
    assert "node_type_counts" in report["ontology"]
    assert "relation_type_counts" in report["ontology"]
    assert report["ontology"]["critical_category_coverage"]["dataset"]["covered"]
    assert "direct_summary_coverage" in report["summaries"]
    assert "observation_node_ratio" in report["observations"]
    assert "paper_evidence_observation_node_ratio" in report["observations"]
    assert "topology_observation_count" in report["observations"]
    assert "tracked_source_coverage" in report["freshness"]
    assert "working_tree_relevant_modified_count" in report["freshness"]
    assert "working_tree_relevant_modified_samples" in report["freshness"]
    assert "endpoint_result_relation_coverage" in report["endpoint_linkage"]
    assert "endpoint_state_relation_coverage" in report["endpoint_linkage"]
    assert "missing_endpoint_state_count" in report["endpoint_linkage"]
    assert "grouped_cv_duplicate_cluster_controls" in report["method_evidence"]
    grouped_cv = report["method_evidence"]["grouped_cv_duplicate_cluster_controls"]
    assert grouped_cv["tracked_method_ids"] == [
        "method:cv_plus_grouped",
        "method:cv_minmax_grouped",
    ]
    assert grouped_cv["present_count"] == grouped_cv["tracked_method_count"]
    assert grouped_cv["registered_count"] == grouped_cv["tracked_method_count"]
    assert grouped_cv["specified_count"] == grouped_cv["tracked_method_count"]
    assert grouped_cv["methods"]["method:cv_plus_grouped"]["evidence_status"] in {
        "empirical_evidence_present",
        "queued_pending_report_evidence",
        "registered_pending_config_and_report_evidence",
    }
    assert "duplicate-cluster plus-family caveats" in grouped_cv["claim_boundary"]
    assert (
        "report:methodology_sanity_audit_20260627"
        not in report["critical_linkage"]["reports_summarize_dataset"][
            "missing_samples"
        ]
    )
    assert (
        "report:method_literature_coverage_audit"
        not in report["critical_linkage"]["reports_summarize_dataset"][
            "missing_samples"
        ]
    )
    assert (
        "report:methodology_sanity_audit_20260627"
        not in report["critical_linkage"]["reports_evaluate_method"]["missing_samples"]
    )
    assert (
        report["critical_linkage"]["report_sidecars_support_primary"]["coverage"] == 1.0
    )
    assert report["traceability"]["specific_edge_provenance_coverage"] == 1.0
    assert (
        report["traceability"]["edge_selector_provenance_coverage"]
        >= report["metadata"]["thresholds"]["min_edge_selector_provenance_coverage"]
    )
    assert report["traceability"]["edge_selector_provenance_coverage"] >= 0.80
    assert (
        report["claim_traceability"]["claim_edge_selector_provenance_coverage"]
        >= report["metadata"]["thresholds"][
            "min_claim_edge_selector_provenance_coverage"
        ]
    )
    assert (
        report["claim_traceability"]["claim_relation_selector_coverage"][
            "SUPPORTED_BY"
        ]["selector_provenance_coverage"]
        >= 0.95
    )
    assert report["paper_gate_traceability"]["paper_gate_count"] == 6
    assert (
        report["paper_gate_traceability"]["fully_traceable_gate_coverage"]
        >= report["metadata"]["thresholds"]["min_paper_gate_traceability_coverage"]
    )
    assert (
        report["paper_gate_traceability"]["exact_selector_coverage"]
        >= report["metadata"]["thresholds"]["min_paper_gate_source_selector_coverage"]
    )
    assert report["paper_gate_traceability"]["missing_traceability_link_count"] == 0
    assert report["traceability"]["distinct_edge_confidence_value_count"] >= 3
    assert (
        report["traceability"]["high_multiplicity_edges_without_evidence_samples_count"]
        == 0
    )
    assert report["observations"]["observation_node_ratio"] >= 2.0
    assert report["observations"]["paper_evidence_observation_node_ratio"] >= 1.0
    assert "partial_report_count" in report["critical_linkage"]
    assert (
        "report:duplicate_cluster_sensitivity_acs_income_log1p_row_signature"
        not in report["critical_linkage"]["reports_evaluate_method"]["missing_samples"]
    )
    assert (
        "report:datagov_source_review"
        not in report["critical_linkage"]["reports_evaluate_method"]["missing_samples"]
    )
    assert (
        report["critical_linkage"][
            "datasets_queued_or_reported_source_review_only_count"
        ]
        == 5
    )
    assert (
        "dataset:brfss_2024_llcp_source_review"
        not in report["critical_linkage"]["datasets_queued_or_reported"][
            "missing_samples"
        ]
    )
    assert (
        "dataset:world_bank_wdi_source_review"
        not in report["critical_linkage"]["datasets_queued_or_reported"][
            "missing_samples"
        ]
    )
    assert (
        "dataset:ipums_cps_source_review"
        not in report["critical_linkage"]["datasets_queued_or_reported"][
            "missing_samples"
        ]
    )
    assert (
        "dataset:icpsr_openicpsr_source_review"
        not in report["critical_linkage"]["datasets_queued_or_reported"][
            "missing_samples"
        ]
    )
    assert isinstance(report["issues"], list)


def test_knowledge_graph_quality_gate_flags_broken_edges(tmp_path):
    audit = load_audit_module()
    graph_path = tmp_path / "knowledge_graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "schema": "test",
                "node_count": 2,
                "edge_count": 2,
                "nodes": [
                    {
                        "id": "dataset:demo",
                        "type": "dataset",
                        "summary": "Demo regression dataset.",
                    },
                    {
                        "id": "policy:demo",
                        "type": "policy",
                        "summary": "Demo data policy.",
                    },
                ],
                "edges": [
                    {
                        "source": "dataset:demo",
                        "relation": "GOVERNED_BY",
                        "target": "policy:demo",
                        "provenance_id": "test:policy",
                        "confidence": 1.0,
                    },
                    {
                        "source": "dataset:demo",
                        "relation": "HAS_AUDIT",
                        "target": "audit:missing",
                    },
                ],
            }
        )
    )

    report = audit.audit_graph(
        graph_path=graph_path,
        repo_root=tmp_path,
        max_examples=5,
    )
    codes = {item["code"] for item in report["issues"]}

    assert report["referential_integrity"]["missing_endpoint_edge_count"] == 1
    assert report["traceability"]["explicit_edge_provenance_coverage"] == 0.5
    assert "MISSING_EDGE_ENDPOINTS" in codes
    assert "LOW_EDGE_PROVENANCE_COVERAGE" in codes
    assert audit.has_blocking_issues(report["issues"], "critical")


def test_knowledge_graph_quality_tracks_endpoint_result_semantic_gaps(tmp_path):
    audit = load_audit_module()
    graph_path = tmp_path / "knowledge_graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "schema": "test",
                "node_count": 6,
                "edge_count": 5,
                "nodes": [
                    {
                        "id": "endpoint_result:demo:cqr",
                        "type": "endpoint_result",
                        "intervals": 0,
                        "support_status": "clean_endpoint_support_diagnostic",
                        "summary": "Endpoint result for a demo run.",
                    },
                    {
                        "id": "report:demo",
                        "type": "report",
                        "summary": "Demo report.",
                    },
                    {
                        "id": "method:cqr",
                        "type": "method",
                        "summary": "CQR method.",
                    },
                    {
                        "id": "dataset:demo",
                        "type": "dataset",
                        "summary": "Demo dataset.",
                    },
                    {
                        "id": "metric:coverage",
                        "type": "metric",
                        "summary": "Coverage metric.",
                    },
                    {
                        "id": "config:demo",
                        "type": "config",
                        "summary": "Demo config.",
                    },
                ],
                "edges": [
                    {
                        "source": "endpoint_result:demo:cqr",
                        "relation": "SUPPORTED_BY_ENDPOINT_AUDIT",
                        "target": "report:demo",
                        "provenance_id": "p1",
                        "confidence": 1.0,
                    },
                    {
                        "source": "endpoint_result:demo:cqr",
                        "relation": "SUPPORTS_REPORT",
                        "target": "report:demo",
                        "provenance_id": "p2",
                        "confidence": 1.0,
                    },
                    {
                        "source": "endpoint_result:demo:cqr",
                        "relation": "EVALUATES_METHOD",
                        "target": "method:cqr",
                        "provenance_id": "p3",
                        "confidence": 1.0,
                    },
                    {
                        "source": "endpoint_result:demo:cqr",
                        "relation": "SUMMARIZES_DATASET",
                        "target": "dataset:demo",
                        "provenance_id": "p4",
                        "confidence": 1.0,
                    },
                    {
                        "source": "endpoint_result:demo:cqr",
                        "relation": "REPORTS_METRIC",
                        "target": "metric:coverage",
                        "provenance_id": "p5",
                        "confidence": 1.0,
                    },
                ],
            }
        )
    )

    report = audit.audit_graph(
        graph_path=graph_path,
        repo_root=tmp_path,
        max_examples=5,
    )
    issues_by_code = {item["code"]: item for item in report["issues"]}

    assert report["endpoint_linkage"]["endpoint_result_count"] == 1
    assert (
        report["endpoint_linkage"]["endpoint_result_relation_coverage"][
            "SUMMARIZES_CONFIG"
        ]["coverage"]
        == 0.0
    )
    assert report["endpoint_linkage"]["zero_interval_endpoint_result_count"] == 1
    assert report["endpoint_linkage"]["clean_zero_interval_endpoint_result_count"] == 1
    assert (
        issues_by_code["ENDPOINT_RESULTS_WITHOUT_CONFIG_LINKAGE"]["severity"] == "low"
    )
    assert (
        issues_by_code["CLEAN_ENDPOINT_RESULT_WITH_ZERO_INTERVALS"]["severity"]
        == "high"
    )
    assert issues_by_code["ENDPOINT_RESULT_WITH_ZERO_INTERVALS"]["severity"] == "medium"
    assert (
        issues_by_code["ENDPOINT_RESULTS_WITHOUT_EXPLICIT_STATE"]["severity"]
        == "medium"
    )
