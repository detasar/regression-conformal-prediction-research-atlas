import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments/regression/scripts/audit_neutral_reporting_language.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "audit_neutral_reporting_language", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_minimal_sources(root: Path) -> None:
    report_dir = (
        root / "experiments/regression/reports/methodology_sanity_audit_20260627"
    )
    manuscript_dir = root / "experiments/regression/manuscript"
    catalog_dir = root / "experiments/regression/catalogs"
    write_json(
        manuscript_dir / "paper_gate_closure_map.json",
        {
            "summary": {
                "gate_count": 2,
                "positive_claim_ready_gate_count": 0,
                "scoped_or_negative_path_ready_gate_count": 2,
                "disallowed_language_item_count": 3,
            }
        },
    )
    write_json(
        manuscript_dir / "post_experiment_publication_activation_audit.json",
        {
            "summary": {
                "overall_status": "post_experiment_publication_activation_blocked",
                "publication_phase_start_authorized": False,
                "positive_claim_ready_gate_count": 0,
                "final_result_disposition_gate_count": 2,
            },
            "activation_checks": [
                {"check_id": "final_result_dispositions_available", "status": "pass"}
            ],
        },
    )
    write_json(
        report_dir / "publication_methodology_audit.json",
        {
            "summary": {
                "unsupported_claim_hits": 0,
                "can_support_final_method_selection": False,
                "can_support_publication_ready_fairness": False,
                "can_support_bounded_support_validity": False,
                "can_support_venn_abers_regression_validation": False,
            }
        },
    )
    write_json(
        report_dir / "scientific_review_finding_register.json",
        {
            "summary": {
                "open_blocker_count": 0,
                "hard_open_blocker_count": 0,
                "tracked_caveat_count": 1,
            }
        },
    )
    (catalog_dir / "guarded_claims.md").parent.mkdir(parents=True, exist_ok=True)
    (catalog_dir / "guarded_claims.md").write_text(
        "\n".join(
            [
                "No final winner claim is made.",
                "No protected-class fairness claim is made.",
                "Validated Venn-Abers language remains blocked and diagnostic.",
                "Final method selection remains closed.",
                "This prevents a metric from being mistaken for a Venn-Abers validation claim.",
            ]
        ),
        encoding="utf-8",
    )


def test_minimal_guarded_neutral_reporting_sources_pass(tmp_path):
    audit = load_module()
    write_minimal_sources(tmp_path)

    payload = audit.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "neutral_reporting_language_audit_pass"
    assert payload["summary"]["unguarded_hit_count"] == 0
    assert payload["failed_checks"] == []


def test_unguarded_method_promotion_language_fails(tmp_path):
    audit = load_module()
    write_minimal_sources(tmp_path)
    claim_path = tmp_path / "experiments/regression/manuscript/unguarded_claim.md"
    claim_path.write_text(
        "CQR is the best method and the final winner for regression conformal prediction.",
        encoding="utf-8",
    )

    payload = audit.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "neutral_reporting_language_audit_fail"
    assert payload["summary"]["unguarded_hit_count"] >= 1
    assert "no_unguarded_promotional_language" in payload["failed_checks"]


def test_checked_in_neutral_reporting_language_audit_passes():
    audit = load_module()

    payload = audit.build_payload(ROOT)

    assert payload["summary"]["overall_status"] == "neutral_reporting_language_audit_pass"
    assert payload["summary"]["unguarded_hit_count"] == 0
    assert payload["summary"]["failed_check_count"] == 0
