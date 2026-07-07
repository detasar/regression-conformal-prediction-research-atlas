"""Build a bundle-level manuscript eligibility matrix.

This is a manuscript-control artifact, not a result table. It joins the
publication bundle index, claim evidence view, and paper-readiness map so that
future drafting can distinguish descriptive, robustness, and blocked main-result
surfaces without hand-interpreting Markdown manifests.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_regression_manuscript_bundle_eligibility_matrix_v1"
DEFAULT_OUT = Path("experiments/regression/manuscript/bundle_eligibility_matrix.json")
BUNDLE_INDEX = Path("experiments/regression/catalogs/manuscript_bundle_index.json")
CLAIM_REGISTER = Path("experiments/regression/catalogs/manuscript_claim_register.json")
EVIDENCE_VIEW = Path("experiments/regression/manuscript/evidence_view.json")
READINESS_MAP = Path("experiments/regression/manuscript/paper_readiness_map.json")
PUBLICATION_METHODOLOGY = Path(
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "publication_methodology_audit.json"
)

SURFACE_IDS = (
    "dataset_table",
    "main_results_table",
    "robustness_results_table",
    "negative_results_table",
    "methodology_appendix",
    "reproducibility_appendix",
)


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


def rows_by_bundle(evidence_view: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_bundle: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evidence_view.get("rows", []) or []:
        if not isinstance(row, dict):
            continue
        for bundle_id in row.get("bundle_ids", []) or []:
            if bundle_id:
                by_bundle[str(bundle_id)].append(row)
    return dict(by_bundle)


def claim_status_by_id(claim_register: dict[str, Any]) -> dict[str, str]:
    statuses = {}
    for claim in claim_register.get("claims", []) or []:
        if isinstance(claim, dict) and claim.get("claim_id"):
            statuses[str(claim["claim_id"])] = str(claim.get("status") or "")
    return statuses


def surface_statuses(readiness_map: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("surface_id")): row
        for row in readiness_map.get("paper_surfaces", []) or []
        if isinstance(row, dict) and row.get("surface_id")
    }


def gate_statuses(readiness_map: dict[str, Any]) -> dict[str, str]:
    return {
        str(row.get("gate_id")): str(row.get("status"))
        for row in readiness_map.get("blocked_gates", []) or []
        if isinstance(row, dict) and row.get("gate_id")
    }


def manifest_node_id(manifest_path: str) -> str:
    return f"manifest:{Path(manifest_path).parent.name}:publication_readiness"


def has_caveat(bundle: dict[str, Any]) -> bool:
    text = " ".join(
        str(value)
        for value in (
            bundle.get("status"),
            bundle.get("paper_table_candidate"),
            bundle.get("claim_scope"),
            " ".join(str(item) for item in bundle.get("promotion_blockers", []) or []),
        )
    ).lower()
    return "caveat" in text or bool(bundle.get("promotion_blockers"))


def surface_eligibility(
    bundle: dict[str, Any],
    *,
    manifest_present: bool,
    paper_surfaces: dict[str, dict[str, Any]],
    blocked_gates: dict[str, str],
) -> dict[str, dict[str, Any]]:
    candidate = str(bundle.get("paper_table_candidate") or "")
    evidence_role = str(bundle.get("evidence_role") or "")
    status = str(bundle.get("status") or "")
    completed = status.startswith("completed")
    robustness_candidate = (
        completed
        and evidence_role == "robustness"
        and candidate.startswith("robustness_results_table")
        and manifest_present
    )
    main_blockers = [
        gate
        for gate in (
            "final_method_model_selection_gate",
            "multiplicity_selection_record",
            "dataset_specific_final_gates",
        )
        if blocked_gates.get(gate) == "blocked"
    ]
    matrix = {
        "dataset_table": {
            "eligible": manifest_present,
            "status": "descriptive_only" if manifest_present else "blocked",
            "reason": (
                "Manifested dataset bundle can support descriptive extraction only."
                if manifest_present
                else "Manifest path is missing from the current workspace."
            ),
            "blocking_gates": [],
        },
        "main_results_table": {
            "eligible": False,
            "status": "blocked",
            "reason": "Bundle is not a final main-result bundle and global final-selection gates remain blocked.",
            "blocking_gates": main_blockers,
        },
        "robustness_results_table": {
            "eligible": robustness_candidate,
            "status": (
                "eligible_with_caveats"
                if robustness_candidate and has_caveat(bundle)
                else "eligible"
                if robustness_candidate
                else "not_applicable"
            ),
            "reason": (
                "Bundle is scoped robustness evidence and must carry its manifest caveats."
                if robustness_candidate and has_caveat(bundle)
                else "Bundle is scoped robustness evidence."
                if robustness_candidate
                else "Bundle is not indexed as a robustness-table candidate."
            ),
            "blocking_gates": [],
        },
        "negative_results_table": {
            "eligible": candidate == "negative_results_table",
            "status": (
                "eligible"
                if candidate == "negative_results_table"
                else "not_applicable"
            ),
            "reason": (
                "Bundle is explicitly indexed as negative-result evidence."
                if candidate == "negative_results_table"
                else "Negative-result evidence is currently claim-level rather than bundle-level."
            ),
            "blocking_gates": [],
        },
        "methodology_appendix": {
            "eligible": manifest_present,
            "status": "eligible_with_caveats" if manifest_present else "blocked",
            "reason": "Manifest can be cited in methodology/reproducibility prose with claim boundaries.",
            "blocking_gates": [],
        },
        "reproducibility_appendix": {
            "eligible": manifest_present,
            "status": "eligible_with_caveats" if manifest_present else "blocked",
            "reason": "Manifest path, config, report directory, and ledger policy can support reproducibility notes.",
            "blocking_gates": [],
        },
    }
    for surface_id, surface in paper_surfaces.items():
        if surface_id in matrix:
            matrix[surface_id]["surface_status"] = surface.get("status")
    return matrix


def build_payload(root: Path) -> dict[str, Any]:
    bundle_index_path = root / BUNDLE_INDEX
    claim_register_path = root / CLAIM_REGISTER
    evidence_view_path = root / EVIDENCE_VIEW
    readiness_map_path = root / READINESS_MAP
    publication_path = root / PUBLICATION_METHODOLOGY

    bundle_index = read_json(bundle_index_path)
    claim_register = read_json(claim_register_path)
    evidence_view = read_json(evidence_view_path)
    readiness_map = read_json(readiness_map_path)
    publication = read_json(publication_path)

    evidence_by_bundle = rows_by_bundle(evidence_view)
    claim_statuses = claim_status_by_id(claim_register)
    paper_surfaces = surface_statuses(readiness_map)
    blocked_gates = gate_statuses(readiness_map)
    rows: list[dict[str, Any]] = []

    for bundle in bundle_index.get("bundles", []) or []:
        if not isinstance(bundle, dict) or not bundle.get("bundle_id"):
            continue
        bundle_id = str(bundle["bundle_id"])
        manifest_path = str(bundle.get("manifest_path") or "")
        manifest_present = bool(manifest_path) and (root / manifest_path).exists()
        evidence_rows = evidence_by_bundle.get(bundle_id, [])
        linked_claim_ids = [
            str(row.get("claim_id")) for row in evidence_rows if row.get("claim_id")
        ]
        linked_claim_statuses = {
            str(row["claim_id"]): claim_statuses.get(
                str(row["claim_id"]),
                str(row.get("status") or ""),
            )
            for row in evidence_rows
            if row.get("claim_id")
        }
        eligibility = surface_eligibility(
            bundle,
            manifest_present=manifest_present,
            paper_surfaces=paper_surfaces,
            blocked_gates=blocked_gates,
        )
        rows.append(
            {
                "bundle_id": bundle_id,
                "dataset_id": bundle.get("dataset_id"),
                "paired_dataset_id": bundle.get("paired_dataset_id"),
                "target": bundle.get("target"),
                "target_transform": bundle.get("target_transform"),
                "diagnostic_group": bundle.get("diagnostic_group"),
                "evidence_role": bundle.get("evidence_role"),
                "status": bundle.get("status"),
                "paper_table_candidate": bundle.get("paper_table_candidate"),
                "manifest_path": manifest_path,
                "manifest_node_id": manifest_node_id(manifest_path) if manifest_path else None,
                "manifest_present": manifest_present,
                "claim_scope": bundle.get("claim_scope"),
                "linked_claim_ids": linked_claim_ids,
                "linked_claim_statuses": linked_claim_statuses,
                "promotion_blockers": bundle.get("promotion_blockers", []) or [],
                "promotion_blocker_count": len(bundle.get("promotion_blockers", []) or []),
                "requires_caveat_label": has_caveat(bundle),
                "surface_eligibility": eligibility,
                "eligible_surface_ids": [
                    surface_id
                    for surface_id, surface in eligibility.items()
                    if surface.get("eligible") is True
                ],
                "blocked_surface_ids": [
                    surface_id
                    for surface_id, surface in eligibility.items()
                    if surface.get("status") == "blocked"
                ],
            }
        )

    table_counts = Counter(str(row.get("paper_table_candidate") or "") for row in rows)
    robustness_rows = [
        row
        for row in rows
        if row["surface_eligibility"]["robustness_results_table"]["eligible"]
    ]
    main_rows = [
        row
        for row in rows
        if row["surface_eligibility"]["main_results_table"]["eligible"]
    ]
    unlinked_rows = [row for row in rows if not row["linked_claim_ids"]]
    missing_manifest_rows = [row for row in rows if not row["manifest_present"]]
    final_claim_status = (readiness_map.get("summary") or {}).get(
        "final_selection_claim_status"
    )
    overall_status = (
        "bundle_eligibility_matrix_ready_no_final_claims"
        if rows
        and not main_rows
        and not missing_manifest_rows
        and final_claim_status == "blocked"
        else "bundle_eligibility_matrix_review_required"
    )

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "bundle_index": rel(bundle_index_path, root),
            "claim_register": rel(claim_register_path, root),
            "evidence_view": rel(evidence_view_path, root),
            "paper_readiness_map": rel(readiness_map_path, root),
            "publication_methodology": rel(publication_path, root),
        },
        "summary": {
            "overall_status": overall_status,
            "bundle_count": len(rows),
            "manifest_present_count": sum(row["manifest_present"] for row in rows),
            "missing_manifest_count": len(missing_manifest_rows),
            "claim_linked_bundle_count": len(rows) - len(unlinked_rows),
            "unlinked_bundle_count": len(unlinked_rows),
            "robustness_candidate_count": len(robustness_rows),
            "caveated_robustness_candidate_count": sum(
                row["requires_caveat_label"] for row in robustness_rows
            ),
            "main_results_eligible_count": len(main_rows),
            "final_claim_eligible_count": 0,
            "promotion_blocker_count": sum(row["promotion_blocker_count"] for row in rows),
            "table_candidate_counts": dict(sorted(table_counts.items())),
            "final_selection_claim_status": final_claim_status,
            "publication_methodology_status": (publication.get("summary") or {}).get(
                "overall_status"
            ),
            "paper_readiness_status": (readiness_map.get("summary") or {}).get(
                "overall_status"
            ),
        },
        "claim_boundaries": [
            "This matrix controls table eligibility; it is not a result table.",
            "Main-result and final-selection eligibility remains false while global final-selection gates are blocked.",
            "Robustness eligibility is scoped to each bundle manifest and must carry caveat labels.",
        ],
        "surface_ids": list(SURFACE_IDS),
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Bundle Eligibility Matrix",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Bundles: {summary['bundle_count']}",
        f"- Manifests present: {summary['manifest_present_count']} / {summary['bundle_count']}",
        f"- Claim-linked bundles: {summary['claim_linked_bundle_count']} / {summary['bundle_count']}",
        f"- Robustness candidates: {summary['robustness_candidate_count']} ({summary['caveated_robustness_candidate_count']} caveated)",
        f"- Main-results eligible rows: {summary['main_results_eligible_count']}",
        f"- Final-claim eligible rows: {summary['final_claim_eligible_count']}",
        f"- Final-selection claim status: `{summary['final_selection_claim_status']}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Bundle Rows",
            "",
            "| Bundle | Dataset | Status | Candidate table | Robustness | Main results | Caveat label | Linked claims |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        robustness = row["surface_eligibility"]["robustness_results_table"]["status"]
        main = row["surface_eligibility"]["main_results_table"]["status"]
        linked = ", ".join(f"`{claim_id}`" for claim_id in row["linked_claim_ids"]) or "none"
        lines.append(
            "| "
            f"`{row['bundle_id']}` | "
            f"`{row['dataset_id']}` | "
            f"`{row['status']}` | "
            f"`{row['paper_table_candidate']}` | "
            f"`{robustness}` | "
            f"`{main}` | "
            f"`{row['requires_caveat_label']}` | "
            f"{linked} |"
        )
    lines.extend(
        [
            "",
            "## Promotion Blocker Samples",
            "",
        ]
    )
    for row in payload["rows"]:
        blockers = row["promotion_blockers"][:2]
        if not blockers:
            continue
        lines.append(f"### `{row['bundle_id']}`")
        for blocker in blockers:
            lines.append(f"- {blocker}")
        lines.append("")
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
                "status": "ok",
                "out": rel(out_path, root),
                **payload["summary"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
