"""Build a compact manuscript evidence extraction view.

This is a reader-facing index over the claim register, bundle index, and
knowledge graph. It does not rank methods or promote claims; it makes the
claim -> manifest -> report -> endpoint/caveat chain explicit before paper
drafting.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_manuscript_evidence_view_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/evidence_view.json")
CLAIM_REGISTER = Path("experiments/regression/catalogs/manuscript_claim_register.json")
BUNDLE_INDEX = Path("experiments/regression/catalogs/manuscript_bundle_index.json")
KNOWLEDGE_GRAPH = Path("experiments/regression/catalogs/knowledge_graph.json")


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


def manifest_node_id(manifest_path: str) -> str:
    report_name = Path(manifest_path).parent.name
    return f"manifest:{report_name}:publication_readiness"


def endpoint_counts(edges: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for edge in edges:
        if edge.get("relation") != "SUPPORTED_BY_ENDPOINT_AUDIT":
            continue
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if not target.startswith("report:"):
            continue
        if source.startswith("endpoint_result:"):
            counts[target]["endpoint_result_count"] += 1
        elif source.startswith("endpoint_caveat:"):
            counts[target]["endpoint_caveat_count"] += 1
        elif source.startswith("endpoint_state:"):
            counts[target]["endpoint_state_count"] += 1
    return {key: dict(value) for key, value in counts.items()}


def requirement_status_counts(claim: dict[str, Any]) -> dict[str, int]:
    return dict(
        sorted(
            Counter(
                str(requirement.get("status"))
                for requirement in claim.get("requirements", []) or []
                if isinstance(requirement, dict)
            ).items()
        )
    )


def build_payload(root: Path) -> dict[str, Any]:
    claim_register_path = root / CLAIM_REGISTER
    bundle_index_path = root / BUNDLE_INDEX
    kg_path = root / KNOWLEDGE_GRAPH
    claim_register = read_json(claim_register_path)
    bundle_index = read_json(bundle_index_path)
    kg = read_json(kg_path)
    endpoint_by_report = endpoint_counts(kg.get("edges", []) or [])

    bundles_by_manifest: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for bundle in bundle_index.get("bundles", []) or []:
        if not isinstance(bundle, dict) or not bundle.get("manifest_path"):
            continue
        bundles_by_manifest[manifest_node_id(str(bundle["manifest_path"]))].append(bundle)

    rows = []
    for claim in claim_register.get("claims", []) or []:
        if not isinstance(claim, dict) or not claim.get("claim_id"):
            continue
        supporting = [str(node_id) for node_id in claim.get("supporting_node_ids", []) or []]
        manifests = [node_id for node_id in supporting if node_id.startswith("manifest:")]
        reports = [node_id for node_id in supporting if node_id.startswith("report:")]
        endpoint_reports = [
            node_id
            for node_id in reports
            if node_id.endswith(":endpoint_audit") or node_id in endpoint_by_report
        ]
        endpoint_result_count = sum(
            endpoint_by_report.get(report, {}).get("endpoint_result_count", 0)
            for report in endpoint_reports
        )
        endpoint_caveat_count = sum(
            endpoint_by_report.get(report, {}).get("endpoint_caveat_count", 0)
            for report in endpoint_reports
        )
        endpoint_state_count = sum(
            endpoint_by_report.get(report, {}).get("endpoint_state_count", 0)
            for report in endpoint_reports
        )
        matched_bundles = [
            bundle
            for manifest in manifests
            for bundle in bundles_by_manifest.get(manifest, [])
        ]
        rows.append(
            {
                "claim_id": claim["claim_id"],
                "claim_type": claim.get("claim_type"),
                "status": claim.get("status"),
                "dataset_ids": claim.get("dataset_ids", []),
                "manifest_node_ids": manifests,
                "bundle_ids": [bundle.get("bundle_id") for bundle in matched_bundles],
                "bundle_statuses": sorted(
                    {
                        str(bundle.get("status"))
                        for bundle in matched_bundles
                        if bundle.get("status")
                    }
                ),
                "paper_table_candidates": sorted(
                    {
                        str(bundle.get("paper_table_candidate"))
                        for bundle in matched_bundles
                        if bundle.get("paper_table_candidate")
                    }
                ),
                "supporting_report_count": len(reports),
                "endpoint_audit_report_count": len(endpoint_reports),
                "endpoint_result_count": endpoint_result_count,
                "endpoint_caveat_count": endpoint_caveat_count,
                "endpoint_state_count": endpoint_state_count,
                "clean_endpoint_state_count": max(
                    endpoint_state_count - endpoint_caveat_count,
                    0,
                ),
                "requirement_status_counts": requirement_status_counts(claim),
                "blocking_node_count": len(claim.get("blocking_node_ids", []) or []),
                "not_claiming_count": len(claim.get("not_claiming", []) or []),
                "not_claiming_samples": (claim.get("not_claiming", []) or [])[:3],
                "promotion_blocker_count": sum(
                    len(bundle.get("promotion_blockers", []) or [])
                    for bundle in matched_bundles
                ),
                "promotion_blocker_samples": [
                    blocker
                    for bundle in matched_bundles
                    for blocker in (bundle.get("promotion_blockers", []) or [])
                ][:3],
            }
        )

    status_counts = Counter(row["status"] for row in rows)
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "claim_register": rel(claim_register_path, root),
            "bundle_index": rel(bundle_index_path, root),
            "knowledge_graph": rel(kg_path, root),
        },
        "summary": {
            "claim_count": len(rows),
            "status_counts": dict(sorted(status_counts.items())),
            "claims_with_manifest_count": sum(bool(row["manifest_node_ids"]) for row in rows),
            "claims_with_endpoint_evidence_count": sum(
                row["endpoint_audit_report_count"] > 0 for row in rows
            ),
            "endpoint_result_count": sum(row["endpoint_result_count"] for row in rows),
            "endpoint_caveat_count": sum(row["endpoint_caveat_count"] for row in rows),
            "clean_endpoint_state_count": sum(
                row["clean_endpoint_state_count"] for row in rows
            ),
        },
        "claim_boundaries": [
            "This view is an extraction index, not a manuscript result table.",
            "Rows inherit claim-register and manifest caveats; no final method/model is selected here.",
            "Endpoint counts are KG linkage summaries and do not imply bounded-support validity.",
        ],
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Manuscript Evidence View",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Claim count: {summary['claim_count']}",
        f"- Claims with manifests: {summary['claims_with_manifest_count']}",
        f"- Claims with endpoint evidence: {summary['claims_with_endpoint_evidence_count']}",
        f"- Endpoint result/caveat/clean-state counts: {summary['endpoint_result_count']} / {summary['endpoint_caveat_count']} / {summary['clean_endpoint_state_count']}",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Evidence Rows",
            "",
            "| Claim | Status | Bundles | Reports | Endpoint results | Endpoint caveats | Clean endpoint states | Table candidates |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            "| "
            f"`{row['claim_id']}` | "
            f"`{row['status']}` | "
            f"{len(row['bundle_ids'])} | "
            f"{row['supporting_report_count']} | "
            f"{row['endpoint_result_count']} | "
            f"{row['endpoint_caveat_count']} | "
            f"{row['clean_endpoint_state_count']} | "
            f"`{', '.join(row['paper_table_candidates'])}` |"
        )
    lines.extend(
        [
            "",
            "## Non-Claim Samples",
            "",
        ]
    )
    for row in payload["rows"]:
        samples = row["not_claiming_samples"] or row["promotion_blocker_samples"]
        if not samples:
            continue
        lines.append(f"### `{row['claim_id']}`")
        for sample in samples:
            lines.append(f"- {sample}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    out_path = resolve(root, args.out)
    payload = build_payload(root)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(json.dumps({"out": rel(out_path, root), **payload["summary"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
