"""Build a report-surface summary for source-review-only audits."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_source_review_report_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-json", required=True)
    parser.add_argument("--profile-json", default=None)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(
    *,
    audit_payload: dict[str, Any],
    audit_path: Path,
    profile_payload: dict[str, Any] | None,
    profile_path: Path | None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    dataset_id = str(audit_payload["dataset_id"])
    summary = dict(audit_payload.get("summary", {}))
    modeling_approved = bool(summary.get("modeling_approved", False))
    raw_data_downloaded = bool(
        summary.get(
            "raw_data_downloaded",
            audit_payload.get("access_policy", {}).get("raw_data_downloaded", False),
        )
    )
    runner_config_approved = bool(summary.get("runner_config_approved", False))
    status = (
        "source_review_report_modeling_blocked"
        if not modeling_approved
        else "source_review_report_modeling_approved"
    )

    return {
        "schema": SCHEMA,
        "report_id": dataset_id,
        "dataset_id": dataset_id,
        "dataset_ids": [dataset_id],
        "source": audit_payload.get("source"),
        "source_family": audit_payload.get("source_family"),
        "source_url": audit_payload.get("source_url"),
        "audit_path": str(audit_path),
        "profile_path": str(profile_path) if profile_path else None,
        "generated_at_utc": generated_at_utc
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "audit_status": audit_payload.get("audit_status"),
        "metadata_only_review": bool(summary.get("metadata_only_review", True)),
        "modeling_approved": modeling_approved,
        "runner_config_approved": runner_config_approved,
        "raw_data_downloaded": raw_data_downloaded,
        "summary": summary,
        "blockers": list(audit_payload.get("blockers", [])),
        "next_actions": list(audit_payload.get("next_actions", [])),
        "non_claims": list(audit_payload.get("non_claims", [])),
        "access_caveats": list(audit_payload.get("access_caveats", [])),
        "candidate_dataset_policy": audit_payload.get("candidate_dataset_policy", {}),
        "profile_summary": profile_payload or {},
        "claim_boundaries": [
            "This report is a source-review summary, not a model-performance report.",
            "No raw data was downloaded by this report builder.",
            "No runner config, target, group, split, preprocessing, imputation, or conformal method is approved by this report.",
            "The report can support source-discovery accounting only while modeling_approved is false.",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# Source Review Report: {report['dataset_id']}",
        "",
        f"- Schema: `{report['schema']}`",
        f"- Status: `{report['status']}`",
        f"- Audit status: `{report.get('audit_status')}`",
        f"- Source: {report.get('source')}",
        f"- Source family: `{report.get('source_family')}`",
        f"- Source URL: {report.get('source_url')}",
        f"- Audit path: `{report.get('audit_path')}`",
        f"- Profile path: `{report.get('profile_path')}`",
        f"- Metadata-only review: `{report['metadata_only_review']}`",
        f"- Modeling approved: `{report['modeling_approved']}`",
        f"- Runner config approved: `{report['runner_config_approved']}`",
        f"- Raw data downloaded: `{report['raw_data_downloaded']}`",
        "",
        "## Summary",
        "",
    ]
    for key in sorted(summary):
        lines.append(f"- {key}: `{summary[key]}`")
    lines.extend(["", "## Blockers", ""])
    for blocker in report["blockers"]:
        lines.append(f"- {blocker}")
    lines.extend(["", "## Next Actions", ""])
    for action in report["next_actions"]:
        lines.append(f"- {action}")
    lines.extend(["", "## Non-Claims", ""])
    for non_claim in report["non_claims"]:
        lines.append(f"- {non_claim}")
    lines.extend(["", "## Claim Boundaries", ""])
    for boundary in report["claim_boundaries"]:
        lines.append(f"- {boundary}")
    if report["access_caveats"]:
        lines.extend(["", "## Access Caveats", ""])
        for caveat in report["access_caveats"]:
            lines.append(f"- {caveat}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    audit_path = Path(args.audit_json)
    profile_path = Path(args.profile_json) if args.profile_json else None
    out_dir = Path(args.out_dir)
    audit_payload = load_json(audit_path)
    profile_payload = load_json(profile_path) if profile_path else None
    report = build_report(
        audit_payload=audit_payload,
        audit_path=audit_path,
        profile_payload=profile_payload,
        profile_path=profile_path,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_dir / "source_review_report.json", report)
    atomic_write_text(out_dir / "source_review_report.md", render_markdown(report))
    print(json.dumps({"status": "ok", "out_dir": str(out_dir), **report["summary"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
