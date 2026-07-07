import json
from pathlib import Path

from experiments.regression.scripts import build_external_source_discovery_watchlist as watchlist


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_minimal_watchlist_repo(root, *, openml_rows=True):
    for family in watchlist.SOURCE_FAMILIES:
        if family.secondary:
            continue
        prefix = family.audit_prefixes[0] if family.audit_prefixes else family.source_id
        (root / watchlist.AUDITS_DIR / f"{prefix}demo").mkdir(parents=True, exist_ok=True)
        token = family.report_tokens[0] if family.report_tokens else family.source_id
        (root / watchlist.REPORTS_DIR / f"model_family_sweep_{token}demo").mkdir(
            parents=True,
            exist_ok=True,
        )
    write_text(
        root / watchlist.SOURCE_REGISTRY,
        "OpenML UCI Fairlearn Folktables AIF360 NHANES MEPS HMDA "
        "College Scorecard SCF PISA StackOverflow OULAD Data.gov",
    )
    write_jsonl(
        root / watchlist.OPENML_DISCOVERY,
        [{"openml_id": 1}, {"openml_id": 2}] if openml_rows else [],
    )
    write_jsonl(root / watchlist.OPENML_RANKED, [{"openml_id": 1}])
    write_jsonl(root / watchlist.DATASET_CANDIDATES, [{"dataset_id": "demo"}])


def test_external_source_discovery_watchlist_summarizes_source_families(tmp_path):
    write_minimal_watchlist_repo(tmp_path)

    payload = watchlist.build_payload(tmp_path)
    primary_count = sum(not family.secondary for family in watchlist.SOURCE_FAMILIES)
    secondary_count = sum(family.secondary for family in watchlist.SOURCE_FAMILIES)

    assert (
        payload["summary"]["overall_status"]
        == "external_source_discovery_watchlist_ready_with_gaps"
    )
    assert payload["summary"]["source_family_count"] == len(watchlist.SOURCE_FAMILIES)
    assert payload["summary"]["primary_source_family_count"] == primary_count
    assert payload["summary"]["secondary_source_family_count"] == secondary_count
    assert payload["summary"]["local_audited_family_count"] == primary_count
    assert payload["summary"]["pending_primary_family_count"] == 0
    assert payload["summary"]["openml_discovery_rows"] == 2
    assert payload["summary"]["openml_ranked_rows"] == 1
    assert payload["summary"]["dataset_candidate_rows"] == 1
    kaggle = next(row for row in payload["rows"] if row["source_id"] == "kaggle_secondary")
    assert kaggle["repo_status"] == "secondary_discovery_deferred"
    assert kaggle["secondary_source"] is True
    assert payload["failed_checks"] == []


def test_external_source_discovery_watchlist_flags_missing_openml_rows(tmp_path):
    write_minimal_watchlist_repo(tmp_path, openml_rows=False)

    payload = watchlist.build_payload(tmp_path)

    assert (
        payload["summary"]["overall_status"]
        == "external_source_discovery_watchlist_review_required"
    )
    assert payload["summary"]["failed_check_count"] == 1
    assert {
        check["check_id"] for check in payload["failed_checks"]
    } == {"openml_discovery_rows_present"}


def test_checked_in_external_source_discovery_watchlist_has_current_scope():
    payload = watchlist.build_payload(Path(__file__).resolve().parents[1])

    assert (
        payload["summary"]["overall_status"]
        == "external_source_discovery_watchlist_ready_with_gaps"
    )
    assert payload["summary"]["source_family_count"] >= 14
    assert payload["summary"]["primary_source_family_count"] >= 13
    assert payload["summary"]["local_audited_family_count"] >= 17
    assert payload["summary"]["pending_primary_family_count"] == 0
    assert payload["summary"]["openml_discovery_rows"] >= 600
    assert payload["summary"]["openml_ranked_rows"] >= 50
    assert payload["summary"]["failed_check_count"] == 0
    pending_ids = {
        row["source_id"]
        for row in payload["rows"]
        if row["repo_status"] == "watchlist_pending_manual_review"
    }
    assert "icpsr_openicpsr" not in pending_ids
    brfss = next(row for row in payload["rows"] if row["source_id"] == "cdc_brfss")
    assert brfss["repo_status"] == "implemented_with_audits_and_reports"
    assert brfss["covered_by_local_audit"] is True
    assert brfss["covered_by_local_report"] is True
    wdi = next(row for row in payload["rows"] if row["source_id"] == "world_bank_wdi")
    assert wdi["repo_status"] == "implemented_with_audits_and_reports"
    assert wdi["covered_by_local_audit"] is True
    assert wdi["covered_by_local_report"] is True
    ipums = next(row for row in payload["rows"] if row["source_id"] == "ipums_cps")
    assert ipums["repo_status"] == "implemented_with_audits_and_reports"
    assert ipums["covered_by_local_audit"] is True
    assert ipums["covered_by_local_report"] is True
    icpsr = next(
        row for row in payload["rows"] if row["source_id"] == "icpsr_openicpsr"
    )
    assert icpsr["repo_status"] == "implemented_with_audits_and_reports"
    assert icpsr["covered_by_local_audit"] is True
    assert icpsr["covered_by_local_report"] is True
    fairlearn = next(row for row in payload["rows"] if row["source_id"] == "fairlearn")
    assert fairlearn["repo_status"] == "implemented_with_audits_and_reports"
    assert fairlearn["covered_by_local_audit"] is True
    assert fairlearn["covered_by_local_report"] is True
    datagov = next(row for row in payload["rows"] if row["source_id"] == "datagov")
    assert datagov["repo_status"] == "implemented_with_audits_and_reports"
    assert datagov["covered_by_local_audit"] is True
    assert datagov["covered_by_local_report"] is True
