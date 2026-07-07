"""Build the publication citation registry for regression CP sources.

This pre-prose artifact converts the already audited method-literature and
reader-primer source URLs into stable citation keys and BibTeX entries. It
does not add new method claims, draft manuscript text, or authorize a final
method recommendation.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_publication_citation_registry_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/publication_citation_registry.json")
DEFAULT_BIB_OUT = Path("experiments/regression/manuscript/references.bib")
READER_METHOD_PRIMER = Path(
    "experiments/regression/manuscript/reader_method_primer_citation_map.json"
)
METHOD_LITERATURE_AUDIT = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "method_literature_coverage_audit.json"
)


CITATION_ROWS: tuple[dict[str, Any], ...] = (
    {
        "citation_key": "lei2017distribution_free_regression",
        "entry_type": "misc",
        "title": "Distribution-Free Predictive Inference For Regression",
        "authors": [
            "Lei, Jing",
            "G'Sell, Max",
            "Rinaldo, Alessandro",
            "Tibshirani, Ryan J.",
            "Wasserman, Larry",
        ],
        "year": "2017",
        "url": "https://arxiv.org/abs/1604.04173",
        "doi": "10.48550/arXiv.1604.04173",
        "eprint": "1604.04173",
        "archive_prefix": "arXiv",
        "source_kind": "arxiv",
        "metadata_source_note": "arXiv page: submitted 2016, last revised 2017.",
    },
    {
        "citation_key": "tibshirani2020covariate_shift",
        "entry_type": "misc",
        "title": "Conformal Prediction Under Covariate Shift",
        "authors": [
            "Tibshirani, Ryan J.",
            "Barber, Rina Foygel",
            "Candes, Emmanuel J.",
            "Ramdas, Aaditya",
        ],
        "year": "2020",
        "url": "https://arxiv.org/abs/1904.06019",
        "doi": "10.48550/arXiv.1904.06019",
        "eprint": "1904.06019",
        "archive_prefix": "arXiv",
        "source_kind": "arxiv",
        "metadata_source_note": "arXiv page: submitted 2019, last revised 2020.",
    },
    {
        "citation_key": "barber2020jackknife_plus",
        "entry_type": "misc",
        "title": "Predictive inference with the jackknife+",
        "authors": [
            "Barber, Rina Foygel",
            "Candes, Emmanuel J.",
            "Ramdas, Aaditya",
            "Tibshirani, Ryan J.",
        ],
        "year": "2020",
        "url": "https://arxiv.org/abs/1905.02928",
        "doi": "10.48550/arXiv.1905.02928",
        "eprint": "1905.02928",
        "archive_prefix": "arXiv",
        "source_kind": "arxiv",
        "metadata_source_note": "arXiv page: submitted 2019, last revised 2020.",
    },
    {
        "citation_key": "romano2019conformalized_quantile_regression",
        "entry_type": "misc",
        "title": "Conformalized Quantile Regression",
        "authors": [
            "Romano, Yaniv",
            "Patterson, Evan",
            "Candes, Emmanuel J.",
        ],
        "year": "2019",
        "url": "https://arxiv.org/abs/1905.03222",
        "doi": "10.48550/arXiv.1905.03222",
        "eprint": "1905.03222",
        "archive_prefix": "arXiv",
        "source_kind": "arxiv",
        "metadata_source_note": "arXiv page: submitted 2019.",
    },
    {
        "citation_key": "chernozhukov2021distributional_conformal",
        "entry_type": "article",
        "title": "Distributional conformal prediction",
        "authors": [
            "Chernozhukov, Victor",
            "Wuthrich, Kaspar",
            "Zhu, Yinchu",
        ],
        "year": "2021",
        "journal": "Proceedings of the National Academy of Sciences",
        "volume": "118",
        "number": "48",
        "pages": "e2107794118",
        "url": "https://arxiv.org/abs/1909.07889",
        "doi": "10.48550/arXiv.1909.07889",
        "eprint": "1909.07889",
        "archive_prefix": "arXiv",
        "source_kind": "arxiv",
        "metadata_source_note": "arXiv page with PNAS journal reference.",
    },
    {
        "citation_key": "vovk2019efficient_predictive_distributions",
        "entry_type": "misc",
        "title": "Computationally efficient versions of conformal predictive distributions",
        "authors": [
            "Vovk, Vladimir",
            "Petej, Ivan",
            "Nouretdinov, Ilia",
            "Manokhin, Valery",
            "Gammerman, Alex",
        ],
        "year": "2019",
        "url": "https://arxiv.org/abs/1911.00941",
        "doi": "10.48550/arXiv.1911.00941",
        "eprint": "1911.00941",
        "archive_prefix": "arXiv",
        "source_kind": "arxiv",
        "metadata_source_note": "arXiv page: submitted 2019.",
    },
    {
        "citation_key": "kim2020jackknife_after_bootstrap",
        "entry_type": "misc",
        "title": "Predictive Inference Is Free with the Jackknife+-after-Bootstrap",
        "authors": [
            "Kim, Byol",
            "Xu, Chen",
            "Barber, Rina Foygel",
        ],
        "year": "2020",
        "url": "https://arxiv.org/abs/2002.09025",
        "doi": "10.48550/arXiv.2002.09025",
        "eprint": "2002.09025",
        "archive_prefix": "arXiv",
        "source_kind": "arxiv",
        "metadata_source_note": "arXiv page: submitted and last revised in 2020.",
    },
    {
        "citation_key": "angelopoulos2025conformal_risk_control",
        "entry_type": "misc",
        "title": "Conformal Risk Control",
        "authors": [
            "Angelopoulos, Anastasios N.",
            "Bates, Stephen",
            "Fisch, Adam",
            "Lei, Lihua",
            "Schuster, Tal",
        ],
        "year": "2025",
        "url": "https://arxiv.org/abs/2208.02814",
        "doi": "10.48550/arXiv.2208.02814",
        "eprint": "2208.02814",
        "archive_prefix": "arXiv",
        "source_kind": "arxiv",
        "metadata_source_note": "arXiv page: submitted 2022, last revised 2025.",
    },
    {
        "citation_key": "wang2026tail_allocation",
        "entry_type": "misc",
        "title": "Tail allocation for conformal prediction intervals",
        "authors": ["Wang, Tianying"],
        "year": "2026",
        "url": "https://arxiv.org/abs/2604.25202",
        "doi": "10.48550/arXiv.2604.25202",
        "eprint": "2604.25202",
        "archive_prefix": "arXiv",
        "source_kind": "arxiv",
        "metadata_source_note": "arXiv page: submitted 2026.",
    },
    {
        "citation_key": "cuonzo2026tail_specific_intervals",
        "entry_type": "misc",
        "title": "Conformal Prediction Intervals with Tail-Specific Guarantees",
        "authors": [
            "Cuonzo, Simone",
            "Deliu, Nina",
        ],
        "year": "2026",
        "url": "https://arxiv.org/abs/2606.18199",
        "doi": "10.48550/arXiv.2606.18199",
        "eprint": "2606.18199",
        "archive_prefix": "arXiv",
        "source_kind": "arxiv",
        "metadata_source_note": "arXiv page: submitted 2026.",
    },
    {
        "citation_key": "petej2026inductive_venn_abers_regressors",
        "entry_type": "misc",
        "title": "Inductive Venn-Abers and related regressors",
        "authors": [
            "Petej, Ivan",
            "Vovk, Vladimir",
        ],
        "year": "2026",
        "url": "https://arxiv.org/html/2605.06646v1",
        "eprint": "2605.06646",
        "archive_prefix": "arXiv",
        "source_kind": "arxiv_html",
        "metadata_source_note": "arXiv HTML page: version 1, submitted 2026.",
    },
    {
        "citation_key": "vovk2017nonparametric_predictive_distributions",
        "entry_type": "inproceedings",
        "title": "Nonparametric predictive distributions based on conformal prediction",
        "authors": [
            "Vovk, Vladimir",
            "Shen, Jieli",
            "Manokhin, Valery",
            "Xie, Min-ge",
        ],
        "year": "2017",
        "booktitle": (
            "Proceedings of the Sixth Workshop on Conformal and Probabilistic "
            "Prediction and Applications"
        ),
        "pages": "82--102",
        "volume": "60",
        "series": "Proceedings of Machine Learning Research",
        "publisher": "PMLR",
        "url": "https://proceedings.mlr.press/v60/vovk17a.html",
        "source_kind": "pmlr",
        "metadata_source_note": "PMLR volume 60 page.",
    },
    {
        "citation_key": "nouretdinov2018ivapd",
        "entry_type": "inproceedings",
        "title": "Inductive Venn-Abers predictive distribution",
        "authors": [
            "Nouretdinov, Ilia",
            "Volkhonskiy, Denis",
            "Lim, Pitt",
            "Toccaceli, Paolo",
            "Gammerman, Alexander",
        ],
        "year": "2018",
        "booktitle": (
            "Proceedings of the Seventh Workshop on Conformal and Probabilistic "
            "Prediction and Applications"
        ),
        "pages": "15--36",
        "volume": "91",
        "series": "Proceedings of Machine Learning Research",
        "publisher": "PMLR",
        "url": "https://proceedings.mlr.press/v91/nouretdinov18a.html",
        "source_kind": "pmlr",
        "metadata_source_note": "PMLR volume 91 page.",
    },
    {
        "citation_key": "nouretdinov2024ivapd_applications",
        "entry_type": "inproceedings",
        "title": "Inductive Venn-Abers Predictive Distributions: New Applications & Evaluation",
        "authors": [
            "Nouretdinov, Ilia",
            "Gammerman, James",
        ],
        "year": "2024",
        "booktitle": (
            "Proceedings of the Thirteenth Symposium on Conformal and "
            "Probabilistic Prediction with Applications"
        ),
        "pages": "490--507",
        "volume": "230",
        "series": "Proceedings of Machine Learning Research",
        "publisher": "PMLR",
        "url": "https://proceedings.mlr.press/v230/nouretdinov24a.html",
        "source_kind": "pmlr",
        "metadata_source_note": "PMLR volume 230 page.",
    },
    {
        "citation_key": "vanderlaan2025generalized_venn_abers",
        "entry_type": "inproceedings",
        "title": (
            "Generalized Venn and Venn-Abers Calibration with Applications "
            "in Conformal Prediction"
        ),
        "authors": [
            "Van Der Laan, Lars",
            "Alaa, Ahmed",
        ],
        "year": "2025",
        "booktitle": "Proceedings of the 42nd International Conference on Machine Learning",
        "pages": "60748--60763",
        "volume": "267",
        "series": "Proceedings of Machine Learning Research",
        "publisher": "PMLR",
        "url": "https://proceedings.mlr.press/v267/van-der-laan25a.html",
        "source_kind": "pmlr",
        "metadata_source_note": "PMLR volume 267 page.",
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    parser.add_argument(
        "--bib-out", default=str(DEFAULT_BIB_OUT), help="Output BibTeX path."
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def collect_primer_urls(payload: dict[str, Any]) -> dict[str, set[str]]:
    by_url: dict[str, set[str]] = {}
    for row in payload.get("concept_rows") or []:
        concept_id = str(row.get("concept_id") or "").strip()
        for url in row.get("primary_source_urls") or []:
            by_url.setdefault(str(url), set()).add(concept_id)
    return by_url


def collect_literature_urls(payload: dict[str, Any]) -> dict[str, set[str]]:
    by_url: dict[str, set[str]] = {}
    for row in payload.get("requirements") or []:
        requirement_id = str(row.get("requirement_id") or "").strip()
        for url, ok in (row.get("source_url_status") or {}).items():
            if ok:
                by_url.setdefault(str(url), set()).add(requirement_id)
    return by_url


def escape_bibtex(value: str) -> str:
    return value.replace("&", r"\&")


def format_bibtex(row: dict[str, Any]) -> str:
    fields: list[tuple[str, str]] = [
        ("author", " and ".join(row["authors"])),
        ("title", row["title"]),
        ("year", row["year"]),
    ]
    for field in [
        "journal",
        "booktitle",
        "volume",
        "number",
        "pages",
        "series",
        "publisher",
        "doi",
        "eprint",
        "archive_prefix",
        "url",
    ]:
        value = row.get(field)
        if value:
            bib_field = "archivePrefix" if field == "archive_prefix" else field
            fields.append((bib_field, str(value)))
    lines = [f"@{row['entry_type']}{{{row['citation_key']},"]
    for index, (field, value) in enumerate(fields):
        suffix = "," if index < len(fields) - 1 else ""
        lines.append(f"  {field} = {{{escape_bibtex(value)}}}{suffix}")
    lines.append("}")
    return "\n".join(lines)


def build_payload(root: Path) -> dict[str, Any]:
    primer = read_json(root / READER_METHOD_PRIMER)
    literature = read_json(root / METHOD_LITERATURE_AUDIT)
    primer_urls = collect_primer_urls(primer)
    literature_urls = collect_literature_urls(literature)
    expected_urls = set(primer_urls) | set(literature_urls)
    registry_urls = {row["url"] for row in CITATION_ROWS}
    citation_keys = [row["citation_key"] for row in CITATION_ROWS]
    duplicate_keys = sorted(
        {key for key in citation_keys if citation_keys.count(key) > 1}
    )
    missing_expected_urls = sorted(expected_urls - registry_urls)
    extra_registry_urls = sorted(registry_urls - expected_urls)
    incomplete_rows = []
    enriched_rows = []
    for row in CITATION_ROWS:
        covered_concepts = sorted(primer_urls.get(row["url"], set()))
        covered_requirements = sorted(literature_urls.get(row["url"], set()))
        source_role_parts = []
        if covered_concepts:
            source_role_parts.append("primer")
        if covered_requirements:
            source_role_parts.append("literature")
        source_role = "_and_".join(source_role_parts) if source_role_parts else "unlinked"
        required_fields = ["citation_key", "entry_type", "title", "authors", "year", "url"]
        missing = [field for field in required_fields if not row.get(field)]
        if not covered_concepts and not covered_requirements:
            missing.append("upstream_url_link")
        enriched = {
            **row,
            "covered_primer_concept_ids": covered_concepts,
            "covered_literature_requirement_ids": covered_requirements,
            "source_role": source_role,
            "bibtex": format_bibtex(row),
            "claim_use_boundary": (
                "Citation metadata only; this row does not authorize empirical "
                "claims, method recommendations, final prose, or positive "
                "method promotion."
            ),
        }
        enriched_rows.append(enriched)
        if missing:
            incomplete_rows.append(
                {"citation_key": row.get("citation_key"), "missing": missing}
            )
    checks = [
        {
            "check_id": "primer_primary_urls_all_covered",
            "status": "pass" if set(primer_urls).issubset(registry_urls) else "fail",
            "evidence": {
                "primer_primary_url_count": len(primer_urls),
                "covered_count": len(set(primer_urls) & registry_urls),
                "missing_urls": sorted(set(primer_urls) - registry_urls),
            },
            "blocker": "primer_urls_missing_registry_rows",
        },
        {
            "check_id": "literature_primary_urls_all_covered",
            "status": (
                "pass" if set(literature_urls).issubset(registry_urls) else "fail"
            ),
            "evidence": {
                "literature_primary_url_count": len(literature_urls),
                "covered_count": len(set(literature_urls) & registry_urls),
                "missing_urls": sorted(set(literature_urls) - registry_urls),
            },
            "blocker": "literature_urls_missing_registry_rows",
        },
        {
            "check_id": "citation_keys_unique",
            "status": "pass" if not duplicate_keys else "fail",
            "evidence": {
                "citation_key_count": len(citation_keys),
                "unique_citation_key_count": len(set(citation_keys)),
                "duplicate_keys": duplicate_keys,
            },
            "blocker": "duplicate_citation_keys",
        },
        {
            "check_id": "registry_urls_exactly_match_upstream_union",
            "status": (
                "pass" if not missing_expected_urls and not extra_registry_urls else "fail"
            ),
            "evidence": {
                "expected_url_count": len(expected_urls),
                "registry_url_count": len(registry_urls),
                "missing_expected_urls": missing_expected_urls,
                "extra_registry_urls": extra_registry_urls,
            },
            "blocker": "registry_url_set_mismatch",
        },
        {
            "check_id": "citation_rows_complete",
            "status": "pass" if not incomplete_rows else "fail",
            "evidence": {
                "citation_row_count": len(enriched_rows),
                "incomplete_rows": incomplete_rows,
            },
            "blocker": "citation_rows_incomplete",
        },
        {
            "check_id": "final_outputs_remain_blocked",
            "status": "pass",
            "evidence": {
                "final_manuscript_prose_permission": False,
                "method_recommendation_authorized": False,
                "method_champion_authorized": False,
                "method_advocacy_authorized": False,
                "positive_claim_promotion_authorized": False,
            },
            "blocker": "citation_registry_authorized_final_claims",
        },
    ]
    failed_checks = [row for row in checks if row["status"] != "pass"]
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "reader_method_primer_citation_map": rel(root / READER_METHOD_PRIMER, root),
            "method_literature_coverage_audit": rel(root / METHOD_LITERATURE_AUDIT, root),
        },
        "summary": {
            "overall_status": (
                "publication_citation_registry_ready_no_final_prose"
                if not failed_checks
                else "publication_citation_registry_blocked"
            ),
            "phase_state": "pre_prose_citation_metadata_registry_final_outputs_blocked",
            "citation_row_count": len(enriched_rows),
            "bibtex_entry_count": len(enriched_rows),
            "primer_primary_url_count": len(primer_urls),
            "primer_primary_url_covered_count": len(set(primer_urls) & registry_urls),
            "literature_primary_url_count": len(literature_urls),
            "literature_primary_url_covered_count": len(
                set(literature_urls) & registry_urls
            ),
            "expected_upstream_url_count": len(expected_urls),
            "registry_url_count": len(registry_urls),
            "final_manuscript_prose_permission": False,
            "method_recommendation_authorized": False,
            "method_champion_authorized": False,
            "method_advocacy_authorized": False,
            "positive_claim_promotion_authorized": False,
            "result_reporting_policy": (
                "analysis_only_report_observed_behavior_no_method_advocacy"
            ),
            "failed_check_count": len(failed_checks),
        },
        "citation_rows": enriched_rows,
        "checks": checks,
        "failed_checks": failed_checks,
        "claim_boundaries": [
            "This registry is citation metadata, not manuscript prose.",
            "A citation row proves source traceability only; it does not prove an empirical result.",
            "The registry does not recommend CQR, CV+, Venn-Abers, or any other method.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Publication Citation Registry",
        "",
        "This pre-prose artifact maps audited conformal-prediction source URLs to stable citation keys and BibTeX entries. It does not draft final manuscript text or authorize a method recommendation.",
        "",
        "## Summary",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Phase state: `{summary['phase_state']}`",
        f"- Citation rows: {summary['citation_row_count']}",
        f"- BibTeX entries: {summary['bibtex_entry_count']}",
        f"- Primer URLs covered: {summary['primer_primary_url_covered_count']} / {summary['primer_primary_url_count']}",
        f"- Literature URLs covered: {summary['literature_primary_url_covered_count']} / {summary['literature_primary_url_count']}",
        f"- Final prose authorized: `{summary['final_manuscript_prose_permission']}`",
        f"- Method recommendation authorized: `{summary['method_recommendation_authorized']}`",
        f"- Positive-claim promotion authorized: `{summary['positive_claim_promotion_authorized']}`",
        f"- Failed checks: {summary['failed_check_count']}",
        "",
        "## Citation Rows",
        "",
        "| Citation key | Type | Year | Source role | Upstream links | URL |",
        "|---|---:|---:|---|---|---|",
    ]
    for row in payload["citation_rows"]:
        upstream = (
            f"{len(row['covered_primer_concept_ids'])} primer concepts; "
            f"{len(row['covered_literature_requirement_ids'])} literature requirements"
        )
        lines.append(
            "| `{}` | `{}` | {} | `{}` | {} | {} |".format(
                row["citation_key"],
                row["entry_type"],
                row["year"],
                row["source_role"],
                upstream,
                row["url"],
            )
        )
    lines.extend(["", "## Claim Boundaries", ""])
    for boundary in payload["claim_boundaries"]:
        lines.append(f"- {boundary}")
    return "\n".join(lines) + "\n"


def render_bibtex(payload: dict[str, Any]) -> str:
    return "\n\n".join(row["bibtex"] for row in payload["citation_rows"]) + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out = root / args.out
    bib_out = root / args.bib_out
    payload = build_payload(root)
    atomic_write_json(out, payload)
    atomic_write_text(out.with_suffix(".md"), render_markdown(payload))
    atomic_write_text(bib_out, render_bibtex(payload))
    print(
        json.dumps(
            {
                "status": "ok",
                "out": rel(out, root),
                "bib_out": rel(bib_out, root),
                "overall_status": payload["summary"]["overall_status"],
                "citation_row_count": payload["summary"]["citation_row_count"],
                "failed_check_count": payload["summary"]["failed_check_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
