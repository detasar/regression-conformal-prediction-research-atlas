import json
from pathlib import Path

from experiments.regression.scripts import audit_graph_artifact_readiness as audit


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def graph_text(*tokens: str) -> str:
    token_lines = "\n".join(f"  A --> {token}[\"{token}\"]" for token in tokens)
    return (
        "```mermaid\n"
        "flowchart TD\n"
        "  A[\"Start\"] --> B[\"Middle\"]\n"
        "  B --> C[\"End\"]\n"
        f"{token_lines}\n"
        "```\n"
    )


def patch_specs(monkeypatch):
    specs = (
        {
            "graph_id": "mini_graph",
            "path": Path("experiments/regression/graphs/mini_graph.mmd"),
            "min_edge_count": 2,
            "required_tokens": ("RequiredToken",),
        },
    )
    monkeypatch.setattr(audit, "GRAPH_SPECS", specs)


def write_kg(root: Path):
    write_json(
        root / "experiments/regression/catalogs/knowledge_graph.json",
        {
            "nodes": [
                {"id": "graph:mini_graph", "type": "graph"},
                {"id": "catalog:knowledge_graph", "type": "catalog"},
            ],
            "edges": [
                {
                    "source": "graph:mini_graph",
                    "relation": "DOCUMENTS_GRAPH",
                    "target": "catalog:knowledge_graph",
                }
            ],
        },
    )


def test_graph_artifact_readiness_passes_for_traceable_current_graph(tmp_path, monkeypatch):
    patch_specs(monkeypatch)
    write(
        tmp_path / "experiments/regression/graphs/mini_graph.mmd",
        graph_text("RequiredToken"),
    )
    write_kg(tmp_path)

    payload = audit.build_payload(
        tmp_path,
        tmp_path / "experiments/regression/catalogs/knowledge_graph.json",
    )

    assert payload["summary"]["overall_status"] == "graph_artifact_readiness_pass"
    assert payload["summary"]["failed_check_count"] == 0
    assert payload["summary"]["all_required_tokens_present"] is True
    assert payload["summary"]["all_kg_graph_nodes_traceable"] is True


def test_graph_artifact_readiness_fails_when_current_token_is_missing(tmp_path, monkeypatch):
    patch_specs(monkeypatch)
    write(
        tmp_path / "experiments/regression/graphs/mini_graph.mmd",
        graph_text("OldToken"),
    )
    write_kg(tmp_path)

    payload = audit.build_payload(
        tmp_path,
        tmp_path / "experiments/regression/catalogs/knowledge_graph.json",
    )

    assert payload["summary"]["overall_status"] == "graph_artifact_readiness_fail"
    assert payload["summary"]["failed_check_count"] == 1
    failed = [row for row in payload["checks"] if row["status"] == "fail"]
    assert failed[0]["check_id"] == "mini_graph:current_audit_tokens"
