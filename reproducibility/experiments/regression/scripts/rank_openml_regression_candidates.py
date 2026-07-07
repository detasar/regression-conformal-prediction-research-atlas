"""Rank OpenML regression discoveries for manual source review."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from cpfi.regression.experiment import atomic_write_text


THEME_TERMS = {
    "income_wage_salary": ["income", "wage", "salary"],
    "education_score": ["gpa", "grade", "score", "iq"],
    "housing_price": ["house", "housing", "price", "rent"],
    "crime": ["crime", "violentcrimes"],
    "health_medical": ["health", "medical", "hema", "cells"],
    "age": ["age"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--discovery",
        default="experiments/regression/catalogs/openml_feature_discovery.jsonl",
    )
    parser.add_argument(
        "--out-jsonl",
        default="experiments/regression/catalogs/openml_ranked_candidates.jsonl",
    )
    parser.add_argument(
        "--out-md",
        default="experiments/regression/catalogs/openml_ranked_candidates.md",
    )
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def themes_for(record: dict) -> list[str]:
    text = " ".join(
        str(record.get(key, "")) for key in ["name", "target_feature"]
    ).lower()
    tokens = [token for token in re.split(r"[^a-z0-9]+", text) if token]
    themes = []
    for theme, terms in THEME_TERMS.items():
        if any(term_matches_token(term, token) for term in terms for token in tokens):
            themes.append(theme)
    return themes


def term_matches_token(term: str, token: str) -> bool:
    if term in {"age", "rent"}:
        return token == term or token.startswith(term)
    if term in {"house", "housing"}:
        return token.startswith(term)
    if term == "price":
        return token == term or token.endswith(term)
    if term in {"crime", "violentcrimes"}:
        return term in token
    return token == term or term in token


def score_record(record: dict) -> dict:
    themes = themes_for(record)
    sensitive_hits = record.get("sensitive_name_hits") or []
    if is_deprioritized_feature_bag(record):
        review_status = "not_ranked"
        priority_score = 0
    elif sensitive_hits:
        review_status = "source_review_required_sensitive_name_hit"
        priority_score = 100 + len(sensitive_hits) * 10 + len(themes)
    elif themes:
        review_status = "benchmark_source_review_required"
        priority_score = 10 + len(themes)
    else:
        review_status = "not_ranked"
        priority_score = 0

    return {
        "openml_id": record.get("openml_id"),
        "name": record.get("name"),
        "source_url": record.get("source_url"),
        "target_feature": record.get("target_feature"),
        "n_instances": record.get("n_instances"),
        "n_features": record.get("n_features"),
        "n_missing_values": record.get("n_missing_values"),
        "sensitive_name_hits": sensitive_hits,
        "themes": themes,
        "feature_names_sample": record.get("feature_names_sample", [])[:20],
        "review_status": review_status,
        "priority_score": priority_score,
        "notes": (
            "Word-count or high-dimensional feature-bag names can contain sensitive words without tabular protected columns."
            if is_deprioritized_feature_bag(record)
            else
            "Feature names require source-level review before fairness use."
            if themes or sensitive_hits
            else ""
        ),
    }


def is_deprioritized_feature_bag(record: dict) -> bool:
    name = str(record.get("name", "")).lower()
    if name.endswith(".wc"):
        return True
    n_features = record.get("n_features")
    target = str(record.get("target_feature", "")).lower()
    try:
        feature_count = float(n_features)
    except (TypeError, ValueError):
        feature_count = 0.0
    return feature_count > 1000 and target == "class" and not themes_for(record)


def render_markdown(records: list[dict], total_rows: int) -> str:
    ranked = [record for record in records if record["review_status"] != "not_ranked"]
    lines = [
        "# Ranked OpenML Regression Candidate Review",
        "",
        f"- Source discovery rows: {total_rows}",
        f"- Ranked rows requiring manual review: {len(ranked)}",
        "- Ranking is based on target/name themes and sensitive-name hits only;",
        "  feature semantics still require manual source review before modeling.",
        "",
        "| OpenML id | Name | Target | Rows | Missing | Themes | Review status |",
        "|---:|---|---|---:|---:|---|---|",
    ]
    for record in ranked:
        lines.append(
            "| {openml_id} | {name} | {target_feature} | {n_instances} | "
            "{n_missing_values} | {themes} | {review_status} |".format(
                **{
                    **record,
                    "themes": ", ".join(record["themes"]),
                }
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    rows = read_jsonl(Path(args.discovery))
    records = sorted(
        (score_record(row) for row in rows),
        key=lambda item: (-item["priority_score"], str(item["name"]), int(item["openml_id"])),
    )
    ranked = [record for record in records if record["review_status"] != "not_ranked"]
    jsonl_text = "".join(json.dumps(record, sort_keys=True) + "\n" for record in ranked)
    atomic_write_text(Path(args.out_jsonl), jsonl_text)
    atomic_write_text(Path(args.out_md), render_markdown(records, total_rows=len(rows)))
    print(json.dumps({"status": "ok", "ranked": len(ranked), "source_rows": len(rows)}))


if __name__ == "__main__":
    main()
