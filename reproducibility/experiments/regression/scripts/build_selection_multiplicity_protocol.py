"""Build the manuscript selection and multiplicity protocol.

This artifact defines how a future paper-facing model/method recommendation
must account for ranking scope, multiplicity, tie breaks, and post-selection
validation. It deliberately does not select a winner.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_selection_multiplicity_protocol_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/selection_multiplicity_protocol.json")
MANIFEST_SCHEMA = Path("experiments/regression/catalogs/manuscript_evidence_manifest_schema.json")
PUBLICATION_PROTOCOL = Path("experiments/regression/PUBLICATION_READINESS_PROTOCOL.md")
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
PUBLICATION_METHODOLOGY = REPORT_DIR / "publication_methodology_audit.json"
FINAL_SELECTION = REPORT_DIR / "final_selection_claim_boundary_audit.json"
EVIDENCE_VIEW = Path("experiments/regression/manuscript/evidence_view.json")
BUNDLE_INDEX = Path("experiments/regression/catalogs/manuscript_bundle_index.json")

FIELD_PROTOCOL: dict[str, dict[str, Any]] = {
    "predeclared_operating_criterion": {
        "required_content": [
            "nominal coverage threshold",
            "eligible-row filters",
            "primary ranking metric",
            "failure or no-winner rule",
        ],
        "protocol_text": "Use best interval score only among rows satisfying nominal coverage, endpoint, split, leakage, duplicate, and claim-boundary gates. If no row satisfies the eligibility rule, record no winner and preserve negative evidence.",
    },
    "ranking_scope": {
        "required_content": [
            "dataset id",
            "target and transform",
            "diagnostic group",
            "alpha",
            "model grid",
            "conformal grid",
            "seed set",
        ],
        "protocol_text": "Ranking scope must be declared before extraction as dataset, target, target transform, diagnostic group, alpha, eligible model families/configs, conformal methods, and split seeds.",
    },
    "multiplicity_scope": {
        "required_content": [
            "searched atomic rows",
            "aggregated rows",
            "controlled skips",
            "failures",
            "excluded rows",
        ],
        "protocol_text": "Every recommendation must report the number of searched atomic rows and aggregated candidate rows, including completed, failed, controlled-skip, and excluded rows.",
    },
    "tie_break_rule": {
        "required_content": [
            "deterministic tie order",
            "coverage safety first",
            "width or interval-score tie handling",
        ],
        "protocol_text": "Tie breaks are deterministic: prefer lower absolute coverage error, then lower group coverage gap, then lower median width, then lower mean width, then simpler method family, then lexicographic method/model id.",
    },
    "nominal_coverage_requirement": {
        "required_content": [
            "coverage at or above nominal",
            "alpha-specific nominal target",
            "negative-evidence fallback",
        ],
        "protocol_text": "A row is eligible for winner language only if coverage is at or above the nominal target for its alpha inside the declared aggregation scope. Undercoverage rows can be negative evidence only.",
    },
    "post_selection_claim_boundary": {
        "required_content": [
            "dataset-scoped claim",
            "no fairness/population/legal/production promotion",
            "validation evidence",
        ],
        "protocol_text": "Selection can support only the declared dataset/method benchmark scope. Fairness, population, legal, policy, production, bounded-support, and Venn-Abers validation claims require separate gates.",
    },
    "exploratory_ranking_label": {
        "required_content": [
            "triage label",
            "not final selection",
            "not method superiority",
        ],
        "protocol_text": "Any ranking before all gates pass must be labeled exploratory triage or caveated robustness evidence and must not use final winner or superiority wording.",
    },
    "sensitivity_or_holdout_validation": {
        "required_content": [
            "split or duplicate sensitivity",
            "endpoint validation",
            "post-selection validation",
        ],
        "protocol_text": "Promotion beyond exploratory triage requires sensitivity or holdout evidence appropriate to the selected claim, with endpoint-domain and split/duplicate caveats resolved or explicitly scoped.",
    },
}

ELIGIBILITY_FILTERS = [
    "complete_ledger",
    "zero_unexplained_failures",
    "expected_skips_only",
    "split_controls_pass",
    "feature_leakage_pass",
    "duplicate_controls_pass_or_scoped",
    "endpoint_audit_pass_when_required",
    "dataset_specific_final_gate_pass",
    "claim_register_allows_surface",
    "venn_abers_validation_gate_pass_when_method_claim_requires_it",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_checks(
    manifest_schema: dict[str, Any],
    publication_methodology: dict[str, Any],
    final_selection: dict[str, Any],
    evidence_view: dict[str, Any],
) -> dict[str, bool]:
    required_fields = set(
        str(field)
        for field in manifest_schema.get("selection_multiplicity_evidence_fields", [])
    )
    covered_fields = set(FIELD_PROTOCOL)
    publication_summary = publication_methodology.get("summary") or {}
    final_summary = final_selection.get("summary") or {}
    evidence_rows = evidence_view.get("rows") or []
    main_result_promoted = any(
        isinstance(row, dict)
        and row.get("status") in {"main_result", "final_selection", "winner"}
        for row in evidence_rows
    )
    requirement_statuses = publication_methodology.get("requirement_statuses") or {}
    return {
        "all_manifest_selection_fields_covered": required_fields <= covered_fields,
        "no_extra_unknown_selection_fields": covered_fields <= required_fields,
        "publication_methodology_keeps_final_selection_blocked": publication_summary.get(
            "can_support_final_method_selection"
        )
        is False,
        "final_selection_claim_remains_blocked": final_summary.get("claim_status")
        == "blocked",
        "multiplicity_requirement_still_blocked_until_bundle_record": requirement_statuses.get(
            "multiplicity_selection_record"
        )
        == "blocked",
        "main_result_not_promoted_in_evidence_view": not main_result_promoted,
        "eligibility_filters_declared": len(ELIGIBILITY_FILTERS) >= 8,
        "negative_evidence_rule_declared": "nominal_coverage_requirement" in FIELD_PROTOCOL,
    }


def count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    values = [
        str(row.get(field))
        for row in rows
        if isinstance(row, dict) and row.get(field) not in {None, ""}
    ]
    return dict(sorted(Counter(values).items()))


def bundle_ranking_scope(
    bundle: dict[str, Any],
    final_selection_summary: dict[str, Any],
) -> dict[str, Any]:
    promotion_blockers = [
        str(item)
        for item in bundle.get("promotion_blockers", []) or []
        if str(item).strip()
    ]
    if final_selection_summary.get("claim_status") == "blocked":
        promotion_blockers.append("final_selection_claim_status_blocked")
    return {
        "scope_id": str(bundle.get("bundle_id") or "unknown_bundle"),
        "bundle_id": bundle.get("bundle_id"),
        "dataset_id": bundle.get("dataset_id"),
        "target": bundle.get("target"),
        "target_transform": bundle.get("target_transform"),
        "diagnostic_group": bundle.get("diagnostic_group"),
        "evidence_role": bundle.get("evidence_role"),
        "paper_table_candidate": bundle.get("paper_table_candidate"),
        "status": bundle.get("status"),
        "manifest_path": bundle.get("manifest_path"),
        "claim_scope": bundle.get("claim_scope"),
        "promotion_blocker_count": len(promotion_blockers),
        "promotion_blockers": promotion_blockers,
        "final_selection_eligible": False,
        "selection_record_status": "blocked_until_dataset_specific_final_gates_pass",
    }


def build_manifest_coverage(
    bundle_rows: list[dict[str, Any]],
    evidence_view: dict[str, Any],
) -> dict[str, Any]:
    evidence_rows = [
        row for row in evidence_view.get("rows", []) or [] if isinstance(row, dict)
    ]
    linked_bundle_ids: set[str] = set()
    for row in evidence_rows:
        linked_bundle_ids.update(
            str(bundle_id)
            for bundle_id in row.get("bundle_ids", []) or []
            if str(bundle_id).strip()
        )
    indexed_bundle_ids = {
        str(bundle.get("bundle_id"))
        for bundle in bundle_rows
        if str(bundle.get("bundle_id") or "").strip()
    }
    linked_indexed_bundle_ids = indexed_bundle_ids & linked_bundle_ids
    manifest_paths = [
        str(bundle.get("manifest_path"))
        for bundle in bundle_rows
        if str(bundle.get("manifest_path") or "").strip()
    ]
    evidence_summary = evidence_view.get("summary") or {}
    return {
        "indexed_bundle_count": len(bundle_rows),
        "indexed_manifest_path_count": len(manifest_paths),
        "evidence_claim_count": len(evidence_rows),
        "claims_with_manifest_count": int(
            evidence_summary.get("claims_with_manifest_count") or 0
        ),
        "linked_indexed_bundle_count": len(linked_indexed_bundle_ids),
        "unlinked_indexed_bundle_count": len(indexed_bundle_ids - linked_bundle_ids),
        "linked_indexed_bundle_ids": sorted(linked_indexed_bundle_ids),
        "unlinked_indexed_bundle_ids": sorted(indexed_bundle_ids - linked_bundle_ids),
        "bundle_status_counts": count_by(bundle_rows, "status"),
        "evidence_role_counts": count_by(bundle_rows, "evidence_role"),
        "paper_table_candidate_counts": count_by(bundle_rows, "paper_table_candidate"),
    }


def build_observed_multiplicity_scope(
    bundle_rows: list[dict[str, Any]],
    publication_methodology: dict[str, Any],
    evidence_view: dict[str, Any],
) -> dict[str, Any]:
    publication_summary = publication_methodology.get("summary") or {}
    evidence_summary = evidence_view.get("summary") or {}
    return {
        "scope_status": "observed_scope_recorded_no_final_selection",
        "completed_ledger_rows_scanned": int(
            publication_summary.get("total_completed_rows") or 0
        ),
        "reports_scanned": int(publication_summary.get("reports_scanned") or 0),
        "configs_scanned": int(publication_summary.get("configs_scanned") or 0),
        "manifested_bundle_count": len(bundle_rows),
        "unique_dataset_count": len(
            {bundle.get("dataset_id") for bundle in bundle_rows if bundle.get("dataset_id")}
        ),
        "unique_target_count": len(
            {bundle.get("target") for bundle in bundle_rows if bundle.get("target")}
        ),
        "diagnostic_group_count": len(
            {
                bundle.get("diagnostic_group")
                for bundle in bundle_rows
                if bundle.get("diagnostic_group")
            }
        ),
        "claim_count": int(evidence_summary.get("claim_count") or 0),
        "endpoint_result_count": int(evidence_summary.get("endpoint_result_count") or 0),
        "endpoint_caveat_count": int(evidence_summary.get("endpoint_caveat_count") or 0),
        "claim_status_counts": dict(
            sorted((evidence_summary.get("status_counts") or {}).items())
        ),
        "current_selection_allowed": False,
    }


def build_selection_records(
    publication_methodology: dict[str, Any],
    final_selection: dict[str, Any],
    ranking_scope_count: int,
) -> list[dict[str, Any]]:
    publication_summary = publication_methodology.get("summary") or {}
    final_summary = final_selection.get("summary") or {}
    return [
        {
            "record_id": "current_no_winner_record",
            "status": "blocked_no_final_selection",
            "ranking_scope_count": ranking_scope_count,
            "searched_completed_ledger_rows": int(
                publication_summary.get("total_completed_rows") or 0
            ),
            "can_support_final_method_selection": bool(
                publication_summary.get("can_support_final_method_selection")
            ),
            "final_selection_claim_status": final_summary.get("claim_status"),
            "no_winner_rule_applied": True,
            "reason": "Dataset-specific final gates, multiplicity record, endpoint bounded-support, fairness/population, and Venn-Abers validation gates remain blocked.",
        }
    ]


def build_payload(root: Path) -> dict[str, Any]:
    out_sources = {
        "manifest_schema": root / MANIFEST_SCHEMA,
        "publication_protocol": root / PUBLICATION_PROTOCOL,
        "publication_methodology": root / PUBLICATION_METHODOLOGY,
        "final_selection_claim_boundary": root / FINAL_SELECTION,
        "manuscript_evidence_view": root / EVIDENCE_VIEW,
        "manuscript_bundle_index": root / BUNDLE_INDEX,
    }
    manifest_schema = read_json(out_sources["manifest_schema"])
    publication_methodology = read_json(out_sources["publication_methodology"])
    final_selection = read_json(out_sources["final_selection_claim_boundary"])
    evidence_view = read_json(out_sources["manuscript_evidence_view"])
    bundle_index = read_json(out_sources["manuscript_bundle_index"])
    checks = build_checks(
        manifest_schema,
        publication_methodology,
        final_selection,
        evidence_view,
    )
    failed_checks = [key for key, value in checks.items() if not value]
    required_fields = list(
        manifest_schema.get("selection_multiplicity_evidence_fields", []) or []
    )
    bundle_summary = bundle_index.get("bundle_summary") or {}
    bundle_rows = [
        row for row in bundle_index.get("bundles", []) or [] if isinstance(row, dict)
    ]
    final_summary = final_selection.get("summary") or {}
    ranking_scopes = [
        bundle_ranking_scope(bundle, final_summary) for bundle in bundle_rows
    ]
    manifest_coverage = build_manifest_coverage(bundle_rows, evidence_view)
    observed_multiplicity_scope = build_observed_multiplicity_scope(
        bundle_rows,
        publication_methodology,
        evidence_view,
    )
    selection_records = build_selection_records(
        publication_methodology,
        final_selection,
        len(ranking_scopes),
    )
    overall_status = (
        "selection_multiplicity_protocol_defined_no_final_selection"
        if not failed_checks
        else "selection_multiplicity_protocol_incomplete"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {key: rel(path, root) for key, path in out_sources.items()},
        "summary": {
            "overall_status": overall_status,
            "required_manifest_field_count": len(required_fields),
            "covered_manifest_field_count": len(FIELD_PROTOCOL),
            "failed_check_count": len(failed_checks),
            "eligibility_filter_count": len(ELIGIBILITY_FILTERS),
            "manifested_bundle_count": int(
                bundle_summary.get("manifest_count")
                or len(bundle_rows)
            ),
            "ranking_scope_count": len(ranking_scopes),
            "selection_record_count": len(selection_records),
            "linked_indexed_bundle_count": manifest_coverage[
                "linked_indexed_bundle_count"
            ],
            "unlinked_indexed_bundle_count": manifest_coverage[
                "unlinked_indexed_bundle_count"
            ],
            "completed_ledger_rows_scanned": observed_multiplicity_scope[
                "completed_ledger_rows_scanned"
            ],
            "can_support_final_method_selection": False,
            "final_selection_claim_status": final_summary.get("claim_status"),
        },
        "claim_boundaries": [
            "This protocol defines how future selection records must be written; it does not select a final method or model.",
            "Best/winner language remains blocked until dataset-specific final gates and manifest-level multiplicity records pass.",
            "Undercoverage rows can be reported as negative evidence only, not as recommended conformal methods.",
        ],
        "checks": checks,
        "failed_checks": failed_checks,
        "required_manifest_fields": required_fields,
        "field_protocol": FIELD_PROTOCOL,
        "eligibility_filters": ELIGIBILITY_FILTERS,
        "ranking_contract": {
            "primary_rule": "best interval score among eligible nominal-or-above rows",
            "coverage_guard": "coverage must be at or above nominal for the declared alpha and aggregation scope",
            "group_guard": "group coverage gap must be reported and can veto winner language when material or unstable",
            "no_winner_rule": "if no eligible row exists, report no winner and preserve negative evidence",
        },
        "multiplicity_contract": {
            "must_count": [
                "dataset_count",
                "target_count",
                "model_family_count",
                "model_config_count",
                "conformal_method_count",
                "conformal_config_count",
                "seed_count",
                "atomic_row_count",
                "aggregated_candidate_count",
                "controlled_skip_count",
                "failure_count",
                "excluded_row_count",
            ],
            "must_disclose": [
                "predeclared ranking scope",
                "post-hoc exclusions",
                "controlled runtime skips",
                "sensitivity or holdout validation scope",
                "claim surface allowed by the claim register",
            ],
        },
        "observed_multiplicity_scope": observed_multiplicity_scope,
        "ranking_scopes": ranking_scopes,
        "selection_records": selection_records,
        "manifest_coverage": manifest_coverage,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Selection And Multiplicity Protocol",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Required manifest fields covered: {summary['covered_manifest_field_count']} / {summary['required_manifest_field_count']}",
        f"- Eligibility filters: {summary['eligibility_filter_count']}",
        f"- Manifested bundles in current index: {summary['manifested_bundle_count']}",
        f"- Observed ranking scopes: {summary['ranking_scope_count']}",
        f"- Selection records: {summary['selection_record_count']}",
        f"- Linked indexed bundles: {summary['linked_indexed_bundle_count']}",
        f"- Unlinked indexed bundles: {summary['unlinked_indexed_bundle_count']}",
        f"- Completed ledger rows scanned: {summary['completed_ledger_rows_scanned']}",
        f"- Can support final method selection now: `{summary['can_support_final_method_selection']}`",
        f"- Final-selection claim status: `{summary['final_selection_claim_status']}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Manifest Field Protocol",
            "",
            "| Field | Protocol | Required content |",
            "| --- | --- | --- |",
        ]
    )
    for field, spec in payload["field_protocol"].items():
        lines.append(
            "| "
            f"`{field}` | "
            f"{spec['protocol_text']} | "
            f"{', '.join(spec['required_content'])} |"
        )
    lines.extend(
        [
            "",
            "## Eligibility Filters",
            "",
        ]
    )
    lines.extend(f"- `{item}`" for item in payload["eligibility_filters"])
    lines.extend(
        [
            "",
            "## Ranking Contract",
            "",
        ]
    )
    for key, value in payload["ranking_contract"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Multiplicity Contract",
            "",
            "Must count:",
        ]
    )
    lines.extend(f"- `{item}`" for item in payload["multiplicity_contract"]["must_count"])
    lines.append("")
    lines.append("Must disclose:")
    lines.extend(
        f"- `{item}`" for item in payload["multiplicity_contract"]["must_disclose"]
    )
    observed_scope = payload["observed_multiplicity_scope"]
    lines.extend(
        [
            "",
            "## Observed Multiplicity Scope",
            "",
            f"- Scope status: `{observed_scope['scope_status']}`",
            f"- Completed ledger rows scanned: {observed_scope['completed_ledger_rows_scanned']}",
            f"- Reports scanned: {observed_scope['reports_scanned']}",
            f"- Configs scanned: {observed_scope['configs_scanned']}",
            f"- Manifested bundles: {observed_scope['manifested_bundle_count']}",
            f"- Unique datasets: {observed_scope['unique_dataset_count']}",
            f"- Unique targets: {observed_scope['unique_target_count']}",
            f"- Diagnostic groups: {observed_scope['diagnostic_group_count']}",
            f"- Current selection allowed: `{observed_scope['current_selection_allowed']}`",
            "",
            "Claim status counts:",
        ]
    )
    lines.extend(
        f"- `{key}`: {value}"
        for key, value in observed_scope["claim_status_counts"].items()
    )
    lines.extend(
        [
            "",
            "## Ranking Scopes",
            "",
            "| Scope | Dataset | Target | Transform | Group | Role | Candidate table | Status | Blockers |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for scope in payload["ranking_scopes"]:
        lines.append(
            "| "
            f"`{scope['scope_id']}` | "
            f"`{scope.get('dataset_id')}` | "
            f"`{scope.get('target')}` | "
            f"`{scope.get('target_transform')}` | "
            f"`{scope.get('diagnostic_group')}` | "
            f"`{scope.get('evidence_role')}` | "
            f"`{scope.get('paper_table_candidate')}` | "
            f"`{scope.get('status')}` | "
            f"{scope['promotion_blocker_count']} |"
        )
    manifest_coverage = payload["manifest_coverage"]
    lines.extend(
        [
            "",
            "## Manifest Coverage",
            "",
            f"- Indexed bundles: {manifest_coverage['indexed_bundle_count']}",
            f"- Indexed manifest paths: {manifest_coverage['indexed_manifest_path_count']}",
            f"- Evidence claims: {manifest_coverage['evidence_claim_count']}",
            f"- Claims with manifest evidence: {manifest_coverage['claims_with_manifest_count']}",
            f"- Linked indexed bundles: {manifest_coverage['linked_indexed_bundle_count']}",
            f"- Unlinked indexed bundles: {manifest_coverage['unlinked_indexed_bundle_count']}",
            "",
            "Bundle status counts:",
        ]
    )
    lines.extend(
        f"- `{key}`: {value}"
        for key, value in manifest_coverage["bundle_status_counts"].items()
    )
    lines.extend(
        [
            "",
            "## Selection Records",
            "",
            "| Record | Status | Ranking scopes | Searched rows | Final claim | No-winner rule |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for record in payload["selection_records"]:
        lines.append(
            "| "
            f"`{record['record_id']}` | "
            f"`{record['status']}` | "
            f"{record['ranking_scope_count']} | "
            f"{record['searched_completed_ledger_rows']} | "
            f"`{record['final_selection_claim_status']}` | "
            f"`{record['no_winner_rule_applied']}` |"
        )
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status |",
            "| --- | --- |",
        ]
    )
    for key, value in payload["checks"].items():
        lines.append(f"| `{key}` | `{'pass' if value else 'fail'}` |")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = resolve(root, args.out)
    payload = build_payload(root)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok" if not payload["failed_checks"] else "fail",
                "out": rel(out_path, root),
                **payload["summary"],
            },
            sort_keys=True,
        )
    )
    return 1 if payload["failed_checks"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
