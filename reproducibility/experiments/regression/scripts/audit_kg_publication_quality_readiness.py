"""Audit publication-grade knowledge-graph readiness from live KG metrics.

The knowledge graph is a provenance layer, not empirical proof. This audit
keeps that boundary explicit while replacing stale hand-written KG publication
snapshots with a reproducible report derived from the current graph.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts import audit_knowledge_graph_quality as kg_quality


SCHEMA = "cpfi_kg_publication_quality_audit_v2"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_GRAPH = Path("experiments/regression/catalogs/knowledge_graph.json")
DEFAULT_OUT = REPORT_DIR / "kg_publication_quality_audit.json"
RETROSPECTIVE_GATE = REPORT_DIR / "retrospective_quality_gate.json"
PAPER_OBSERVATION_NODE_RATIO_TARGET = 2.0
PAPER_EVIDENCE_OBSERVATION_NODE_RATIO_TARGET = 1.0
STALE_TOKENS = (
    "fail_current_snapshot",
    "missing tracked config",
    "6 relevant untracked sources",
    "untracked Lawschool row-signature sidecars",
    "ae7b2591ffe7",
    "1,700",
    "11,171",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--graph", default=str(DEFAULT_GRAPH), help="Knowledge graph JSON path.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    parser.add_argument("--max-examples", type=int, default=25)
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def severity_total(counts: dict[str, Any], names: tuple[str, ...]) -> int:
    return sum(int(counts.get(name) or 0) for name in names)


def coverage_value(row: dict[str, Any], key: str) -> float:
    value = (row.get(key) or {}).get("coverage")
    return float(value or 0.0)


def tracked_missing_count(freshness: dict[str, Any]) -> int:
    tracked = freshness.get("tracked_source_coverage") or {}
    return sum(
        int(row.get("missing_count") or 0)
        for row in tracked.values()
        if isinstance(row, dict)
    )


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def current_commit(root: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--short=12", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip()
    return value or None


def retrospective_pre_run_freeze_snapshot(root: Path) -> dict[str, Any] | None:
    """Return the current gate's pre-run dirty snapshot when it matches HEAD."""
    payload = read_json(root / RETROSPECTIVE_GATE)
    snapshot = payload.get("pre_run_git_dirty")
    if not isinstance(snapshot, dict) or not snapshot.get("schema"):
        return None
    if payload.get("git_commit") != current_commit(root):
        return None
    row = dict(snapshot)
    row["snapshot_source"] = "retrospective_quality_gate_pre_run_git_dirty"
    return row


def freeze_snapshot_from_freshness(freshness: dict[str, Any]) -> dict[str, Any]:
    modified = int(freshness.get("working_tree_relevant_modified_count") or 0)
    untracked = int(freshness.get("working_tree_relevant_untracked_count") or 0)
    samples = list(freshness.get("working_tree_relevant_modified_samples") or [])
    samples.extend(freshness.get("working_tree_relevant_untracked_samples") or [])
    return {
        "schema": "cpfi_kg_publication_live_freshness_snapshot_v1",
        "snapshot_source": "live_kg_publication_quality_freshness",
        "is_dirty": bool(modified or untracked),
        "relevant_dirty_path_count": modified + untracked,
        "relevant_dirty_paths": samples,
    }


def publication_freeze_snapshot(root: Path, freshness: dict[str, Any]) -> dict[str, Any]:
    return retrospective_pre_run_freeze_snapshot(root) or freeze_snapshot_from_freshness(
        freshness
    )


def all_critical_linkage_complete(critical: dict[str, Any]) -> bool:
    required = (
        "configs_queue_dataset",
        "configs_queue_method",
        "datasets_governed_by_policy",
        "datasets_queued_or_reported",
        "datasets_with_audit",
        "datasets_with_source",
        "decisions_link_dataset",
        "methods_specified",
        "report_sidecars_support_primary",
        "reports_evaluate_method",
        "reports_summarize_dataset",
    )
    return all(coverage_value(critical, key) == 1.0 for key in required)


def endpoint_publication_state_complete(endpoint: dict[str, Any]) -> bool:
    return (
        int(endpoint.get("missing_endpoint_state_count") or 0) == 0
        and int(endpoint.get("uncaveated_without_state_count") or 0) == 0
        and int(endpoint.get("schema_incomplete_endpoint_result_count") or 0) == 0
    )


