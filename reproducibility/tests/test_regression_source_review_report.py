import json
from pathlib import Path

from experiments.regression.scripts import build_source_review_report as report


ROOT = Path(__file__).resolve().parents[1]


def audit_payload():
    return {
        "dataset_id": "demo_source_review",
        "source": "Demo source",
        "source_family": "demo_family",
        "source_url": "https://example.org/data",
        "audit_status": "source_review_only_modeling_blocked",
        "summary": {
            "candidate_query_count": 2,
            "metadata_only_review": True,
            "modeling_approved": False,
            "raw_data_downloaded": False,
            "runner_config_approved": False,
        },
        "blockers": ["no dataset selected"],
        "next_actions": ["select a dataset record"],
        "non_claims": ["not model evidence"],
        "access_caveats": ["demo caveat"],
    }


def test_source_review_report_keeps_modeling_blocked():
    payload = report.build_report(
        audit_payload=audit_payload(),
        audit_path=Path("experiments/regression/audits/demo/audit.json"),
        profile_payload={"dataset_record_selected": False},
        profile_path=Path("experiments/regression/audits/demo/profile.json"),
        generated_at_utc="2026-07-04T00:00:00+00:00",
    )

    assert payload["schema"] == report.SCHEMA
    assert payload["dataset_id"] == "demo_source_review"
    assert payload["dataset_ids"] == ["demo_source_review"]
    assert payload["status"] == "source_review_report_modeling_blocked"
    assert payload["modeling_approved"] is False
    assert payload["runner_config_approved"] is False
    assert payload["raw_data_downloaded"] is False
    assert "not a model-performance report" in payload["claim_boundaries"][0]


def test_source_review_report_markdown_preserves_non_claims():
    payload = report.build_report(
        audit_payload=audit_payload(),
        audit_path=Path("experiments/regression/audits/demo/audit.json"),
        profile_payload=None,
        profile_path=None,
        generated_at_utc="2026-07-04T00:00:00+00:00",
    )

    markdown = report.render_markdown(payload)

    assert "Modeling approved: `False`" in markdown
    assert "Runner config approved: `False`" in markdown
    assert "not model evidence" in markdown


def test_source_review_report_cli_writes_json_and_markdown(tmp_path):
    audit_path = tmp_path / "audit.json"
    profile_path = tmp_path / "profile.json"
    out_dir = tmp_path / "report"
    audit_path.write_text(json.dumps(audit_payload()), encoding="utf-8")
    profile_path.write_text(
        json.dumps({"dataset_record_selected": False}),
        encoding="utf-8",
    )

    built = report.build_report(
        audit_payload=json.loads(audit_path.read_text(encoding="utf-8")),
        audit_path=audit_path,
        profile_payload=json.loads(profile_path.read_text(encoding="utf-8")),
        profile_path=profile_path,
        generated_at_utc="2026-07-04T00:00:00+00:00",
    )
    out_dir.mkdir()
    (out_dir / "source_review_report.json").write_text(
        json.dumps(built, sort_keys=True),
        encoding="utf-8",
    )
    (out_dir / "source_review_report.md").write_text(
        report.render_markdown(built),
        encoding="utf-8",
    )

    assert json.loads((out_dir / "source_review_report.json").read_text())[
        "modeling_approved"
    ] is False
    assert "Source Review Report" in (
        out_dir / "source_review_report.md"
    ).read_text(encoding="utf-8")


def test_checked_in_source_review_reports_remain_modeling_blocked():
    report_dirs = [
        "brfss_2024_llcp_source_review",
        "datagov_source_review",
        "icpsr_openicpsr_source_review",
        "ipums_cps_source_review",
        "world_bank_wdi_source_review",
    ]

    for report_dir in report_dirs:
        path = (
            ROOT
            / "experiments/regression/reports"
            / report_dir
            / "source_review_report.json"
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["status"] == "source_review_report_modeling_blocked"
        assert payload["metadata_only_review"] is True
        assert payload["modeling_approved"] is False
        assert payload["runner_config_approved"] is False
        assert payload["raw_data_downloaded"] is False
