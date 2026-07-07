"""Audit manuscript-facing graph artifacts for freshness and KG traceability."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_graph_artifact_readiness_audit_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = REPORT_DIR / "graph_artifact_readiness_audit.json"
DEFAULT_KG = Path("experiments/regression/catalogs/knowledge_graph.json")

GRAPH_SPECS: tuple[dict[str, Any], ...] = (
    {
        "graph_id": "data_flow",
        "path": Path("experiments/regression/graphs/data_flow.mmd"),
        "min_edge_count": 40,
        "required_tokens": (
            "GraphArtifactReadinessAudit",
            "VennAbersValidationReadinessAudit",
            "RetrospectiveQualityGate",
            "KGPublicationQualityAudit",
            "PublicationPreparationPackets",
            "ReviewerDesignBrief",
            "VisualTableAuditPlan",
            "VisualTableAuditReport",
            "VisualTableRenderCandidateAudit",
            "PublicationRetentionReadinessAudit",
            "DraftVisualTableArtifacts",
            "NeutralResultLedger",
            "KGNavigationUsabilityAudit",
            "TriptychDecision",
        ),
    },
    {
        "graph_id": "control_flow",
        "path": Path("experiments/regression/graphs/control_flow.mmd"),
        "min_edge_count": 40,
        "required_tokens": (
            "GraphArtifactReadinessAudit",
            "VennAbersValidationReadinessAudit",
            "PublicationMethodologyAudit",
            "RetrospectiveQualityGate",
            "PublicationPreparationPackets",
            "ReviewerDesignBrief",
            "VisualTableAuditPlan",
            "VisualTableAuditReport",
            "VisualTableRenderCandidateAudit",
            "PublicationRetentionReadinessAudit",
            "DraftVisualTableArtifacts",
            "NeutralResultLedger",
            "KGNavigationUsabilityAudit",
            "TriptychDecision",
        ),
    },
    {
        "graph_id": "dependency_graph",
        "path": Path("experiments/regression/graphs/dependency_graph.mmd"),
        "min_edge_count": 40,
        "required_tokens": (
            "GraphArtifactReadinessAuditScript",
            "VennAbersValidationReadinessAuditScript",
            "KnowledgeGraphQualityScript",
            "KGPublicationQualityScript",
            "PublicationPreparationPacketsScript",
            "ReviewerDesignBriefScript",
            "VisualTableAuditPlanScript",
            "VisualTableAuditExecutionScript",
            "VisualTableRenderCandidateAuditScript",
            "PublicationRetentionReadinessAuditScript",
            "NeutralResultLedgerScript",
        ),
    },
    {
        "graph_id": "system_ontology",
        "path": Path("experiments/regression/graphs/system_ontology.mmd"),
        "min_edge_count": 40,
        "required_tokens": (
            "GraphArtifactReadinessAudit",
            "VennAbersValidationReadiness",
            "FinalClaimBoundary",
            "KGPublicationQuality",
            "PublicationPreparationPackets",
            "ReviewerDesignBrief",
            "VisualTableAuditPlan",
            "VisualTableAuditReport",
            "VisualTableRenderCandidateAudit",
            "PublicationRetentionReadinessAudit",
            "DraftVisualTableArtifacts",
            "NeutralResultLedger",
            "KGNavigationUsabilityAudit",
            "TriptychDecision",
        ),
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--knowledge-graph", default=str(DEFAULT_KG), help="Knowledge graph JSON path.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_json_if_present(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def graph_edge_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if "-->" in line or "---" in line)


def graph_node_count(text: str) -> int:
    node_ids: set[str] = set()
    for match in re.finditer(r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*(?:\[|\{|\()", text, re.MULTILINE):
        node_ids.add(match.group(1))
    for match in re.finditer(r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*[-.]*>", text, re.MULTILINE):
        node_ids.add(match.group(1))
    for match in re.finditer(r"-->\s*([A-Za-z][A-Za-z0-9_]*)", text):
        node_ids.add(match.group(1))
    return len(node_ids)


def check(check_id: str, passed: bool, severity: str, description: str, **details: Any) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "description": description,
        "details": details,
    }


def kg_indexes(payload: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], set[tuple[str, str, str]]]:
    nodes = {
        str(node.get("id")): node
        for node in payload.get("nodes", []) or []
        if isinstance(node, dict) and node.get("id")
    }
    edges = {
        (str(edge.get("source")), str(edge.get("relation")), str(edge.get("target")))
        for edge in payload.get("edges", []) or []
        if isinstance(edge, dict)
    }
    return nodes, edges


def build_payload(root: Path, kg_path: Path) -> dict[str, Any]:
    kg_payload = read_json_if_present(kg_path)
    kg_nodes, kg_edges = kg_indexes(kg_payload)
    graph_rows: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    for spec in GRAPH_SPECS:
        graph_id = str(spec["graph_id"])
        path = resolve(root, spec["path"])
        node_id = f"graph:{graph_id}"
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        edge_count = graph_edge_count(text)
        node_count = graph_node_count(text)
        missing_tokens = [
            token for token in spec["required_tokens"] if token not in text
        ]
        kg_node = kg_nodes.get(node_id)
        kg_edge = (node_id, "DOCUMENTS_GRAPH", "catalog:knowledge_graph") in kg_edges
        row = {
            "graph_id": graph_id,
            "node_id": node_id,
            "path": rel(path, root),
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "line_count": len(text.splitlines()),
            "node_count_estimate": node_count,
            "edge_count_estimate": edge_count,
            "min_edge_count": spec["min_edge_count"],
            "required_tokens": list(spec["required_tokens"]),
            "missing_required_tokens": missing_tokens,
            "kg_node_present": bool(kg_node),
            "kg_documents_catalog_edge_present": kg_edge,
        }
        graph_rows.append(row)
        checks.extend(
            [
                check(
                    f"{graph_id}:file_present",
                    row["exists"] and row["size_bytes"] > 0,
                    "critical",
                    "Graph artifact file exists and is non-empty.",
                    path=row["path"],
                ),
                check(
                    f"{graph_id}:mermaid_fenced",
                    text.strip().startswith("```mermaid") and text.strip().endswith("```"),
                    "high",
                    "Graph artifact is a fenced Mermaid document.",
                    path=row["path"],
                ),
                check(
                    f"{graph_id}:flowchart_declared",
                    "flowchart " in text,
                    "high",
                    "Graph artifact declares a Mermaid flowchart.",
                    path=row["path"],
                ),
                check(
                    f"{graph_id}:edge_density_floor",
                    edge_count >= int(spec["min_edge_count"]),
                    "medium",
                    "Graph artifact has enough explicit edges to be publication-useful.",
                    path=row["path"],
                    edge_count=edge_count,
                    min_edge_count=spec["min_edge_count"],
                ),
                check(
                    f"{graph_id}:current_audit_tokens",
                    not missing_tokens,
                    "critical",
                    "Graph artifact mentions the current gate/audit nodes required for manuscript navigation.",
                    path=row["path"],
                    missing_required_tokens=missing_tokens,
                ),
                check(
                    f"{graph_id}:kg_node_traceable",
                    bool(kg_node) and kg_edge,
                    "critical",
                    "Graph artifact has a KG graph node and DOCUMENTS_GRAPH edge to the KG catalog.",
                    path=row["path"],
                    node_id=node_id,
                    kg_node_present=bool(kg_node),
                    kg_documents_catalog_edge_present=kg_edge,
                ),
            ]
        )

    status_counts = Counter(row["status"] for row in checks)
    failed_check_count = int(status_counts.get("fail", 0))
    overall_status = (
        "graph_artifact_readiness_pass"
        if failed_check_count == 0
        else "graph_artifact_readiness_fail"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "knowledge_graph": rel(kg_path, root),
        "summary": {
            "overall_status": overall_status,
            "graph_count": len(graph_rows),
            "failed_check_count": failed_check_count,
            "check_status_counts": dict(sorted(status_counts.items())),
            "total_edge_count_estimate": sum(int(row["edge_count_estimate"]) for row in graph_rows),
            "total_node_count_estimate": sum(int(row["node_count_estimate"]) for row in graph_rows),
            "all_required_tokens_present": all(not row["missing_required_tokens"] for row in graph_rows),
            "all_kg_graph_nodes_traceable": all(
                row["kg_node_present"] and row["kg_documents_catalog_edge_present"]
                for row in graph_rows
            ),
        },
        "graph_rows": graph_rows,
        "checks": checks,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Graph Artifact Readiness Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Graph count: {summary['graph_count']}",
        f"- Failed checks: {summary['failed_check_count']}",
        f"- Total estimated nodes / edges: {summary['total_node_count_estimate']} / {summary['total_edge_count_estimate']}",
        f"- Required tokens present: `{summary['all_required_tokens_present']}`",
        f"- KG graph nodes traceable: `{summary['all_kg_graph_nodes_traceable']}`",
        "",
        "## Graphs",
        "",
        "| Graph | Nodes | Edges | Missing tokens | KG traceable |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["graph_rows"]:
        missing = ", ".join(row["missing_required_tokens"]) or "none"
        traceable = row["kg_node_present"] and row["kg_documents_catalog_edge_present"]
        lines.append(
            "| "
            f"`{row['graph_id']}` | "
            f"{row['node_count_estimate']} | "
            f"{row['edge_count_estimate']} | "
            f"{missing} | "
            f"`{traceable}` |"
        )
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status | Severity |",
            "| --- | --- | --- |",
        ]
    )
    for row in payload["checks"]:
        lines.append(f"| `{row['check_id']}` | `{row['status']}` | {row['severity']} |")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    kg_path = resolve(root, args.knowledge_graph)
    out_path = resolve(root, args.out)
    payload = build_payload(root, kg_path)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok" if payload["summary"]["failed_check_count"] == 0 else "fail",
                "out": rel(out_path, root),
                **payload["summary"],
            },
            sort_keys=True,
        )
    )
    return 1 if payload["summary"]["failed_check_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
