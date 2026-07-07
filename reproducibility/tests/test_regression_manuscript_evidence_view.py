import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments/regression/scripts/build_manuscript_evidence_view.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "build_manuscript_evidence_view", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_evidence_view_links_claim_manifest_and_endpoint_counts(tmp_path):
    view = load_module()
    write_json(
        tmp_path / "experiments/regression/catalogs/manuscript_claim_register.json",
        {
            "claims": [
                {
                    "claim_id": "demo_claim",
                    "claim_type": "dataset_robustness_gate",
                    "status": "robustness_evidence_gate_passed_with_caveats",
                    "dataset_ids": ["demo_dataset"],
                    "supporting_node_ids": [
                        "manifest:demo_run:publication_readiness",
                        "report:demo_run:endpoint_audit",
                    ],
                    "not_claiming": ["No final method is selected."],
                    "requirements": [
                        {"requirement_id": "endpoint_audit", "status": "present"}
                    ],
                }
            ]
        },
    )
    write_json(
        tmp_path / "experiments/regression/catalogs/manuscript_bundle_index.json",
        {
            "bundles": [
                {
                    "bundle_id": "demo_run",
                    "status": "completed_with_caveats",
                    "manifest_path": "experiments/regression/reports/demo_run/publication_readiness_manifest.md",
                    "paper_table_candidate": "robustness_results_table",
                    "promotion_blockers": ["Endpoint caveat remains."],
                }
            ]
        },
    )
    write_json(
        tmp_path / "experiments/regression/catalogs/knowledge_graph.json",
        {
            "edges": [
                {
                    "source": "endpoint_result:demo_run:cqr",
                    "relation": "SUPPORTED_BY_ENDPOINT_AUDIT",
                    "target": "report:demo_run:endpoint_audit",
                },
                {
                    "source": "endpoint_caveat:demo_run:cqr",
                    "relation": "SUPPORTED_BY_ENDPOINT_AUDIT",
                    "target": "report:demo_run:endpoint_audit",
                },
                {
                    "source": "endpoint_state:demo_run:cqr",
                    "relation": "SUPPORTED_BY_ENDPOINT_AUDIT",
                    "target": "report:demo_run:endpoint_audit",
                },
            ]
        },
    )

    payload = view.build_payload(tmp_path)

    assert payload["summary"]["claim_count"] == 1
    assert payload["summary"]["claims_with_manifest_count"] == 1
    assert payload["summary"]["claims_with_endpoint_evidence_count"] == 1
    row = payload["rows"][0]
    assert row["bundle_ids"] == ["demo_run"]
    assert row["endpoint_result_count"] == 1
    assert row["endpoint_caveat_count"] == 1
    assert row["clean_endpoint_state_count"] == 0


def test_checked_in_evidence_view_has_stackoverflow_model_visible_claim():
    view = load_module()

    payload = view.build_payload(ROOT)
    rows = {row["claim_id"]: row for row in payload["rows"]}

    row = rows["stackoverflow_model_visible_duplicate_sensitivity_pending"]
    assert row["endpoint_result_count"] == 9
    assert row["endpoint_caveat_count"] == 6
    assert row["clean_endpoint_state_count"] == 3
    assert row["bundle_ids"] == [
        "duplicate_cluster_sensitivity_stackoverflow_2025_compensation_log1p_age_model_visible"
    ]
