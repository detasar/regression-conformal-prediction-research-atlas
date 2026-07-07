import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "experiments/regression/scripts/audit_final_selection_claim_boundary.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "audit_final_selection_claim_boundary", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_minimal_sources(root: Path, *, stale_backlog_blocker: bool = False) -> None:
    report_dir = root / "experiments/regression/reports/methodology_sanity_audit_20260627"
    catalog_dir = root / "experiments/regression/catalogs"
    claim = {
        "claim_id": "final_selection_and_fairness_claims_blocked",
        "status": "blocked",
        "claim_text": (
            "Choosing a final conformal method/model, publication-ready "
            "fairness conclusions, population inference, legal/policy "
            "guidance, production readiness, bounded-support validity, and "
            "Venn-Abers regression validation claims are blocked."
        ),
        "blocking_node_ids": ["report:integrity_remediation_backlog"]
        if stale_backlog_blocker
        else ["report:retrospective_methodology_controls"],
        "not_claiming": [
            (
                "No final method/model selection, fairness, population, legal, "
                "policy, production, bounded-support, or Venn-Abers validation "
                "claim is made."
            )
        ],
        "requirements": [
            {
                "requirement_id": "remediation_backlog_closed_or_scoped",
                "status": "blocked" if stale_backlog_blocker else "pass",
            },
            {"requirement_id": "final_method_model_selection_gate", "status": "blocked"},
            {"requirement_id": "multiplicity_selection_record", "status": "blocked"},
            {"requirement_id": "dataset_specific_final_gates", "status": "blocked"},
            {"requirement_id": "endpoint_bounded_support_gate", "status": "blocked"},
            {"requirement_id": "fairness_population_inference_gate", "status": "blocked"},
            {
                "requirement_id": "venn_abers_regression_validation_gate",
                "status": "blocked",
            },
        ],
    }
    if stale_backlog_blocker:
        claim["requirements"].append(
            {
                "requirement_id": "all_backlog_actions_closed_or_scoped",
                "status": "blocked",
            }
        )
    write_json(catalog_dir / "manuscript_claim_register.json", {"claims": [claim]})
    (catalog_dir / "manuscript_claim_register.md").write_text(
        """
# Claim Register

## Claim: final_selection_and_fairness_claims_blocked

Status: `blocked`

Requirements:

- `remediation_backlog_closed_or_scoped`: pass.
- `final_method_model_selection_gate`: blocked.
- `multiplicity_selection_record`: blocked.
- `dataset_specific_final_gates`: blocked.
- `endpoint_bounded_support_gate`: blocked.
- `fairness_population_inference_gate`: blocked.
- `venn_abers_regression_validation_gate`: blocked.
""",
        encoding="utf-8",
    )
    (root / "experiments/regression/PUBLICATION_READINESS_PROTOCOL.md").parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    (root / "experiments/regression/PUBLICATION_READINESS_PROTOCOL.md").write_text(
        """
## Model Selection And Multiplicity

The record must state the predeclared operating criterion, multiplicity scope,
and post-selection claim boundary.
""",
        encoding="utf-8",
    )
    write_json(
        report_dir / "integrity_remediation_backlog.json",
        {"summary": {"open_action_count": 0}},
    )
    write_json(
        report_dir / "retrospective_methodology_controls.json",
        {"summary": {"control_status_counts": {"pass": 9, "caveat": 1}}},
    )
    write_json(
        report_dir / "manuscript_manifest_completeness_audit.json",
        {"summary": {"overall_status": "pass", "bundle_index_status": "pass"}},
    )


def test_checked_in_final_selection_claim_boundary_passes():
    audit = load_module()

    payload = audit.build_payload(ROOT)

    assert payload["summary"]["overall_status"] == "pass"
    assert payload["summary"]["open_remediation_actions"] == 0
    assert payload["summary"]["blocked_requirement_count"] >= 6
    assert payload["failed_checks"] == []


def test_closed_backlog_cannot_remain_the_blocked_reason(tmp_path):
    audit = load_module()
    write_minimal_sources(tmp_path, stale_backlog_blocker=True)

    payload = audit.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "fail"
    assert "no_stale_backlog_blocker_when_backlog_closed" in payload["failed_checks"]
    assert "remediation_backlog_closed_or_scoped_current" in payload["failed_checks"]
