import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "experiments/regression/scripts/audit_kg_publication_quality_readiness.py"
)
KG_QUALITY = ROOT / "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"
KG_PUBLICATION = (
    ROOT
    / "experiments/regression/reports/methodology_sanity_audit_20260627"
    / "kg_publication_quality_audit.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "audit_kg_publication_quality_readiness", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def passing_quality_with_modified_sources() -> dict:
    critical_row = {"coverage": 1.0}
    return {
        "metadata": {
            "thresholds": {
                "min_edge_selector_provenance_coverage": 1.0,
                "min_claim_edge_selector_provenance_coverage": 1.0,
            }
        },
        "graph": {
            "node_count": 4,
            "edge_count": 4,
            "edge_node_ratio": 1.0,
            "isolated_node_count": 0,
            "weak_component_count": 1,
        },
        "traceability": {
            "explicit_edge_provenance_coverage": 1.0,
            "specific_edge_provenance_coverage": 1.0,
            "edge_selector_provenance_coverage": 1.0,
            "edge_confidence_coverage": 1.0,
            "edge_confidence_reason_coverage": 1.0,
            "average_edge_confidence": 0.99,
            "distinct_edge_confidence_value_count": 3,
            "provenance_granularity_counts": {"artifact_root_selector": 1},
            "multiplicity_edge_count": 0,
            "high_multiplicity_edges_without_evidence_samples_count": 0,
        },
        "claim_traceability": {
            "claim_edge_selector_provenance_coverage": 1.0,
            "claim_edge_missing_selector_count": 0,
            "claim_edge_count": 0,
            "claim_relation_selector_coverage": {},
        },
        "ontology": {
            "unknown_node_types": [],
            "unknown_relation_types": [],
            "domain_range_violation_count": 0,
        },
        "summaries": {
            "direct_summary_coverage": 1.0,
            "semantic_summary_coverage": 1.0,
        },
        "observations": {
            "observation_node_ratio": 2.0,
            "paper_evidence_observation_node_ratio": 1.0,
            "topology_observation_count": 1,
            "total_observation_count": 8,
        },
        "freshness": {
            "tracked_source_coverage": {},
            "working_tree_relevant_untracked_count": 0,
            "working_tree_relevant_untracked_samples": [],
            "working_tree_relevant_modified_count": 4,
            "working_tree_relevant_modified_samples": [
                "experiments/regression/catalogs/knowledge_graph.json"
            ],
        },
        "critical_linkage": {
            "configs_queue_dataset": critical_row,
            "configs_queue_method": critical_row,
            "datasets_governed_by_policy": critical_row,
            "datasets_queued_or_reported": critical_row,
            "datasets_with_audit": critical_row,
            "datasets_with_source": critical_row,
            "decisions_link_dataset": critical_row,
            "methods_specified": critical_row,
            "report_sidecars_support_primary": critical_row,
            "reports_evaluate_method": critical_row,
            "reports_summarize_dataset": critical_row,
        },
        "endpoint_linkage": {
            "missing_endpoint_state_count": 0,
            "uncaveated_without_state_count": 0,
            "schema_incomplete_endpoint_result_count": 0,
            "zero_interval_endpoint_result_count": 0,
            "clean_zero_interval_endpoint_result_count": 0,
            "endpoint_result_count": 0,
            "endpoint_state_count": 0,
            "endpoint_caveat_count": 0,
            "uncaveated_endpoint_result_count": 0,
            "endpoint_result_relation_coverage": {},
        },
        "method_evidence": {
            "grouped_cv_duplicate_cluster_controls": {
                "tracked_method_count": 2,
                "present_count": 2,
                "registered_count": 2,
                "specified_count": 2,
                "queued_method_count": 2,
                "evaluated_method_count": 0,
                "pending_empirical_method_count": 2,
                "methods": {
                    "method:cv_plus_grouped": {},
                    "method:cv_minmax_grouped": {},
                },
            }
        },
        "issue_counts_by_severity": {},
    }


def test_checked_in_kg_publication_quality_is_current():
    audit = load_module()
    graph_path = ROOT / "experiments/regression/catalogs/knowledge_graph.json"

    payload = audit.build_payload(ROOT, graph_path, max_examples=5)
    markdown = audit.render_markdown(payload)

    assert payload["summary"]["overall_status"] in {
        "kg_publication_ready",
        "kg_publication_ready_with_polish_caveats",
    }
    assert payload["summary"]["hard_failed_check_count"] == 0
    assert payload["summary"]["tracked_missing_source_count"] == 0
    assert payload["summary"]["relevant_untracked_source_count"] == 0
    assert payload["summary"]["isolated_node_count"] == 0
    assert payload["summary"]["weak_component_count"] == 1
    assert payload["summary"]["explicit_edge_provenance_coverage"] == 1.0
    assert payload["summary"]["edge_selector_provenance_coverage"] == 1.0
    assert (
        payload["summary"]["provenance_granularity_counts"][
            "artifact_root_selector"
        ]
        > 0
    )
    assert payload["summary"]["claim_edge_selector_provenance_coverage"] >= 0.95
    assert payload["summary"]["claim_edge_missing_selector_count"] == 0
    assert payload["summary"]["edge_confidence_coverage"] == 1.0
    assert payload["summary"]["edge_confidence_reason_coverage"] == 1.0
    assert payload["summary"]["distinct_edge_confidence_value_count"] >= 3
    assert (
        payload["summary"][
            "high_multiplicity_edges_without_evidence_samples_count"
        ]
        == 0
    )
    assert payload["summary"]["paper_evidence_observation_node_ratio"] >= 1.0
    assert payload["summary"]["uncaveated_without_state_count"] == 0
    assert payload["summary"]["grouped_cv_tracked_method_count"] == 2
    assert payload["summary"]["grouped_cv_present_count"] == 2
    assert payload["summary"]["grouped_cv_registered_count"] == 2
    assert payload["summary"]["grouped_cv_specified_count"] == 2
    assert "method:cv_plus_grouped" in (
        payload["method_evidence_monitor"]["methods"]
    )
    assert "method:cv_minmax_grouped" in (
        payload["method_evidence_monitor"]["methods"]
    )
    assert payload["failed_checks"] == []
    assert "## Method Evidence Monitor" in markdown
    assert "## Claim Traceability" in markdown
    assert "Edge selector provenance coverage" in markdown
    assert "Claim-edge selector provenance coverage" in markdown
    assert "Paper-evidence observation/node ratio" in markdown
    assert "duplicate-cluster caveats require completed grouped runs" in markdown
    assert "fail_current_snapshot" not in markdown
    assert "missing tracked config" not in markdown
    assert "6 relevant untracked sources" not in markdown
    assert "untracked Lawschool row-signature sidecars" not in markdown


def test_checked_in_kg_publication_quality_matches_current_graph():
    graph = read_json(KG_QUALITY)["graph"]
    summary = read_json(KG_PUBLICATION)["summary"]

    assert summary["node_count"] == graph["node_count"]
    assert summary["edge_count"] == graph["edge_count"]
    assert summary["isolated_node_count"] == graph["isolated_node_count"]
    assert summary["weak_component_count"] == graph["weak_component_count"]


def test_retrospective_pre_run_snapshot_closes_publication_freeze(monkeypatch, tmp_path):
    audit = load_module()
    graph_path = tmp_path / "experiments/regression/catalogs/knowledge_graph.json"
    write_json(graph_path, {"schema": "test", "nodes": [], "edges": []})
    write_json(
        tmp_path / audit.RETROSPECTIVE_GATE,
        {
            "git_commit": "abc123def456",
            "pre_run_git_dirty": {
                "schema": "cpfi_retrospective_dirty_snapshot_v2",
                "is_dirty": False,
                "relevant_dirty_path_count": 0,
                "relevant_dirty_paths": [],
            },
        },
    )
    monkeypatch.setattr(audit, "current_commit", lambda root: "abc123def456")
    monkeypatch.setattr(
        audit.kg_quality,
        "audit_graph",
        lambda graph_path, repo_root, max_examples: passing_quality_with_modified_sources(),
    )

    payload = audit.build_payload(tmp_path, graph_path, max_examples=5)

    assert payload["summary"]["overall_status"] == "kg_publication_ready"
    assert payload["summary"]["relevant_modified_source_count"] == 4
    assert (
        payload["summary"]["publication_freeze_snapshot_source"]
        == "retrospective_quality_gate_pre_run_git_dirty"
    )
    assert payload["summary"]["publication_freeze_relevant_dirty_source_count"] == 0
    assert payload["polish_checks"]["publication_freeze_no_relevant_modified_sources"]
    assert payload["polish_caveats"] == []


def test_stale_retrospective_snapshot_does_not_close_publication_freeze(
    monkeypatch, tmp_path
):
    audit = load_module()
    graph_path = tmp_path / "experiments/regression/catalogs/knowledge_graph.json"
    write_json(graph_path, {"schema": "test", "nodes": [], "edges": []})
    write_json(
        tmp_path / audit.RETROSPECTIVE_GATE,
        {
            "git_commit": "old123",
            "pre_run_git_dirty": {
                "schema": "cpfi_retrospective_dirty_snapshot_v2",
                "is_dirty": False,
                "relevant_dirty_path_count": 0,
                "relevant_dirty_paths": [],
            },
        },
    )
    monkeypatch.setattr(audit, "current_commit", lambda root: "abc123def456")
    monkeypatch.setattr(
        audit.kg_quality,
        "audit_graph",
        lambda graph_path, repo_root, max_examples: passing_quality_with_modified_sources(),
    )

    payload = audit.build_payload(tmp_path, graph_path, max_examples=5)

    assert (
        payload["summary"]["overall_status"]
        == "kg_publication_ready_with_polish_caveats"
    )
    assert (
        payload["summary"]["publication_freeze_snapshot_source"]
        == "live_kg_publication_quality_freshness"
    )
    assert payload["summary"]["publication_freeze_relevant_dirty_source_count"] == 4
    assert "publication_freeze_no_relevant_modified_sources" in payload["polish_caveats"]


def test_broken_kg_publication_quality_fails(tmp_path):
    audit = load_module()
    graph_path = tmp_path / "experiments/regression/catalogs/knowledge_graph.json"
    write_json(
        graph_path,
        {
            "schema": "test",
            "node_count": 1,
            "edge_count": 1,
            "nodes": [
                {
                    "id": "dataset:demo",
                    "type": "dataset",
                    "summary": "Demo dataset.",
                }
            ],
            "edges": [
                {
                    "source": "dataset:demo",
                    "relation": "HAS_AUDIT",
                    "target": "audit:missing",
                }
            ],
        },
    )

    payload = audit.build_payload(tmp_path, graph_path, max_examples=5)

    assert payload["summary"]["overall_status"] == "fail_current_snapshot"
    assert payload["summary"]["hard_failed_check_count"] >= 1
    assert payload["failed_checks"]
