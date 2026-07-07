"""Audit regression conformal method-literature coverage.

This audit does not choose a final method. It checks that the study has a
traceable registry/spec/config position for major regression conformal method
families, and it records which literature families remain scoped gaps rather
than completed broad-sweep runner evidence.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from cpfi.regression.conformal import get_regression_cp_methods
from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_method_literature_coverage_audit_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_OUT = REPORT_DIR / "method_literature_coverage_audit.json"
METHOD_REGISTRY = Path("experiments/regression/catalogs/method_registry.json")
LITERATURE_NOTES = Path("experiments/regression/catalogs/literature_notes.md")
METHOD_TABLE = Path("experiments/regression/manuscript/method_table.md")
METHOD_SPECS_DIR = Path("experiments/regression/method_specs")
CONFIG_GLOB = "experiments/regression/configs/*.yaml"


CLAIM_BOUNDARIES = [
    "This audit checks method-literature coverage and claim boundaries; it is not a final model or conformal-method selection.",
    "Runner-integrated methods are empirical candidates only when their configs, ledgers, endpoint audits, and claim guards exist.",
    "Reference, diagnostic, predictive-distribution, risk-control, and watchlist methods must not be rewritten as completed ordinary interval runner evidence.",
    "Tracked literature gaps keep final-selection and exhaustive-literature claims blocked until implemented, explicitly scoped out, or assigned to a separate follow-up study.",
]


@dataclass(frozen=True)
class LiteratureRequirement:
    requirement_id: str
    family: str
    role: str
    method_ids: tuple[str, ...]
    runner_method_ids: tuple[str, ...]
    spec_paths: tuple[str, ...]
    source_urls: tuple[str, ...]
    required_literature_tokens: tuple[str, ...]
    claim_boundary: str


REQUIREMENTS: tuple[LiteratureRequirement, ...] = (
    LiteratureRequirement(
        "split_conformal_regression",
        "core_interval",
        "runner_required",
        ("split_abs",),
        ("split_abs",),
        ("experiments/regression/method_specs/split_and_cqr_regression.md",),
        ("https://arxiv.org/abs/1604.04173",),
        ("Distribution-Free Predictive Inference For Regression",),
        "Ordinary split conformal is a baseline interval method, not a conditional/fairness guarantee.",
    ),
    LiteratureRequirement(
        "mondrian_and_shrinkage_regression",
        "group_conditional",
        "runner_required",
        ("mondrian_abs", "shrink_gamma"),
        ("mondrian_abs",),
        ("experiments/regression/method_specs/split_and_cqr_regression.md",),
        ("https://arxiv.org/abs/1604.04173",),
        ("locally varying",),
        "Mondrian/shrinkage rows are group/sensitivity diagnostics unless group-size and claim gates pass.",
    ),
    LiteratureRequirement(
        "normalized_locally_adaptive_split",
        "heteroscedastic_interval",
        "runner_required",
        ("normalized_abs",),
        ("normalized_abs",),
        ("experiments/regression/method_specs/split_and_cqr_regression.md",),
        ("https://arxiv.org/abs/1604.04173",),
        ("locally varying",),
        "Normalized residual intervals require endpoint audits before support or boundedness claims.",
    ),
    LiteratureRequirement(
        "conformalized_quantile_regression",
        "heteroscedastic_interval",
        "runner_required",
        ("cqr",),
        ("cqr",),
        ("experiments/regression/method_specs/split_and_cqr_regression.md",),
        ("https://arxiv.org/abs/1905.03222",),
        ("Conformalized Quantile Regression",),
        "Current broad CQR rows are fixed-backend evidence unless a backend sweep is cited.",
    ),
    LiteratureRequirement(
        "covariate_shift_weighted_conformal",
        "distribution_shift",
        "runner_required",
        ("weighted_abs_covariate_shift",),
        ("weighted_abs_covariate_shift",),
        ("experiments/regression/method_specs/covariate_shift_regression.md",),
        ("https://arxiv.org/abs/1904.06019",),
        ("Conformal Prediction Under Covariate Shift",),
        "Local density-ratio estimates make this diagnostic unless ratios are known or externally validated.",
    ),
    LiteratureRequirement(
        "tail_specific_split_intervals",
        "tail_control",
        "runner_required",
        ("split_tail_0.25", "split_tail_0.50", "split_tail_0.75"),
        ("split_tail_0.25", "split_tail_0.50", "split_tail_0.75"),
        ("experiments/regression/method_specs/tail_specific_split_regression.md",),
        ("https://arxiv.org/abs/2606.18199",),
        ("Conformal Prediction Intervals with Tail-Specific Guarantees",),
        "Current tail variants are fixed allocation diagnostics, not full shortest-interval optimization.",
    ),
    LiteratureRequirement(
        "split_tail_grid_shortest_diagnostic",
        "tail_control",
        "runner_required",
        ("split_tail_grid_shortest",),
        ("split_tail_grid_shortest",),
        ("experiments/regression/method_specs/tail_specific_split_regression.md",),
        ("https://arxiv.org/abs/2606.18199", "https://arxiv.org/abs/2604.25202"),
        (
            "Conformal Prediction Intervals with Tail-Specific Guarantees",
            "Tail allocation for conformal prediction intervals",
        ),
        "Grid-selected split-tail intervals are calibration diagnostics, not full TA-CQR shortest-interval guarantees.",
    ),
    LiteratureRequirement(
        "plus_family_and_resampling",
        "resampling_interval",
        "runner_required",
        (
            "jackknife_plus",
            "jackknife_minmax",
            "cv_plus",
            "cv_minmax",
            "jackknife_plus_after_bootstrap",
        ),
        (
            "jackknife_plus",
            "jackknife_minmax",
            "cv_plus",
            "cv_minmax",
            "jackknife_plus_after_bootstrap",
        ),
        ("experiments/regression/method_specs/plus_family_regression.md",),
        ("https://arxiv.org/abs/1905.02928", "https://arxiv.org/abs/2002.09025"),
        ("Predictive inference with the jackknife+", "Jackknife+-after-Bootstrap"),
        "Plus-family rows are runtime-capped and skipped when configured limits trigger.",
    ),
    LiteratureRequirement(
        "conformal_risk_control_boundary",
        "risk_control",
        "boundary_tracked",
        ("conformal_risk_control",),
        (),
        ("experiments/regression/method_specs/risk_control_and_boundary_methods.md",),
        ("https://arxiv.org/abs/2208.02814",),
        ("Conformal Risk Control",),
        "Risk-control claims are not ordinary interval-coverage claims.",
    ),
    LiteratureRequirement(
        "venn_abers_predictive_distribution",
        "venn_abers_distribution",
        "diagnostic_or_reference",
        ("ivapd_regression",),
        (),
        ("experiments/regression/method_specs/venn_abers_regression.md",),
        (
            "https://proceedings.mlr.press/v91/nouretdinov18a.html",
            "https://proceedings.mlr.press/v230/nouretdinov24a.html",
        ),
        ("Inductive Venn-Abers predictive distribution",),
        "IVAPD is a predictive-distribution diagnostic; interval extraction is a separate policy.",
    ),
    LiteratureRequirement(
        "generalized_venn_abers_quantile_bridge",
        "venn_abers_interval_diagnostic",
        "diagnostic_or_reference",
        (
            "generalized_venn_abers_quantile",
            "ivar_regression_unbounded",
            "venn_abers_quantile",
            "venn_abers_quantile_grid",
            "venn_abers_split_fallback",
        ),
        ("venn_abers_quantile", "venn_abers_split_fallback"),
        ("experiments/regression/method_specs/venn_abers_regression.md",),
        (
            "https://proceedings.mlr.press/v267/van-der-laan25a.html",
            "https://arxiv.org/html/2605.06646v1",
        ),
        ("Generalized Venn and Venn-Abers Calibration", "Inductive Venn-Abers and related regressors"),
        "Fast bridge/fallback rows remain diagnostic or ordinary split fallback evidence, not validated Venn-Abers regression coverage.",
    ),
    LiteratureRequirement(
        "full_conformal_score_grid_reference",
        "full_conformal_reference",
        "diagnostic_or_reference",
        ("full_conformal_regression",),
        (),
        (
            "experiments/regression/method_specs/distributional_and_full_conformal_regression.md",
        ),
        ("https://arxiv.org/abs/1604.04173",),
        ("full conformal inference",),
        "Full conformal score-grid inversion is a reference primitive until candidate refits are bundled.",
    ),
    LiteratureRequirement(
        "rank_one_out_reference",
        "full_conformal_reference",
        "diagnostic_or_reference",
        ("rank_one_out_conformal",),
        (),
        (
            "experiments/regression/method_specs/distributional_and_full_conformal_regression.md",
        ),
        ("https://arxiv.org/abs/1604.04173",),
        ("rank-one-out",),
        "Rank-one-out score-grid inversion is a reference primitive until rank-one update/refit bundles are added.",
    ),
    LiteratureRequirement(
        "distributional_conformal_prediction",
        "distributional_interval",
        "diagnostic_or_reference",
        ("distributional_conformal_prediction",),
        (),
        (
            "experiments/regression/method_specs/distributional_and_full_conformal_regression.md",
        ),
        ("https://arxiv.org/abs/1909.07889",),
        ("Distributional conformal prediction",),
        "Distributional PIT intervals are reference primitives until a conditional-distribution runner protocol exists.",
    ),
    LiteratureRequirement(
        "conformal_predictive_systems",
        "predictive_distribution",
        "diagnostic_or_reference",
        ("conformal_predictive_system",),
        (),
        (
            "experiments/regression/method_specs/distributional_and_full_conformal_regression.md",
        ),
        ("https://proceedings.mlr.press/v60/vovk17a.html", "https://arxiv.org/abs/1911.00941"),
        ("Nonparametric predictive distributions", "conformal predictive distributions"),
        "CPS CDF-grid interval extraction is a reference primitive until a CPS fitting protocol is bundled.",
    ),
    LiteratureRequirement(
        "tail_allocation_shortest_interval_watchlist",
        "tail_control",
        "diagnostic_or_reference",
        ("tail_allocation_shortest_interval",),
        (),
        (
            "experiments/regression/method_specs/distributional_and_full_conformal_regression.md",
        ),
        ("https://arxiv.org/abs/2604.25202",),
        ("Tail allocation for conformal prediction intervals",),
        "Tuning-split tail allocation is a reference primitive until full TA-CQR and endpoint audits are bundled.",
    ),
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


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def registry_methods(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("method_id")): row
        for row in payload.get("regression_methods", []) or []
        if isinstance(row, dict) and row.get("method_id")
    }


def config_method_counts(root: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for path in sorted(root.glob(CONFIG_GLOB)):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        for method in payload.get("cp_methods", []) or []:
            if isinstance(method, dict):
                method_id = str(method.get("method_id") or method.get("label") or "")
            else:
                method_id = str(method)
            if method_id:
                counts[method_id] += 1
    return dict(sorted(counts.items()))


def base_method_id(method_id: str) -> str:
    if method_id.startswith("shrink_"):
        return "shrink_gamma"
    if method_id.startswith("cqr_"):
        return "cqr"
    return method_id


def configured_base_method_counts(config_counts: dict[str, int]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for method_id, count in config_counts.items():
        counts[base_method_id(method_id)] += int(count)
    return dict(sorted(counts.items()))


def specs_text(root: Path) -> dict[str, str]:
    texts = {}
    for path in sorted((root / METHOD_SPECS_DIR).glob("*.md")):
        texts[rel(path, root)] = path.read_text(encoding="utf-8")
    return texts


def source_token_status(notes_text: str, requirement: LiteratureRequirement) -> dict[str, bool]:
    folded_notes = " ".join(notes_text.lower().split())
    return {
        token: " ".join(token.lower().split()) in folded_notes
        for token in requirement.required_literature_tokens
    }


def source_url_status(notes_text: str, requirement: LiteratureRequirement) -> dict[str, bool]:
    return {url: url in notes_text for url in requirement.source_urls}


def spec_status(
    root: Path,
    spec_texts: dict[str, str],
    requirement: LiteratureRequirement,
) -> dict[str, Any]:
    rows = []
    for spec in requirement.spec_paths:
        path = resolve(root, spec)
        text = spec_texts.get(rel(path, root), "")
        rows.append(
            {
                "path": rel(path, root),
                "exists": path.exists(),
                "mentions_any_method": any(method_id in text for method_id in requirement.method_ids),
            }
        )
    return {
        "all_present": all(row["exists"] for row in rows),
        "mentions_any_method": any(row["mentions_any_method"] for row in rows),
        "rows": rows,
    }


def requirement_row(
    requirement: LiteratureRequirement,
    *,
    root: Path,
    registry: dict[str, dict[str, Any]],
    runner_methods: set[str],
    config_counts: dict[str, int],
    spec_texts: dict[str, str],
    notes_text: str,
) -> dict[str, Any]:
    registry_missing = [method_id for method_id in requirement.method_ids if method_id not in registry]
    runner_missing = [
        method_id for method_id in requirement.runner_method_ids if method_id not in runner_methods
    ]
    base_config_counts = configured_base_method_counts(config_counts)
    queued_counts = {
        method_id: int(base_config_counts.get(method_id, 0))
        for method_id in sorted(set(requirement.method_ids) | set(requirement.runner_method_ids))
    }
    queued_total = sum(queued_counts.values())
    source_urls = source_url_status(notes_text, requirement)
    source_tokens = source_token_status(notes_text, requirement)
    spec = spec_status(root, spec_texts, requirement)

    hard_fail_reasons = []
    tracked_gap_reasons = []
    if registry_missing:
        hard_fail_reasons.append("missing_registry_methods")
    if not spec["all_present"]:
        hard_fail_reasons.append("missing_method_spec")
    if not spec["mentions_any_method"]:
        hard_fail_reasons.append("method_spec_does_not_mention_family")
    if not all(source_urls.values()) or not all(source_tokens.values()):
        hard_fail_reasons.append("literature_notes_missing_primary_source")
    if requirement.role == "runner_required":
        if runner_missing:
            hard_fail_reasons.append("runner_methods_missing")
        if queued_total == 0:
            hard_fail_reasons.append("runner_methods_not_queued_in_configs")
    elif requirement.role == "tracked_gap":
        tracked_gap_reasons.append("literature_family_tracked_not_runner_integrated")
    elif requirement.role == "boundary_tracked" and queued_total > 0:
        hard_fail_reasons.append("boundary_method_queued_as_interval_runner")
    elif requirement.role == "diagnostic_or_reference":
        if requirement.runner_method_ids and queued_total == 0:
            tracked_gap_reasons.append("diagnostic_runner_not_queued_in_configs")

    if hard_fail_reasons:
        status = "fail"
        severity = "high"
    elif tracked_gap_reasons:
        status = "tracked_gap"
        severity = "medium"
    else:
        status = "pass"
        severity = "none"

    return {
        "requirement_id": requirement.requirement_id,
        "family": requirement.family,
        "role": requirement.role,
        "status": status,
        "severity": severity,
        "method_ids": list(requirement.method_ids),
        "runner_method_ids": list(requirement.runner_method_ids),
        "registry_missing": registry_missing,
        "registry_statuses": {
            method_id: registry.get(method_id, {}).get("status")
            for method_id in requirement.method_ids
        },
        "runner_missing": runner_missing,
        "queued_config_counts": queued_counts,
        "queued_config_total": queued_total,
        "spec_status": spec,
        "source_url_status": source_urls,
        "source_token_status": source_tokens,
        "hard_fail_reasons": hard_fail_reasons,
        "tracked_gap_reasons": tracked_gap_reasons,
        "claim_boundary": requirement.claim_boundary,
    }


def build_payload(root: Path) -> dict[str, Any]:
    registry_path = root / METHOD_REGISTRY
    notes_path = root / LITERATURE_NOTES
    method_table_path = root / METHOD_TABLE
    registry = registry_methods(read_json(registry_path))
    runner_methods = set(get_regression_cp_methods())
    config_counts = config_method_counts(root)
    base_config_counts = configured_base_method_counts(config_counts)
    spec_texts = specs_text(root)
    notes_text = notes_path.read_text(encoding="utf-8")
    method_table_text = method_table_path.read_text(encoding="utf-8")

    rows = [
        requirement_row(
            requirement,
            root=root,
            registry=registry,
            runner_methods=runner_methods,
            config_counts=config_counts,
            spec_texts=spec_texts,
            notes_text=notes_text,
        )
        for requirement in REQUIREMENTS
    ]
    status_counts = Counter(row["status"] for row in rows)
    hard_failed = [row for row in rows if row["status"] == "fail"]
    tracked_gaps = [row for row in rows if row["status"] == "tracked_gap"]
    config_methods = set(config_counts)
    base_config_methods = set(base_config_counts)
    registry_method_ids = set(registry)
    runner_config_methods = base_config_methods.intersection(runner_methods)
    unregistered_config_methods = sorted(base_config_methods - registry_method_ids)
    runner_methods_not_in_registry = sorted(
        method_id
        for method_id in runner_methods - registry_method_ids
        if base_method_id(method_id) not in registry_method_ids
    )
    registry_runner_like = {
        method_id
        for method_id, row in registry.items()
        if any(
            token in str(row.get("status") or "")
            for token in (
                "implemented",
                "runner_integrated",
                "calibration_fallback",
            )
        )
    }
    runner_like_missing_dispatch = sorted(registry_runner_like - runner_methods)
    runner_like_dispatch_exceptions = {
        method_id
        for method_id in runner_like_missing_dispatch
        if (
            method_id == "shrink_gamma"
            and any(runner_method.startswith("shrink_") for runner_method in runner_methods)
        )
        or "not_runner" in str(registry[method_id].get("status"))
        or "not_standalone" in str(registry[method_id].get("status"))
        or "partially_instantiated" in str(registry[method_id].get("status"))
    }

    hard_checks = {
        "all_config_methods_registered": not unregistered_config_methods,
        "runner_dispatch_methods_registered": not runner_methods_not_in_registry,
        "runner_like_registry_methods_have_dispatch_or_reference_status": not [
            method_id
            for method_id in runner_like_missing_dispatch
            if method_id not in runner_like_dispatch_exceptions
        ],
        "method_table_preserves_no_final_ranking_boundary": (
            "No final manuscript method ranking" in method_table_text
            and "No final" in method_table_text
        ),
        "no_requirement_hard_failures": not hard_failed,
    }
    failed_checks = [key for key, passed in hard_checks.items() if not passed]
    if failed_checks:
        overall_status = "fail"
    elif tracked_gaps:
        overall_status = "method_literature_coverage_pass_with_tracked_gaps"
    else:
        overall_status = "method_literature_coverage_pass"

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "method_registry": rel(registry_path, root),
            "literature_notes": rel(notes_path, root),
            "method_table": rel(method_table_path, root),
            "method_specs_dir": rel(root / METHOD_SPECS_DIR, root),
            "config_glob": CONFIG_GLOB,
            "runner_dispatch": "cpfi.regression.conformal.get_regression_cp_methods",
        },
        "summary": {
            "overall_status": overall_status,
            "literature_requirement_count": len(rows),
            "status_counts": dict(sorted(status_counts.items())),
            "hard_failed_requirement_count": len(hard_failed),
            "tracked_gap_count": len(tracked_gaps),
            "registry_method_count": len(registry),
            "runner_dispatch_method_count": len(runner_methods),
            "configured_cp_method_count": len(config_methods),
            "configured_runner_method_count": len(runner_config_methods),
            "primary_source_url_count": len(
                sorted({url for requirement in REQUIREMENTS for url in requirement.source_urls})
            ),
            "failed_check_count": len(failed_checks),
            "unregistered_config_method_count": len(unregistered_config_methods),
            "runner_dispatch_method_missing_registry_count": len(
                runner_methods_not_in_registry
            ),
        },
        "hard_checks": hard_checks,
        "failed_checks": failed_checks,
        "unregistered_config_methods": unregistered_config_methods,
        "runner_dispatch_methods_missing_registry": runner_methods_not_in_registry,
        "runner_like_registry_methods_missing_dispatch": runner_like_missing_dispatch,
        "requirements": rows,
        "tracked_gaps": tracked_gaps,
        "claim_boundaries": CLAIM_BOUNDARIES,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Method Literature Coverage Audit",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Literature requirements: {summary['literature_requirement_count']}",
        f"- Status counts: `{json.dumps(summary['status_counts'], sort_keys=True)}`",
        f"- Hard failed requirements: {summary['hard_failed_requirement_count']}",
        f"- Tracked gaps: {summary['tracked_gap_count']}",
        f"- Registry methods: {summary['registry_method_count']}",
        f"- Runner dispatch methods: {summary['runner_dispatch_method_count']}",
        f"- Configured CP methods: {summary['configured_cp_method_count']}",
        f"- Primary source URLs: {summary['primary_source_url_count']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Requirements",
            "",
            "| Requirement | Role | Status | Queued Configs | Methods |",
            "|---|---|---:|---:|---|",
        ]
    )
    for row in payload["requirements"]:
        methods = ", ".join(f"`{method_id}`" for method_id in row["method_ids"])
        lines.append(
            f"| `{row['requirement_id']}` | `{row['role']}` | "
            f"`{row['status']}` | {row['queued_config_total']} | {methods} |"
        )
    lines.extend(["", "## Tracked Gaps", ""])
    if payload["tracked_gaps"]:
        for row in payload["tracked_gaps"]:
            lines.append(
                f"- `{row['requirement_id']}`: {row['claim_boundary']}"
            )
    else:
        lines.append("- None.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = resolve(root, args.out)
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["summary"]["overall_status"],
                "tracked_gap_count": payload["summary"]["tracked_gap_count"],
                "failed_check_count": payload["summary"]["failed_check_count"],
                "out": rel(out, root),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
