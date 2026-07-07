import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = (
    ROOT
    / "experiments/regression/scripts/audit_manuscript_claim_register_consistency.py"
)


def load_audit_module():
    spec = importlib.util.spec_from_file_location(
        "audit_manuscript_claim_register_consistency", AUDIT_SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_claim_register(root: Path, *, json_req_status: str, md_req_status: str) -> None:
    catalog = root / "experiments/regression/catalogs"
    catalog.mkdir(parents=True, exist_ok=True)
    (catalog / "manuscript_claim_register.json").write_text(
        json.dumps(
            {
                "schema": "test",
                "claims": [
                    {
                        "claim_id": "demo_claim",
                        "status": "robustness_evidence_gate_passed_with_caveats",
                        "requirements": [
                            {
                                "requirement_id": "methodology_gate_refresh",
                                "status": json_req_status,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (catalog / "manuscript_claim_register.md").write_text(
        f"""# Claim Register

## Claim: demo_claim

Status: `robustness_evidence_gate_passed_with_caveats`

Requirements:

- `methodology_gate_refresh`: {md_req_status}.
""",
        encoding="utf-8",
    )


def test_claim_register_consistency_passes_when_statuses_match(tmp_path):
    audit = load_audit_module()
    write_claim_register(
        tmp_path,
        json_req_status="pass_with_caveats",
        md_req_status="pass_with_caveats",
    )

    payload = audit.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "pass"
    assert payload["rows"][0]["requirement_mismatches"] == []


def test_claim_register_consistency_fails_on_requirement_status_mismatch(tmp_path):
    audit = load_audit_module()
    write_claim_register(
        tmp_path,
        json_req_status="pending_post_documentation_refresh",
        md_req_status="pass_with_caveats",
    )

    payload = audit.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "fail"
    assert payload["rows"][0]["requirement_mismatches"] == [
        {
            "requirement_id": "methodology_gate_refresh",
            "json": "pending_post_documentation_refresh",
            "markdown": "pass_with_caveats",
        }
    ]


def test_checked_in_claim_register_views_are_synchronized():
    audit = load_audit_module()

    payload = audit.build_payload(ROOT)

    assert payload["summary"]["overall_status"] == "pass"
    assert payload["summary"]["claim_count"] >= 10
