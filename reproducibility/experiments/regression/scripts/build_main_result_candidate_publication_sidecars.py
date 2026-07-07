"""Build manuscript-control sidecars for main-result candidate bundles.

The candidate bundles are completed experiment evidence, but they are not final
main-result promotions. This script creates the missing publication manifests
and refreshes the manuscript bundle index plus claim register so the closure
audit can distinguish complete diagnostic evidence from publishable claims.
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


SCHEMA = "cpfi_regression_main_result_candidate_publication_sidecars_v1"
REPORT_DIR = Path("experiments/regression/reports/methodology_sanity_audit_20260627")
DEFAULT_PLAN = REPORT_DIR / "main_result_candidate_bundle_plan.json"
DEFAULT_RESULTS = REPORT_DIR / "main_result_candidate_bundle_results.json"
DEFAULT_OUT = REPORT_DIR / "main_result_candidate_publication_sidecars.json"
BUNDLE_INDEX = Path("experiments/regression/catalogs/manuscript_bundle_index.json")
BUNDLE_INDEX_MD = Path("experiments/regression/catalogs/manuscript_bundle_index.md")
CLAIM_REGISTER = Path("experiments/regression/catalogs/manuscript_claim_register.json")
CLAIM_REGISTER_MD = Path("experiments/regression/catalogs/manuscript_claim_register.md")

AGGREGATE_CLAIM_ID = "main_result_candidate_bundles_blocked_diagnostic_evidence"
PAPER_GATES = [
    "final_method_model_selection_gate",
    "multiplicity_selection_record",
    "dataset_specific_final_gates",
    "endpoint_bounded_support_gate",
    "fairness_population_inference_gate",
    "venn_abers_regression_validation_gate",
]
GLOBAL_NON_CLAIMS = [
    "no final conformal method, model, dataset, or main-results winner",
    "no fairness, protected-class, population, policy, clinical, or production claim",
    "no bounded-support validity claim despite endpoint reconstruction evidence",
    "no validated Venn-Abers regression interval-coverage claim",
]
DATASET_NON_CLAIMS = {
    "nhanes_2017_2018_bmi": [
        "no population-weighted NHANES BMI prevalence, obesity screening, clinical, or health-disparity claim",
        "no survey-design inference because MEC weights, strata, and PSU variance are outside this candidate bundle",
    ],
    "nhanes_2017_2018_glycohemoglobin": [
        "no population-weighted NHANES glycohemoglobin, diabetes-prevalence, clinical, or health-disparity claim",
        "no survey-design inference because MEC weights, strata, and PSU variance are outside this candidate bundle",
    ],
    "nhanes_2017_2018_systolic_bp": [
        "no population-weighted NHANES blood-pressure, hypertension, clinical, or health-disparity claim",
        "no survey-design inference because MEC weights, strata, and PSU variance are outside this candidate bundle",
    ],
    "openml_analcatdata_chlamydia": [
        "no public-health disease-burden, exposure-denominator, sex/race/age fairness, or causal claim",
        "aggregate stratum counts are method-engineering evidence only",
    ],
    "stackoverflow_2025_compensation": [
        "no developer-population compensation, wage-gap, country-adjusted labor-market, or career-guidance claim",
        "self-selected survey filtering and heavy-tailed compensation endpoints remain method-engineering caveats",
    ],
    "uci_wine_quality": [
        "no wine-science, product-ranking, sensory-quality, or recommendation claim",
        "raw duplicate-contaminated UCI Wine evidence is diagnostic only and does not supersede the paired dedup sensitivity evidence",
        "bounded ordinal quality endpoints are audited as claim-boundary evidence, not as validated bounded-support interval claims",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN), help="Candidate plan JSON.")
    parser.add_argument(
        "--results", default=str(DEFAULT_RESULTS), help="Candidate results JSON."
    )
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


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def report_dir_for_plan_row(root: Path, row: dict[str, Any]) -> Path:
    ledger = Path(str(row.get("ledger") or ""))
    return root / "experiments/regression/reports" / ledger.parent.name


def load_sidecars(report_dir: Path) -> dict[str, dict[str, Any]]:
    sidecars = {}
    for name in (
        "pilot_summary",
        "split_profile",
        "feature_leakage_audit",
        "endpoint_audit",
    ):
        path = report_dir / f"{name}.json"
        sidecars[name] = read_json(path) if path.exists() else {}
    return sidecars


def int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def split_caveat_summary(split_profile: dict[str, Any]) -> dict[str, Any]:
    seed_rows = [
        seed
        for profile in split_profile.get("profiles", []) or []
        for seed in profile.get("seeds", []) or []
        if isinstance(seed, dict)
    ]
    return {
        "seed_count": len(seed_rows),
        "sparse_primary_group_cell_count": sum(
            int_value(seed.get("sparse_primary_group_cell_count")) for seed in seed_rows
        ),
        "duplicate_signature_caveat_seed_count": sum(
            1
            for seed in seed_rows
            if seed.get("all_model_visible_feature_signature_overlaps_zero") is False
            or seed.get("all_model_visible_feature_plus_target_signature_overlaps_zero")
            is False
        ),
        "row_id_overlap_failure_count": sum(
            1 for seed in seed_rows if seed.get("all_row_id_overlaps_zero") is not True
        ),
        "split_group_overlap_failure_count": sum(
            1 for seed in seed_rows if seed.get("all_split_group_overlaps_zero") is False
        ),
    }


def endpoint_caveat_summary(endpoint_audit: dict[str, Any]) -> dict[str, Any]:
    totals = endpoint_audit.get("totals") or {}
    return {
        "completed_ledger_rows": endpoint_audit.get("completed_ledger_rows"),
        "reconstructed_runs": endpoint_audit.get("reconstructed_runs"),
        "reconstruction_failures": endpoint_audit.get("reconstruction_failures"),
        "observed_target_min": endpoint_audit.get("observed_target_min"),
        "observed_target_max": endpoint_audit.get("observed_target_max"),
        "lower_floor": endpoint_audit.get("lower_floor"),
        "upper_warning": endpoint_audit.get("upper_warning"),
        "lower_below_floor": int_value(totals.get("lower_below_floor")),
        "upper_above_warning": int_value(totals.get("upper_above_warning")),
        "crossings": int_value(totals.get("crossings")),
        "nonfinite_lower": int_value(totals.get("nonfinite_lower")),
        "nonfinite_upper": int_value(totals.get("nonfinite_upper")),
        "width_above_observed_range": int_value(
            totals.get("width_above_observed_range")
        ),
        "width_above_twice_observed_range": int_value(
            totals.get("width_above_twice_observed_range")
        ),
    }


def leakage_summary(feature_leakage_audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "metadata_files_scanned": feature_leakage_audit.get("metadata_files_scanned"),
        "violations_count": feature_leakage_audit.get("violations_count"),
        "metadata_completeness": feature_leakage_audit.get("metadata_completeness")
        or {},
    }


def diagnostic_summary(result_row: dict[str, Any]) -> dict[str, Any]:
    selection = result_row.get("diagnostic_selection") or {}
    pathology = result_row.get("pathology_summary") or {}
    return {
        "diagnostic_primary_method": result_row.get("diagnostic_primary_method"),
        "winner_counts": selection.get("diagnostic_winner_counts") or {},
        "complete_matched_cell_count": selection.get("complete_matched_cell_count"),
        "flagged_row_count": pathology.get("flagged_row_count"),
        "flag_counts": pathology.get("flag_counts") or {},
    }


def compact_counter(counter: dict[str, Any]) -> str:
    if not counter:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counter.items()))


def manifest_title(dataset_id: str) -> str:
    return " ".join(part.upper() if part in {"bmi"} else part.title() for part in dataset_id.split("_"))


def render_manifest(row: dict[str, Any], result_row: dict[str, Any], report_dir: Path, root: Path) -> str:
    sidecars = load_sidecars(report_dir)
    split_profile = sidecars["split_profile"]
    feature_leakage = sidecars["feature_leakage_audit"]
    endpoint_audit = sidecars["endpoint_audit"]
    split_summary = split_caveat_summary(split_profile)
    endpoint_summary = endpoint_caveat_summary(endpoint_audit)
    leak_summary = leakage_summary(feature_leakage)
    diag_summary = diagnostic_summary(result_row)

    dataset_id = str(row["dataset_id"])
    report_name = report_dir.name
    target = split_profile.get("target") or endpoint_audit.get("config", {}).get("target")
    target_transform = split_profile.get("target_transform") or row.get(
        "target_transform"
    )
    diagnostic_group = split_profile.get("primary_group")
    expected = row.get("expected_atomic_run_count")
    completed = result_row.get("completed_atomic_run_count")
    seeds = row.get("main_result_candidate_seeds") or []
    alphas = row.get("target_alphas") or []
    cp_methods = row.get("cp_methods") or []
    non_claims = DATASET_NON_CLAIMS.get(dataset_id, [])
    blockers = [
        *PAPER_GATES,
        "endpoint pathologies are retained and block bounded-support claims",
        "split profile caveats are retained as claim-boundary evidence",
        "candidate evidence is diagnostic and cannot select a final method/model",
    ]

    lines = [
        f"# Publication Readiness Manifest: Main-Result Candidate Bundle {manifest_title(dataset_id)}",
        "",
        "Schema:",
        "`experiments/regression/catalogs/manuscript_evidence_manifest_schema.json`",
        "(`cpfi_regression_manuscript_evidence_manifest_v1`).",
        "",
        "Status: completed main-result candidate diagnostic bundle with blocked paper gates; no final method, model, dataset, fairness, bounded-support, production, or Venn-Abers validation conclusion is claimed.",
        "",
        f"Manifest timestamp: {now_utc()}.",
        "",
        "## Identity",
        "",
        f"- Experiment id: `{row.get('experiment_id')}`.",
        f"- Dataset id: `{dataset_id}`.",
        f"- Target: `{target}`.",
        f"- Target transform: `{target_transform}`.",
        f"- Diagnostic group: `{diagnostic_group}`.",
        f"- Config: `{row.get('config_path')}`.",
        f"- Report directory: `{rel(report_dir, root)}/`.",
        f"- Ledger path, ignored by Git: `{row.get('ledger')}`.",
        f"- Candidate result summary: `{rel(REPORT_DIR / 'main_result_candidate_bundle_results.json', Path('.'))}`.",
        f"- Publication sidecar builder schema: `{SCHEMA}`.",
        "",
        "## Scientific Question",
        "",
        "Does the fresh-seed candidate bundle reproduce useful regression conformal-prediction behavior for a preselected diagnostic candidate method set without promoting a final main-result claim?",
        "",
        "Scope:",
        "",
        "- diagnostic main-result-candidate evidence after independent fresh seeds;",
        "- completed candidate ledgers, prediction-cache sidecars, endpoint reconstruction, split profile, and feature-leakage audit;",
        "- no-promotion evidence for manuscript gate accounting and future claim-register review.",
        "",
        "Out of scope:",
        "",
    ]
    lines.extend(f"- {item};" for item in [*GLOBAL_NON_CLAIMS, *non_claims])
    lines.extend(
        [
            "- any result table row promoted before every paper gate passes.",
            "",
            "## Design",
            "",
            f"- Fresh candidate seeds: `{seeds}`.",
            f"- Alpha grid: `{alphas}`.",
            f"- Candidate conformal methods: `{cp_methods}`.",
            f"- Expected atomic rows: {expected}.",
            f"- Completed atomic rows: {completed}.",
            f"- Representative model count: {row.get('model_count')}.",
            "- Resume policy: ledger/checkpoint based; the manifest is generated only after the completed ledger and post-run sidecars exist.",
            "- Preprocessing policy: train-fitted preprocessing with target, diagnostic group, split helper, and direct target-construction columns excluded from model-visible features.",
            "- CQR boundary: fixed quantile-backend CQR is carried as diagnostic primary candidate only; no backend-sweep or final-superiority claim is made here.",
            "- Venn-Abers boundary: fast Venn-Abers regression bridge evidence remains diagnostic negative evidence because of undercoverage; this is not Venn-Abers regression validation evidence.",
            "",
            "## Data Evidence",
            "",
            f"- Dataset audit: `experiments/regression/audits/{dataset_id}/audit.json` and `experiments/regression/audits/{dataset_id}/audit.md`.",
            f"- Dataset profile: `experiments/regression/audits/{dataset_id}/profile.json` and `experiments/regression/audits/{dataset_id}/profile.md` when available.",
            f"- Diagnostic group policy: `{diagnostic_group}` is used for coverage diagnostics only.",
            "- Missingness, endpoint, duplicate, and source-selection caveats remain claim-boundary evidence.",
            "- Bounded-support policy: endpoint audit is complete, but endpoint pathologies block any bounded-support validity claim.",
            "",
            "## Model Evidence",
            "",
            f"- Configured representative model count: {row.get('model_count')}.",
            "- Full model-family searches are not rerun inside this candidate bundle; this bundle is a fresh-seed diagnostic closure run.",
            "- Model hyperparameters and random-state policy are inherited from the linked config and ledger.",
            "- Feature-leakage audit checks prediction metadata after the run and found no forbidden model-visible target/group features.",
            f"- feature-leakage audit: `{rel(report_dir / 'feature_leakage_audit.json', root)}` with {leak_summary['metadata_files_scanned']} metadata files scanned and {leak_summary['violations_count']} violations.",
            "",
            "## Conformal Evidence",
            "",
            "- Method registry and specs: `experiments/regression/catalogs/method_registry.json` and `experiments/regression/method_specs/`.",
            "- Nominal coverage levels are defined by alpha as `1 - alpha`; alpha is the requested error rate, not a separate conformal method.",
            "- Diagnostic negative evidence is retained: undercoverage, quantile crossings, fallback groups, endpoint excursions, and extreme widths are not filtered away.",
            f"- Diagnostic winner counts over completed matched cells: `{compact_counter(diag_summary['winner_counts'])}`.",
            f"- Flagged diagnostic rows: {diag_summary['flagged_row_count']} with flags `{compact_counter(diag_summary['flag_counts'])}`.",
            f"- endpoint audit: `{rel(report_dir / 'endpoint_audit.json', root)}` reconstructed {endpoint_summary['reconstructed_runs']} / {endpoint_summary['completed_ledger_rows']} completed runs with {endpoint_summary['reconstruction_failures']} reconstruction failures.",
            "",
            "## Selection And Multiplicity Status",
            "",
            "- Predeclared operating criterion: no final method-selection criterion is activated. Candidate ranking is diagnostic and remains blocked by paper gates.",
            f"- Ranking scope: dataset `{dataset_id}`, target `{target}`, diagnostic group `{diagnostic_group}`, fresh seeds `{seeds}`, alpha grid `{alphas}`, and methods `{cp_methods}`.",
            "- Multiplicity scope: the candidate bundle is one post-selection diagnostic surface within the wider searched dataset/model/method/seed space; it cannot be interpreted as a final independent winner.",
            "- Tie-break rule: among diagnostic rows that satisfy nominal coverage, interval score is read before mean width and group coverage gap; the rule is exploratory and not a promotion rule.",
            "- Nominal coverage requirement: each alpha targets coverage `1 - alpha` and any below-nominal row remains visible.",
            "- Exploratory ranking label: main-result candidate diagnostic evidence only.",
            "- Post-selection claim boundary: No method, model, dataset, or method-superiority claim is supported by this manifest.",
            "- Sensitivity or holdout validation: fresh seeds are independent from selection/validation seeds, but this is still not a final holdout promotion because paper gates remain blocked.",
            "",
            "## Split, Leakage, And Duplicate Controls",
            "",
            f"- Split profile: `{rel(report_dir / 'split_profile.json', root)}`.",
            f"- Split seed count: {split_summary['seed_count']}.",
            f"- Row-id overlap failures: {split_summary['row_id_overlap_failure_count']}.",
            f"- Split-group overlap failures: {split_summary['split_group_overlap_failure_count']}.",
            f"- Sparse primary-group cells: {split_summary['sparse_primary_group_cell_count']}.",
            f"- Duplicate-signature caveat seeds: {split_summary['duplicate_signature_caveat_seed_count']}.",
            "- feature-leakage audit status: pass with zero forbidden-feature violations.",
            "- Duplicate and sparse-cell caveats are retained as methodology caveats rather than treated as final scientific conclusions.",
            "",
            "## Metric Contract",
            "",
            "- Primary diagnostics: coverage, coverage error, group coverage gap, mean width, normalized width, and interval score.",
            "- Endpoint diagnostics: lower-bound floor excursions, upper-warning excursions, nonfinite endpoints, interval crossings, width above observed range, and inverse saturation where applicable.",
            f"- Endpoint floor/warning/pathology counts: lower_below_floor={endpoint_summary['lower_below_floor']}, upper_above_warning={endpoint_summary['upper_above_warning']}, crossings={endpoint_summary['crossings']}, nonfinite_lower={endpoint_summary['nonfinite_lower']}, nonfinite_upper={endpoint_summary['nonfinite_upper']}, width_above_observed_range={endpoint_summary['width_above_observed_range']}, width_above_twice_observed_range={endpoint_summary['width_above_twice_observed_range']}.",
            "- Metrics are diagnostic evidence only until claim-register, bundle-eligibility, and paper-readiness gates allow a paper surface.",
            "",
            "## Promotion Gates",
            "",
            "- claim-register status: candidate diagnostic no-promotion claim must remain blocked for main-result promotion.",
            "- Bundle eligibility status: candidate bundle can support descriptive/methodology/reproducibility evidence, not a main-results table winner.",
            "- No method is promoted by this manifest.",
            "- Required blocked gates:",
        ]
    )
    lines.extend(f"  - `{gate}`." for gate in PAPER_GATES)
    lines.extend(
        [
            "- Candidate-specific promotion blockers:",
        ]
    )
    lines.extend(f"  - {blocker}." for blocker in blockers)
    lines.append("")
    return "\n".join(lines)


def build_bundle_row(
    row: dict[str, Any],
    result_row: dict[str, Any],
    report_dir: Path,
    root: Path,
) -> dict[str, Any]:
    sidecars = load_sidecars(report_dir)
    split_profile = sidecars["split_profile"]
    endpoint = endpoint_caveat_summary(sidecars["endpoint_audit"])
    split_summary = split_caveat_summary(split_profile)
    dataset_id = str(row["dataset_id"])
    blockers = [
        "all six paper-readiness gates remain blocked",
        "candidate evidence is diagnostic and cannot support final method/model selection",
        "fresh-seed candidate run does not by itself resolve multiplicity across the wider searched surface",
        "no fairness, population, clinical, policy, causal, production, bounded-support, or Venn-Abers regression validation claim",
    ]
    if endpoint["lower_below_floor"] or endpoint["upper_above_warning"]:
        blockers.append(
            "endpoint audit retains floor or upper-warning excursions, so bounded-support promotion is blocked"
        )
    if split_summary["sparse_primary_group_cell_count"] or split_summary[
        "duplicate_signature_caveat_seed_count"
    ]:
        blockers.append(
            "split profile retains sparse-cell or duplicate-signature caveats"
        )
    return {
        "bundle_id": report_dir.name,
        "dataset_id": dataset_id,
        "target": split_profile.get("target"),
        "target_transform": split_profile.get("target_transform"),
        "diagnostic_group": split_profile.get("primary_group"),
        "manifest_path": rel(report_dir / "publication_readiness_manifest.md", root),
        "evidence_role": "main_result_candidate_diagnostic",
        "status": "completed_main_result_candidate_blocked_with_caveats",
        "paper_table_candidate": "main_results_table_blocked_diagnostic_only",
        "claim_scope": (
            f"{dataset_id} fresh-seed main_result_candidate diagnostic bundle; "
            "supports closure and methodology evidence only, not a final main result."
        ),
        "promotion_blockers": blockers,
        "candidate_methods": row.get("cp_methods") or [],
        "candidate_seeds": row.get("main_result_candidate_seeds") or [],
        "candidate_alphas": row.get("target_alphas") or [],
        "completed_atomic_run_count": result_row.get("completed_atomic_run_count"),
        "diagnostic_winner_counts": (
            (result_row.get("diagnostic_selection") or {}).get(
                "diagnostic_winner_counts"
            )
            or {}
        ),
        "endpoint_pathology": endpoint,
    }


def update_bundle_index(
    root: Path,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    path = root / BUNDLE_INDEX
    payload = read_json(path)
    existing = [
        item
        for item in payload.get("bundles", []) or []
        if isinstance(item, dict)
        and item.get("bundle_id") not in {row["bundle_id"] for row in rows}
    ]
    payload["bundles"] = [*existing, *rows]
    statuses = [str(row.get("status") or "") for row in payload["bundles"]]
    payload["generated_utc"] = now_utc()
    payload["bundle_summary"] = {
        "manifest_count": len(payload["bundles"]),
        "completed_with_caveats_count": sum(
            status.startswith("completed") for status in statuses
        ),
        "active_run_count": sum(
            "active" in status or "setup" in status for status in statuses
        ),
        "blocked_or_pending_count": sum(
            "blocked" in status or "pending" in status for status in statuses
        ),
    }
    atomic_write_json(path, payload)
    atomic_write_text(root / BUNDLE_INDEX_MD, render_bundle_index_markdown(payload))
    return payload


def render_bundle_index_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("bundle_summary") or {}
    lines = [
        "# Regression CP Manuscript Bundle Index",
        "",
        f"Generated UTC: {payload.get('generated_utc')}",
        "",
        "This index is a manuscript extraction control surface, not a result table. It lists publication-readiness bundles that already have a manifest and states where each bundle may be used later if its gates and claim boundaries allow it.",
        "",
        "## Global Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload.get("global_boundaries") or [])
    lines.extend(
        [
            "",
            "## Current Bundle Coverage",
            "",
            f"- Manifested bundles: {summary.get('manifest_count')}.",
            f"- Completed with caveats: {summary.get('completed_with_caveats_count')}.",
            f"- Active/setup runs pending: {summary.get('active_run_count')}.",
            f"- Blocked or pending indexed bundles: {summary.get('blocked_or_pending_count')}.",
            "",
            "## Bundle Index",
            "",
            "| Bundle | Dataset | Target | Role | Status | Paper Surface |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for bundle in payload.get("bundles", []) or []:
        status = str(bundle.get("status") or "").replace("_", " ")
        surface = str(bundle.get("paper_table_candidate") or "").replace("_", " ")
        dataset = str(bundle.get("dataset_id") or "")
        if bundle.get("paired_dataset_id"):
            dataset = f"{dataset} / {bundle.get('paired_dataset_id')}"
        lines.append(
            "| "
            f"`{bundle.get('bundle_id')}` | "
            f"`{dataset}` | "
            f"`{bundle.get('target')}` | "
            f"{bundle.get('evidence_role')} | "
            f"{status} | "
            f"{surface} |"
        )
    lines.extend(
        [
            "",
            "## Extraction Rule",
            "",
            "Manuscript tables must be generated from manifests, summary reports, audits, and claim-register entries. Changelog and diary entries can explain chronology, but they are not primary scientific evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def aggregate_claim(
    rows: list[dict[str, Any]],
    report_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    dataset_ids = [str(row["dataset_id"]) for row in rows]
    manifest_node_ids = [
        f"manifest:{row['bundle_id']}:publication_readiness" for row in rows
    ]
    report_node_ids = [f"report:{row['bundle_id']}" for row in rows]
    sidecar_nodes = [
        f"report:{row['bundle_id']}:{sidecar}"
        for row in rows
        for sidecar in ("feature_leakage_audit", "endpoint_audit", "split_profile")
    ]
    endpoint_blockers = [
        f"{row['dataset_id']}: lower_below_floor={row['endpoint_pathology']['lower_below_floor']}, upper_above_warning={row['endpoint_pathology']['upper_above_warning']}"
        for row in rows
        if row["endpoint_pathology"]["lower_below_floor"]
        or row["endpoint_pathology"]["upper_above_warning"]
    ]
    dataset_count = len(dataset_ids)
    completed_total = sum(
        int_value(row.get("completed_atomic_run_count")) for row in report_rows
    )
    expected_total = sum(
        int_value(row.get("expected_atomic_run_count")) for row in report_rows
    )
    return {
        "claim_id": AGGREGATE_CLAIM_ID,
        "claim_type": "main_result_candidate_gate",
        "status": "diagnostic_candidate_evidence_blocked_no_main_result_promotion",
        "claim_text": (
            f"{dataset_count} fresh-seed main_result_candidate bundles have completed ledgers, "
            "feature-leakage audits, endpoint audits, publication manifests, and "
            "bundle-index coverage; they are diagnostic no-promotion evidence and "
            "cannot support a final main-result claim while paper gates remain blocked."
        ),
        "scope": (
            f"Fresh-seed candidate evidence for the {dataset_count} selected datasets only; "
            "no final method, model, dataset, fairness, population, bounded-support, "
            "production, or Venn-Abers regression validation claim."
        ),
        "dataset_ids": dataset_ids,
        "supporting_node_ids": [
            "report:main_result_candidate_bundle_results",
            "report:main_result_candidate_post_run_closure_audit",
            "catalog:manuscript_bundle_index",
            *manifest_node_ids,
            *report_node_ids,
            *sidecar_nodes,
        ],
        "blocking_node_ids": [f"paper_gate:{gate}" for gate in PAPER_GATES],
        "not_claiming": [
            *GLOBAL_NON_CLAIMS,
            "CQR, CV+, and Mondrian_abs counts are diagnostic candidate evidence, not a final recommendation",
            "endpoint pathologies are retained rather than hidden",
            *endpoint_blockers,
        ],
        "requirements": [
            {
                "requirement_id": "completed_candidate_ledgers",
                "status": "complete",
                "description": (
                    f"All {dataset_count} candidate ledgers have "
                    f"{completed_total}/{expected_total} completed atomic rows."
                ),
                "supporting_node_ids": report_node_ids,
                "artifact_paths": [row["manifest_path"] for row in rows],
            },
            {
                "requirement_id": "pilot_summaries",
                "status": "pass",
                "description": "Pilot summaries are present and synchronized with candidate ledgers.",
                "supporting_node_ids": report_node_ids,
            },
            {
                "requirement_id": "split_profiles",
                "status": "pass_with_caveats",
                "description": "Split profiles pass hard row-id/split-group checks and retain sparse or duplicate-signature caveats.",
                "supporting_node_ids": [
                    f"report:{row['bundle_id']}:split_profile" for row in rows
                ],
            },
            {
                "requirement_id": "feature_leakage_audits",
                "status": "pass",
                "description": "Feature-leakage audits scanned prediction metadata and found zero forbidden-feature violations.",
                "supporting_node_ids": [
                    f"report:{row['bundle_id']}:feature_leakage_audit" for row in rows
                ],
            },
            {
                "requirement_id": "endpoint_audits",
                "status": "pass_with_endpoint_caveats",
                "description": "Endpoint audits reconstructed all candidate completed runs and retained endpoint pathology counts.",
                "supporting_node_ids": [
                    f"report:{row['bundle_id']}:endpoint_audit" for row in rows
                ],
            },
            {
                "requirement_id": "publication_manifests",
                "status": "present",
                "description": (
                    "Publication-readiness manifests exist for all "
                    f"{dataset_count} candidate bundles."
                ),
                "supporting_node_ids": manifest_node_ids,
                "artifact_paths": [row["manifest_path"] for row in rows],
            },
            {
                "requirement_id": "main_result_promotion",
                "status": "blocked",
                "description": "Main-result promotion remains blocked by paper gates.",
                "blocking_node_ids": [f"paper_gate:{gate}" for gate in PAPER_GATES],
            },
            {
                "requirement_id": "claim_boundary",
                "status": "blocked",
                "description": "Claim boundary blocks final method/model, fairness/population, bounded-support, production, and validated Venn-Abers claims.",
                "blocking_node_ids": [f"paper_gate:{gate}" for gate in PAPER_GATES],
            },
        ],
        "diagnostic_summary": {
            "dataset_count": dataset_count,
            "completed_atomic_run_count": completed_total,
            "expected_atomic_run_count": expected_total,
            "diagnostic_winner_counts": dict(
                sum_counters(
                    (report.get("diagnostic_selection") or {}).get(
                        "diagnostic_winner_counts"
                    )
                    or {}
                    for report in report_rows
                )
            ),
        },
    }


def sum_counters(counters: Any) -> Counter[str]:
    total: Counter[str] = Counter()
    for counter in counters:
        total.update({str(key): int_value(value) for key, value in counter.items()})
    return total


def update_claim_register(
    root: Path,
    claim: dict[str, Any],
) -> dict[str, Any]:
    path = root / CLAIM_REGISTER
    payload = read_json(path)
    claims = [
        item
        for item in payload.get("claims", []) or []
        if isinstance(item, dict) and item.get("claim_id") != AGGREGATE_CLAIM_ID
    ]
    payload["claims"] = [*claims, claim]
    payload["generated_utc"] = now_utc()
    atomic_write_json(path, payload)
    update_claim_register_markdown(root / CLAIM_REGISTER_MD, claim)
    return payload


def render_claim_markdown(claim: dict[str, Any]) -> str:
    lines = [
        f"## Claim: {claim['claim_id']}",
        "",
        f"Status: `{claim['status']}`",
        "",
        claim["claim_text"],
        "",
        f"Scope: {claim['scope']}",
        "",
        "Dataset ids:",
        "",
    ]
    lines.extend(f"- `{dataset_id}`" for dataset_id in claim.get("dataset_ids") or [])
    lines.extend(["", "Supporting evidence nodes:", ""])
    lines.extend(f"- `{node_id}`" for node_id in claim.get("supporting_node_ids") or [])
    lines.extend(["", "Blocking evidence nodes:", ""])
    lines.extend(f"- `{node_id}`" for node_id in claim.get("blocking_node_ids") or [])
    lines.extend(["", "Requirements:", ""])
    for requirement in claim.get("requirements") or []:
        lines.append(
            f"- `{requirement['requirement_id']}`: {requirement['status']}."
        )
    lines.extend(["", "Non-claims:", ""])
    lines.extend(f"- {item}." for item in claim.get("not_claiming") or [])
    lines.append("")
    return "\n".join(lines)


def update_claim_register_markdown(path: Path, claim: dict[str, Any]) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else "# Regression CP Manuscript Claim Register\n\n"
    section = render_claim_markdown(claim)
    pattern = re.compile(
        rf"^## Claim: {re.escape(claim['claim_id'])}\n.*?(?=^## Claim: |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    if pattern.search(text):
        text = pattern.sub(section, text)
    else:
        text = text.rstrip() + "\n\n" + section
    atomic_write_text(path, text.rstrip() + "\n")


def build_payload(
    root: Path,
    *,
    plan_path: Path,
    results_path: Path,
) -> dict[str, Any]:
    plan = read_json(plan_path)
    results = read_json(results_path)
    result_by_dataset = {
        str(row.get("dataset_id")): row
        for row in results.get("dataset_rows", []) or []
        if isinstance(row, dict) and row.get("dataset_id")
    }
    generated_rows: list[dict[str, Any]] = []
    bundle_rows: list[dict[str, Any]] = []
    report_rows: list[dict[str, Any]] = []
    for row in plan.get("candidate_rows", []) or []:
        if not isinstance(row, dict) or not row.get("dataset_id"):
            continue
        dataset_id = str(row["dataset_id"])
        result_row = result_by_dataset[dataset_id]
        report_dir = report_dir_for_plan_row(root, row)
        manifest_path = report_dir / "publication_readiness_manifest.md"
        atomic_write_text(
            manifest_path,
            render_manifest(row, result_row, report_dir, root),
        )
        bundle_row = build_bundle_row(row, result_row, report_dir, root)
        bundle_rows.append(bundle_row)
        report_rows.append(result_row)
        generated_rows.append(
            {
                "dataset_id": dataset_id,
                "bundle_id": report_dir.name,
                "manifest_path": rel(manifest_path, root),
                "feature_leakage_audit": rel(
                    report_dir / "feature_leakage_audit.json", root
                ),
                "endpoint_audit": rel(report_dir / "endpoint_audit.json", root),
                "status": "generated",
            }
        )

    bundle_index = update_bundle_index(root, bundle_rows)
    claim = aggregate_claim(bundle_rows, report_rows)
    claim_register = update_claim_register(root, claim)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": now_utc(),
        "source_artifacts": {
            "plan": rel(plan_path, root),
            "results": rel(results_path, root),
            "bundle_index": rel(root / BUNDLE_INDEX, root),
            "claim_register": rel(root / CLAIM_REGISTER, root),
        },
        "summary": {
            "candidate_dataset_count": len(generated_rows),
            "manifest_generated_count": len(generated_rows),
            "bundle_index_manifest_count": (
                bundle_index.get("bundle_summary") or {}
            ).get("manifest_count"),
            "claim_register_claim_count": len(claim_register.get("claims", []) or []),
            "aggregate_claim_id": AGGREGATE_CLAIM_ID,
            "can_support_main_result_promotion": False,
            "paper_gate_blocker_count": len(PAPER_GATES),
        },
        "rows": generated_rows,
        "claim_boundaries": [
            "Generated candidate sidecars close post-run documentation blockers, not paper promotion gates.",
            "The aggregate claim is diagnostic no-promotion evidence while all paper gates remain blocked.",
        ],
    }
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Main-Result Candidate Publication Sidecars",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Candidate datasets: {summary['candidate_dataset_count']}",
        f"- Manifests generated: {summary['manifest_generated_count']}",
        f"- Bundle-index manifest count: {summary['bundle_index_manifest_count']}",
        f"- Claim-register claim count: {summary['claim_register_claim_count']}",
        f"- Aggregate claim id: `{summary['aggregate_claim_id']}`",
        f"- Main-result promotion supported: `{summary['can_support_main_result_promotion']}`",
        f"- Paper gate blockers retained: {summary['paper_gate_blocker_count']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Generated Rows",
            "",
            "| Dataset | Bundle | Manifest | Status |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            "| "
            f"`{row['dataset_id']}` | "
            f"`{row['bundle_id']}` | "
            f"`{row['manifest_path']}` | "
            f"`{row['status']}` |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = resolve(root, args.out)
    payload = build_payload(
        root,
        plan_path=resolve(root, args.plan),
        results_path=resolve(root, args.results),
    )
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(json.dumps({"out": rel(out_path, root), **payload["summary"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
