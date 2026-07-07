"""Audit neutral reporting language for regression CP publication artifacts.

This audit checks whether method-promotion and positive-claim phrases are
guarded by explicit blocked, diagnostic, negative, scoped, no-claim, or
future-work language. It is a publication-methodology control, not a manuscript
draft and not a new model-performance result.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_neutral_reporting_language_audit_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = REPORT_DIR / "neutral_reporting_language_audit.json"

PAPER_GATE_CLOSURE_MAP = Path(
    "experiments/regression/manuscript/paper_gate_closure_map.json"
)
POST_EXPERIMENT_PUBLICATION_ACTIVATION = Path(
    "experiments/regression/manuscript/post_experiment_publication_activation_audit.json"
)
PUBLICATION_METHODOLOGY_AUDIT = REPORT_DIR / "publication_methodology_audit.json"
SCIENTIFIC_REVIEW_FINDING_REGISTER = (
    REPORT_DIR / "scientific_review_finding_register.json"
)

SCAN_ROOTS = (
    Path("experiments/regression/manuscript"),
    Path("experiments/regression/reports/methodology_sanity_audit_20260627"),
    Path("experiments/regression/catalogs"),
)
SCAN_SUFFIXES = {".json", ".md"}
EXCLUDED_FILENAMES = {
    "knowledge_graph.json",
    "neutral_reporting_language_audit.json",
    "neutral_reporting_language_audit.md",
}
MAX_SAMPLE_COUNT = 12
CONTEXT_CHARS = 220

GUARD_TOKENS = (
    "blocked",
    "blocker",
    "no-",
    "no_",
    "does not",
    "do not",
    "must not",
    "cannot",
    "can not",
    "disallow",
    "disallowed",
    "prohibit",
    "prohibited",
    "forbid",
    "forbidden",
    "diagnostic",
    "negative",
    "no-claim",
    "no claim",
    "scoped",
    "caveat",
    "claim boundary",
    "claim-boundary",
    "remains gated",
    "remain gated",
    "still require",
    "requires",
    "requirement",
    "only after",
    "until",
    "before any",
    "future work",
    "future confirmatory",
    "deferred",
    "out of scope",
    "overstate",
    "not_claiming",
    "not claiming",
    "paper_risk",
    "acceptance_criteria",
    "claim is made",
    "claim is promoted",
    "claim register",
    "design or cite",
    "protocol_design_complete",
    "contract",
    "promoted",
    "false",
    "zero",
    " 0 ",
    ": 0",
    "0/",
    "fit for paper evidence navigation",
)

GUARD_REGEXES = (
    re.compile(r"\bno\b", re.IGNORECASE),
    re.compile(r"\bnot\b", re.IGNORECASE),
    re.compile(r"\bwithout\b", re.IGNORECASE),
    re.compile(r"\bmust\s+remain\b", re.IGNORECASE),
    re.compile(r"\b(?:remain|remains|is|are|stay|stays)\s+closed\b", re.IGNORECASE),
    re.compile(r"\bmistaken\s+for\b", re.IGNORECASE),
)

TERM_SPECS = (
    {
        "term_id": "final_winner_language",
        "family": "final_selection",
        "pattern": r"\bfinal winner\b|\bwinner language\b|\bmethod/model winner\b",
    },
    {
        "term_id": "best_method_language",
        "family": "final_selection",
        "pattern": r"\bbest method\b|\bbest model\b|\bbest conformal\b",
    },
    {
        "term_id": "validated_venn_abers_language",
        "family": "venn_abers",
        "pattern": r"\bvalidated venn[- ]abers\b|\bvenn[- ]abers validation claim\b|\bvalidated regression venn[- ]abers\b",
    },
    {
        "term_id": "bounded_support_validity_language",
        "family": "bounded_support",
        "pattern": r"\bbounded[- ]support validity\b|\bbounded[- ]support language\b",
    },
    {
        "term_id": "fairness_claim_language",
        "family": "fairness",
        "pattern": r"\bpublication[- ]ready fairness\b|\bpopulation fairness\b|\bprotected[- ]class fairness\b|\bfairness claim\b",
    },
    {
        "term_id": "final_selection_language",
        "family": "final_selection",
        "pattern": r"\bfinal method/model selection\b|\bfinal model selection\b|\bfinal method selection\b",
    },
    {
        "term_id": "production_language",
        "family": "deployment",
        "pattern": r"\bproduction ready\b|\bproduction readiness\b|\bproduction evidence\b",
    },
    {
        "term_id": "superiority_recommendation_language",
        "family": "final_selection",
        "pattern": r"\bsuperiority\b|\brecommendation language\b|\bfinal recommendation\b",
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    return parser.parse_args()


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_json_if_present(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def summary(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("summary") or {}


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def iter_scan_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for scan_root in SCAN_ROOTS:
        absolute_root = root / scan_root
        if not absolute_root.exists():
            continue
        for path in absolute_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SCAN_SUFFIXES:
                continue
            if path.name in EXCLUDED_FILENAMES:
                continue
            files.append(path)
    return sorted(files)


def normalize_context(text: str) -> str:
    return " ".join(text.replace("\x00", " ").split())


def context_for(text: str, start: int, end: int) -> str:
    left = max(0, start - CONTEXT_CHARS)
    right = min(len(text), end + CONTEXT_CHARS)
    return normalize_context(text[left:right])


def context_is_guarded(context: str) -> bool:
    folded = f" {context.lower()} "
    return any(token in folded for token in GUARD_TOKENS) or any(
        regex.search(context) for regex in GUARD_REGEXES
    )


def scan_language(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    pattern_rows: list[dict[str, Any]] = []
    unguarded_hits: list[dict[str, Any]] = []
    family_counts: Counter[str] = Counter()
    files = iter_scan_files(root)
    for spec in TERM_SPECS:
        regex = re.compile(str(spec["pattern"]), re.IGNORECASE)
        guarded_count = 0
        unguarded_count = 0
        total_count = 0
        guarded_samples: list[dict[str, Any]] = []
        unguarded_samples: list[dict[str, Any]] = []
        for path in files:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in regex.finditer(text):
                total_count += 1
                context = context_for(text, match.start(), match.end())
                hit = {
                    "term_id": spec["term_id"],
                    "family": spec["family"],
                    "path": rel(path, root),
                    "matched_text": match.group(0),
                    "context": context,
                }
                if context_is_guarded(context):
                    guarded_count += 1
                    if len(guarded_samples) < MAX_SAMPLE_COUNT:
                        guarded_samples.append(hit)
                else:
                    unguarded_count += 1
                    family_counts[str(spec["family"])] += 1
                    if len(unguarded_samples) < MAX_SAMPLE_COUNT:
                        unguarded_samples.append(hit)
                    if len(unguarded_hits) < MAX_SAMPLE_COUNT:
                        unguarded_hits.append(hit)
        pattern_rows.append(
            {
                "term_id": spec["term_id"],
                "family": spec["family"],
                "pattern": spec["pattern"],
                "total_hit_count": total_count,
                "guarded_hit_count": guarded_count,
                "unguarded_hit_count": unguarded_count,
                "status": "pass" if unguarded_count == 0 else "fail",
                "guarded_samples": guarded_samples,
                "unguarded_samples": unguarded_samples,
            }
        )
    return pattern_rows, unguarded_hits, dict(sorted(family_counts.items()))


def check_row(
    check_id: str,
    status: str,
    evidence: dict[str, Any],
    source_artifacts: list[str],
    blocker: str = "",
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "blocks_neutral_reporting": status == "fail",
        "evidence": evidence,
        "source_artifacts": source_artifacts,
        "blocker": blocker,
    }


def build_payload(root: Path) -> dict[str, Any]:
    paper_path = root / PAPER_GATE_CLOSURE_MAP
    activation_path = root / POST_EXPERIMENT_PUBLICATION_ACTIVATION
    publication_path = root / PUBLICATION_METHODOLOGY_AUDIT
    review_path = root / SCIENTIFIC_REVIEW_FINDING_REGISTER

    paper = read_json_if_present(paper_path)
    activation = read_json_if_present(activation_path)
    publication = read_json_if_present(publication_path)
    review = read_json_if_present(review_path)

    paper_summary = summary(paper)
    activation_summary = summary(activation)
    publication_summary = summary(publication)
    review_summary = summary(review)
    activation_checks = {
        str(row.get("check_id")): row
        for row in activation.get("activation_checks", []) or []
        if isinstance(row, dict) and row.get("check_id")
    }
    final_disposition_check = activation_checks.get("final_result_dispositions_available", {})

    pattern_rows, unguarded_hits, unguarded_family_counts = scan_language(root)
    scanned_files = iter_scan_files(root)
    total_hit_count = sum(safe_int(row.get("total_hit_count")) for row in pattern_rows)
    guarded_hit_count = sum(safe_int(row.get("guarded_hit_count")) for row in pattern_rows)
    unguarded_hit_count = sum(
        safe_int(row.get("unguarded_hit_count")) for row in pattern_rows
    )
    final_result_disposition_count = safe_int(
        activation_summary.get("final_result_disposition_gate_count")
    )
    paper_gate_count = safe_int(paper_summary.get("gate_count"))

    checks = [
        check_row(
            "no_unguarded_promotional_language",
            "pass" if unguarded_hit_count == 0 else "fail",
            {
                "unguarded_hit_count": unguarded_hit_count,
                "unguarded_family_counts": unguarded_family_counts,
            },
            [rel(path, root) for path in scanned_files[:MAX_SAMPLE_COUNT]],
            "unguarded_method_or_claim_promotion_language",
        ),
        check_row(
            "activation_uses_result_dispositions_not_positive_requirement",
            (
                "pass"
                if final_disposition_check.get("status") == "pass"
                and final_result_disposition_count == paper_gate_count
                and safe_int(activation_summary.get("positive_claim_ready_gate_count")) == 0
                else "fail"
            ),
            {
                "final_result_disposition_check_status": final_disposition_check.get(
                    "status"
                ),
                "final_result_disposition_gate_count": final_result_disposition_count,
                "paper_gate_count": paper_gate_count,
                "positive_claim_ready_gate_count": activation_summary.get(
                    "positive_claim_ready_gate_count"
                ),
            },
            [rel(activation_path, root), rel(paper_path, root)],
            "publication_activation_requires_positive_results",
        ),
        check_row(
            "paper_gate_map_retains_disallowed_language_controls",
            (
                "pass"
                if safe_int(paper_summary.get("disallowed_language_item_count")) > 0
                and paper_summary.get("positive_claim_ready_gate_count") == 0
                else "fail"
            ),
            {
                "disallowed_language_item_count": paper_summary.get(
                    "disallowed_language_item_count"
                ),
                "positive_claim_ready_gate_count": paper_summary.get(
                    "positive_claim_ready_gate_count"
                ),
                "scoped_or_negative_path_ready_gate_count": paper_summary.get(
                    "scoped_or_negative_path_ready_gate_count"
                ),
            },
            [rel(paper_path, root)],
            "paper_gate_language_controls_missing",
        ),
        check_row(
            "publication_methodology_keeps_final_claims_blocked",
            (
                "pass"
                if publication_summary.get("can_support_final_method_selection") is False
                and publication_summary.get("can_support_publication_ready_fairness")
                is False
                and publication_summary.get("can_support_bounded_support_validity")
                is False
                and publication_summary.get("can_support_venn_abers_regression_validation")
                is False
                and safe_int(publication_summary.get("unsupported_claim_hits")) == 0
                else "fail"
            ),
            {
                "can_support_final_method_selection": publication_summary.get(
                    "can_support_final_method_selection"
                ),
                "can_support_publication_ready_fairness": publication_summary.get(
                    "can_support_publication_ready_fairness"
                ),
                "can_support_bounded_support_validity": publication_summary.get(
                    "can_support_bounded_support_validity"
                ),
                "can_support_venn_abers_regression_validation": (
                    publication_summary.get(
                        "can_support_venn_abers_regression_validation"
                    )
                ),
                "unsupported_claim_hits": publication_summary.get(
                    "unsupported_claim_hits"
                ),
            },
            [rel(publication_path, root)],
            "publication_methodology_promotes_final_claim",
        ),
        check_row(
            "scientific_review_hard_blockers_do_not_support_stronger_claims",
            (
                "pass"
                if safe_int(review_summary.get("hard_open_blocker_count")) == 0
                else "fail"
            ),
            {
                "open_blocker_count": review_summary.get("open_blocker_count"),
                "hard_open_blocker_count": review_summary.get(
                    "hard_open_blocker_count"
                ),
                "tracked_caveat_count": review_summary.get("tracked_caveat_count"),
            },
            [rel(review_path, root)],
            "scientific_review_hard_open_blockers",
        ),
    ]
    failed_checks = [row for row in checks if row["status"] == "fail"]
    overall_status = (
        "neutral_reporting_language_audit_pass"
        if not failed_checks
        else "neutral_reporting_language_audit_fail"
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_status": overall_status,
            "scanned_file_count": len(scanned_files),
            "term_pattern_count": len(TERM_SPECS),
            "term_hit_count": total_hit_count,
            "guarded_hit_count": guarded_hit_count,
            "unguarded_hit_count": unguarded_hit_count,
            "failed_check_count": len(failed_checks),
            "check_count": len(checks),
            "positive_claim_ready_gate_count": activation_summary.get(
                "positive_claim_ready_gate_count"
            ),
            "final_result_disposition_gate_count": final_result_disposition_count,
            "paper_gate_count": paper_gate_count,
            "publication_phase_start_authorized": activation_summary.get(
                "publication_phase_start_authorized"
            ),
            "publication_activation_status": activation_summary.get("overall_status"),
            "unsupported_claim_hits": publication_summary.get("unsupported_claim_hits"),
            "scientific_review_open_blocker_count": review_summary.get(
                "open_blocker_count"
            ),
            "unguarded_family_counts": unguarded_family_counts,
        },
        "checks": checks,
        "failed_checks": [row["check_id"] for row in failed_checks],
        "pattern_rows": pattern_rows,
        "unguarded_hit_samples": unguarded_hits,
        "claim_boundaries": [
            "This audit detects unguarded promotional language; it does not judge method performance.",
            "Positive, negative, scoped, blocked, and no-claim dispositions are all valid scientific outcomes when reported as observed.",
            "CQR, CV+, Venn-Abers, fairness, bounded-support, and final-selection language must remain diagnostic or explicitly gated until dedicated claim gates pass.",
            "A passing audit means promotional phrases are guarded by claim-boundary language, not that manuscript drafting is authorized.",
        ],
        "source_artifacts": {
            "paper_gate_closure_map": rel(paper_path, root),
            "post_experiment_publication_activation_audit": rel(
                activation_path, root
            ),
            "publication_methodology_audit": rel(publication_path, root),
            "scientific_review_finding_register": rel(review_path, root),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary_payload = payload["summary"]
    lines = [
        "# Neutral Reporting Language Audit",
        "",
        "This audit checks whether promotional or positive-claim language is guarded by explicit claim-boundary context.",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Scanned files: {summary_payload['scanned_file_count']}",
        f"- Term hits: {summary_payload['term_hit_count']}",
        f"- Guarded hits: {summary_payload['guarded_hit_count']}",
        f"- Unguarded hits: {summary_payload['unguarded_hit_count']}",
        f"- Failed checks: {summary_payload['failed_check_count']} / {summary_payload['check_count']}",
        f"- Final result dispositions: {summary_payload['final_result_disposition_gate_count']} / {summary_payload['paper_gate_count']}",
        f"- Positive-claim-ready gates: {summary_payload['positive_claim_ready_gate_count']}",
        f"- Publication phase start authorized: `{summary_payload['publication_phase_start_authorized']}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Blocks neutral reporting |",
        "|---|---:|---:|",
    ]
    for row in payload["checks"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['status']}` | `{row['blocks_neutral_reporting']}` |"
        )
    lines.extend(
        [
            "",
            "## Term Families",
            "",
            "| Term | Family | Hits | Guarded | Unguarded | Status |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in payload["pattern_rows"]:
        lines.append(
            "| `{term_id}` | `{family}` | {total} | {guarded} | {unguarded} | `{status}` |".format(
                term_id=row["term_id"],
                family=row["family"],
                total=row["total_hit_count"],
                guarded=row["guarded_hit_count"],
                unguarded=row["unguarded_hit_count"],
                status=row["status"],
            )
        )
    if payload["unguarded_hit_samples"]:
        lines.extend(["", "## Unguarded Samples", ""])
        for hit in payload["unguarded_hit_samples"]:
            lines.append(
                f"- `{hit['term_id']}` in `{hit['path']}`: {hit['context']}"
            )
    lines.extend(["", "## Claim Boundaries", ""])
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "overall_status": payload["summary"]["overall_status"],
                "unguarded_hit_count": payload["summary"]["unguarded_hit_count"],
                "failed_check_count": payload["summary"]["failed_check_count"],
                "out": rel(out, root),
            },
            sort_keys=True,
        )
    )
    if payload["failed_checks"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