def build_payload(root: Path, graph_path: Path, max_examples: int = 25) -> dict[str, Any]:
    quality = kg_quality.audit_graph(
        graph_path=graph_path,
        repo_root=root,
        max_examples=max_examples,
    )
    graph = quality.get("graph") or {}
    traceability = quality.get("traceability") or {}
    claim_traceability = quality.get("claim_traceability") or {}
    ontology = quality.get("ontology") or {}
    summaries = quality.get("summaries") or {}
    observations = quality.get("observations") or {}
    freshness = quality.get("freshness") or {}
    critical = quality.get("critical_linkage") or {}
    endpoint = quality.get("endpoint_linkage") or {}
    method_evidence = quality.get("method_evidence") or {}
    grouped_cv_monitor = (
        method_evidence.get("grouped_cv_duplicate_cluster_controls") or {}
    )
    issue_counts = quality.get("issue_counts_by_severity") or {}
    missing_tracked = tracked_missing_count(freshness)
    untracked_count = int(freshness.get("working_tree_relevant_untracked_count") or 0)
    modified_count = int(freshness.get("working_tree_relevant_modified_count") or 0)
    freeze_snapshot = publication_freeze_snapshot(root, freshness)
    freeze_relevant_dirty_count = int(
        freeze_snapshot.get("relevant_dirty_path_count") or 0
    )
    hard_issue_count = severity_total(issue_counts, ("medium", "high", "critical"))

    hard_checks = {
        "kg_quality_has_no_medium_or_higher_issues": hard_issue_count == 0,
        "no_missing_tracked_sources": missing_tracked == 0,
        "no_relevant_untracked_sources": untracked_count == 0,
        "no_orphan_nodes": int(graph.get("isolated_node_count") or 0) == 0,
        "single_weak_component": int(graph.get("weak_component_count") or 0) == 1,
        "edge_provenance_complete": (
            float(traceability.get("explicit_edge_provenance_coverage") or 0.0) == 1.0
        ),
        "edge_confidence_and_reason_complete": (
            float(traceability.get("edge_confidence_coverage") or 0.0) == 1.0
            and float(traceability.get("edge_confidence_reason_coverage") or 0.0) == 1.0
        ),
        "ontology_domain_range_clean": (
            not ontology.get("unknown_node_types")
            and not ontology.get("unknown_relation_types")
            and int(ontology.get("domain_range_violation_count") or 0) == 0
        ),
        "critical_linkage_complete": all_critical_linkage_complete(critical),
        "endpoint_publication_state_complete": endpoint_publication_state_complete(endpoint),
        "no_zero_interval_endpoint_results": (
            int(endpoint.get("zero_interval_endpoint_result_count") or 0) == 0
            and int(endpoint.get("clean_zero_interval_endpoint_result_count") or 0) == 0
        ),
        "summary_coverage_complete": (
            float(summaries.get("direct_summary_coverage") or 0.0) == 1.0
            and float(summaries.get("semantic_summary_coverage") or 0.0) == 1.0
        ),
    }
    polish_checks = {
        "specific_edge_provenance_complete": (
            float(traceability.get("specific_edge_provenance_coverage") or 0.0) == 1.0
        ),
        "edge_selector_provenance_target_met": (
            float(traceability.get("edge_selector_provenance_coverage") or 0.0)
            >= float(
                (quality.get("metadata") or {})
                .get("thresholds", {})
                .get("min_edge_selector_provenance_coverage", 0.0)
            )
        ),
        "claim_edge_selector_provenance_target_met": (
            float(
                claim_traceability.get(
                    "claim_edge_selector_provenance_coverage"
                )
                or 0.0
            )
            >= float(
                (quality.get("metadata") or {})
                .get("thresholds", {})
                .get("min_claim_edge_selector_provenance_coverage", 0.0)
            )
        ),
        "edge_confidence_distribution_calibrated": (
            int(traceability.get("distinct_edge_confidence_value_count") or 0) >= 3
        ),
        "multiplicity_evidence_samples_present": (
            int(
                traceability.get(
                    "high_multiplicity_edges_without_evidence_samples_count"
                )
                or 0
            )
            == 0
        ),
        "paper_observation_node_ratio_target_met": (
            float(observations.get("observation_node_ratio") or 0.0)
            >= PAPER_OBSERVATION_NODE_RATIO_TARGET
        ),
        "paper_evidence_observation_node_ratio_target_met": (
            float(observations.get("paper_evidence_observation_node_ratio") or 0.0)
            >= PAPER_EVIDENCE_OBSERVATION_NODE_RATIO_TARGET
        ),
        "publication_freeze_no_relevant_modified_sources": (
            freeze_relevant_dirty_count == 0
        ),
    }
    failed_checks = [key for key, value in hard_checks.items() if not value]
    polish_caveats = [key for key, value in polish_checks.items() if not value]
    if failed_checks:
        overall_status = "fail_current_snapshot"
    elif polish_caveats:
        overall_status = "kg_publication_ready_with_polish_caveats"
    else:
        overall_status = "kg_publication_ready"

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "graph": rel(graph_path, root),
        "quality_source": "experiments/regression/scripts/audit_knowledge_graph_quality.py",
        "summary": {
            "overall_status": overall_status,
            "node_count": graph.get("node_count"),
            "edge_count": graph.get("edge_count"),
            "edge_node_ratio": graph.get("edge_node_ratio"),
            "isolated_node_count": graph.get("isolated_node_count"),
            "weak_component_count": graph.get("weak_component_count"),
            "explicit_edge_provenance_coverage": traceability.get(
                "explicit_edge_provenance_coverage"
            ),
            "specific_edge_provenance_coverage": traceability.get(
                "specific_edge_provenance_coverage"
            ),
            "edge_selector_provenance_coverage": traceability.get(
                "edge_selector_provenance_coverage"
            ),
            "claim_edge_selector_provenance_coverage": (
                claim_traceability.get("claim_edge_selector_provenance_coverage")
            ),
            "claim_edge_missing_selector_count": (
                claim_traceability.get("claim_edge_missing_selector_count")
            ),
            "claim_edge_count": claim_traceability.get("claim_edge_count"),
            "claim_relation_selector_coverage": (
                claim_traceability.get("claim_relation_selector_coverage")
            ),
            "edge_confidence_coverage": traceability.get("edge_confidence_coverage"),
            "edge_confidence_reason_coverage": traceability.get(
                "edge_confidence_reason_coverage"
            ),
            "average_edge_confidence": traceability.get("average_edge_confidence"),
            "distinct_edge_confidence_value_count": traceability.get(
                "distinct_edge_confidence_value_count"
            ),
            "provenance_granularity_counts": traceability.get(
                "provenance_granularity_counts"
            ),
            "multiplicity_edge_count": traceability.get("multiplicity_edge_count"),
            "high_multiplicity_edges_without_evidence_samples_count": (
                traceability.get(
                    "high_multiplicity_edges_without_evidence_samples_count"
                )
            ),
            "direct_summary_coverage": summaries.get("direct_summary_coverage"),
            "semantic_summary_coverage": summaries.get("semantic_summary_coverage"),
            "observation_node_ratio": observations.get("observation_node_ratio"),
            "paper_evidence_observation_node_ratio": observations.get(
                "paper_evidence_observation_node_ratio"
            ),
            "topology_observation_count": observations.get("topology_observation_count"),
            "total_observation_count": observations.get("total_observation_count"),
            "tracked_missing_source_count": missing_tracked,
            "relevant_untracked_source_count": untracked_count,
            "relevant_modified_source_count": modified_count,
            "publication_freeze_snapshot_source": freeze_snapshot.get(
                "snapshot_source"
            ),
            "publication_freeze_relevant_dirty_source_count": (
                freeze_relevant_dirty_count
            ),
            "publication_freeze_is_dirty": freeze_snapshot.get("is_dirty"),
            "endpoint_result_count": endpoint.get("endpoint_result_count"),
            "endpoint_state_count": endpoint.get("endpoint_state_count"),
            "endpoint_caveat_count": endpoint.get("endpoint_caveat_count"),
            "uncaveated_endpoint_result_count": endpoint.get(
                "uncaveated_endpoint_result_count"
            ),
            "uncaveated_without_state_count": endpoint.get(
                "uncaveated_without_state_count"
            ),
            "grouped_cv_tracked_method_count": grouped_cv_monitor.get(
                "tracked_method_count"
            ),
            "grouped_cv_present_count": grouped_cv_monitor.get("present_count"),
            "grouped_cv_registered_count": grouped_cv_monitor.get("registered_count"),
            "grouped_cv_specified_count": grouped_cv_monitor.get("specified_count"),
            "grouped_cv_queued_method_count": grouped_cv_monitor.get(
                "queued_method_count"
            ),
            "grouped_cv_evaluated_method_count": grouped_cv_monitor.get(
                "evaluated_method_count"
            ),
            "grouped_cv_pending_empirical_method_count": grouped_cv_monitor.get(
                "pending_empirical_method_count"
            ),
            "issue_counts_by_severity": issue_counts,
            "hard_failed_check_count": len(failed_checks),
            "polish_caveat_count": len(polish_caveats),
        },
        "hard_checks": hard_checks,
        "polish_checks": polish_checks,
        "failed_checks": failed_checks,
        "polish_caveats": polish_caveats,
        "critical_linkage": critical,
        "claim_traceability": claim_traceability,
        "endpoint_relation_coverage": endpoint.get("endpoint_result_relation_coverage") or {},
        "method_evidence_monitor": grouped_cv_monitor,
        "claim_boundaries": [
            "The KG is a provenance, traceability, and audit-navigation layer; it does not prove empirical model superiority.",
            "A publication-ready KG status only means graph structure, provenance, ontology, freshness, and linkage checks are fit for paper evidence navigation.",
            "Final model/method selection, fairness conclusions, bounded-support validity, and validated Venn-Abers regression still require their dedicated scientific gates.",
            "Grouped CV+ and grouped CV-minmax registration is methodology scaffolding; duplicate-cluster caveats require completed grouped runs and endpoint audits before closure.",
            "Working-tree modified source counts are audit-time telemetry; publication freeze uses the retrospective pre-run dirty snapshot when the audit is executed inside the retrospective gate.",
            "A clean publication-freeze snapshot does not promote final scientific claims; it only records that the KG evidence snapshot started from a clean relevant worktree.",
            "Generated topology observations support navigation only; manuscript prose should prefer non-topology, source-grounded observations and fact-level edge selectors.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    issue_counts = json.dumps(summary["issue_counts_by_severity"], sort_keys=True)
    lines = [
        "# KG Publication Quality Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Graph: `{payload['graph']}`",
        f"- Nodes / edges: {summary['node_count']} / {summary['edge_count']}",
        f"- Edge/node ratio: {summary['edge_node_ratio']}",
        f"- Isolated nodes: {summary['isolated_node_count']}",
        f"- Weak components: {summary['weak_component_count']}",
        f"- Issue counts: `{issue_counts}`",
        f"- Hard failed checks: {summary['hard_failed_check_count']}",
        f"- Polish caveats: {summary['polish_caveat_count']}",
        "",
        "## Claim Boundary",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Core Metrics",
            "",
            "| Dimension | Value |",
            "| --- | --- |",
            f"| Explicit edge provenance coverage | {summary['explicit_edge_provenance_coverage']} |",
            f"| Specific edge provenance coverage | {summary['specific_edge_provenance_coverage']} |",
            f"| Edge selector provenance coverage | {summary['edge_selector_provenance_coverage']} |",
            f"| Claim-edge selector provenance coverage | {summary['claim_edge_selector_provenance_coverage']} |",
            f"| Claim edges missing selectors | {summary['claim_edge_missing_selector_count']} / {summary['claim_edge_count']} |",
            f"| Edge confidence coverage | {summary['edge_confidence_coverage']} |",
            f"| Edge confidence-reason coverage | {summary['edge_confidence_reason_coverage']} |",
            f"| Average edge confidence | {summary['average_edge_confidence']} |",
            f"| Distinct edge confidence values | {summary['distinct_edge_confidence_value_count']} |",
            f"| Provenance granularity counts | `{json.dumps(summary['provenance_granularity_counts'], sort_keys=True)}` |",
            f"| Multiplicity edges | {summary['multiplicity_edge_count']} |",
            f"| Multiplicity edges missing evidence samples | {summary['high_multiplicity_edges_without_evidence_samples_count']} |",
            f"| Direct summary coverage | {summary['direct_summary_coverage']} |",
            f"| Semantic summary coverage | {summary['semantic_summary_coverage']} |",
            f"| Observation/node ratio | {summary['observation_node_ratio']} |",
            f"| Paper-evidence observation/node ratio | {summary['paper_evidence_observation_node_ratio']} |",
            f"| Topology observations | {summary['topology_observation_count']} |",
            f"| Total observations | {summary['total_observation_count']} |",
            f"| Missing tracked sources | {summary['tracked_missing_source_count']} |",
            f"| Relevant untracked sources | {summary['relevant_untracked_source_count']} |",
            f"| Relevant modified sources | {summary['relevant_modified_source_count']} |",
            f"| Publication-freeze snapshot source | {summary['publication_freeze_snapshot_source']} |",
            f"| Publication-freeze relevant dirty sources | {summary['publication_freeze_relevant_dirty_source_count']} |",
            f"| Endpoint results / states / caveats | {summary['endpoint_result_count']} / {summary['endpoint_state_count']} / {summary['endpoint_caveat_count']} |",
            f"| Uncaveated endpoint results without state | {summary['uncaveated_without_state_count']} |",
            f"| Grouped-CV tracked / queued / evaluated methods | {summary['grouped_cv_tracked_method_count']} / {summary['grouped_cv_queued_method_count']} / {summary['grouped_cv_evaluated_method_count']} |",
            f"| Grouped-CV pending empirical methods | {summary['grouped_cv_pending_empirical_method_count']} |",
        ]
    )
    claim_relation_rows = summary.get("claim_relation_selector_coverage") or {}
    lines.extend(
        [
            "",
            "## Claim Traceability",
            "",
            "| Relation | Selector coverage | Selector edges | Total edges | Missing selectors |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for relation, row in sorted(claim_relation_rows.items()):
        lines.append(
            f"| `{relation}` | {row.get('selector_provenance_coverage')} | "
            f"{row.get('selector_provenance_count')} | {row.get('edge_count')} | "
            f"{row.get('missing_selector_count')} |"
        )
    if not claim_relation_rows:
        lines.append("| `none` | 1.0 | 0 | 0 | 0 |")
    lines.extend(
        [
            "",
            "## Method Evidence Monitor",
            "",
            "| Method | Evidence status | Registered | Specified | Queued configs | Evaluating reports |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    monitor = payload.get("method_evidence_monitor") or {}
    methods = monitor.get("methods") or {}
    for method_id, row in sorted(methods.items()):
        lines.append(
            f"| `{method_id}` | `{row.get('evidence_status')}` | "
            f"{row.get('registered_in_count')} | {row.get('specified_by_count')} | "
            f"{row.get('queued_config_count')} | {row.get('evaluating_report_count')} |"
        )
    if not methods:
        lines.append("| `none` | `not_available` | 0 | 0 | 0 | 0 |")
    if monitor.get("claim_boundary"):
        lines.extend(["", f"- {monitor['claim_boundary']}"])
    lines.extend(
        [
            "",
            "## Hard Checks",
            "",
            "| Check | Status |",
            "| --- | --- |",
        ]
    )
    for check, passed in payload["hard_checks"].items():
        lines.append(f"| `{check}` | `{passed}` |")
    lines.extend(
        [
            "",
            "## Paper-Polish Checks",
            "",
            "| Check | Status |",
            "| --- | --- |",
        ]
    )
    for check, passed in payload["polish_checks"].items():
        lines.append(f"| `{check}` | `{passed}` |")
    lines.extend(
        [
            "",
            "## Remaining Polish Caveats",
            "",
        ]
    )
    if payload["polish_caveats"]:
        lines.extend(f"- `{item}`" for item in payload["polish_caveats"])
    else:
        lines.append("- None.")
    text = "\n".join(lines).rstrip() + "\n"
    lowered = text.lower()
    stale_hits = [
        token
        for token in STALE_TOKENS
        if token.lower() in lowered
        and not (
            token == "fail_current_snapshot"
            and summary["overall_status"] == "fail_current_snapshot"
        )
    ]
    if stale_hits:
        raise ValueError(f"rendered stale KG publication tokens: {stale_hits}")
    return text


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    graph_path = resolve(root, args.graph)
    out_path = resolve(root, args.out)
    payload = build_payload(root, graph_path, max_examples=args.max_examples)
    markdown = render_markdown(payload)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), markdown)
    print(
        json.dumps(
            {
                "status": payload["summary"]["overall_status"],
                "out": rel(out_path, root),
                "failed_checks": payload["failed_checks"],
                "polish_caveats": payload["polish_caveats"],
            },
            sort_keys=True,
        )
    )
    return 0 if not payload["failed_checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
