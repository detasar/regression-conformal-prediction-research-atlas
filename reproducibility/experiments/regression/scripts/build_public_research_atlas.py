"""Validate the public Research Atlas HTML/data bundle."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def build_manifest(package_root: Path) -> dict[str, Any]:
    required = [
        "atlas/index.html",
        "atlas/scope/experiment_scope.json",
        "atlas/results/result_cube_public.csv",
        "atlas/datasets/dataset_catalog.json",
        "atlas/methods/method_ontology.json",
        "atlas/provenance/artifact_manifest.json",
        "atlas/provenance/hash_receipts.json",
        "atlas/provenance/index.html",
        "paper/research_document.html",
        "paper/article.html",
        "paper/supplement.html",
        "site/kg_browser.html",
        "site/kg_browser_data.json",
        "site/kg_browser_index.json",
        "site/kg_browser_edges.json",
        "evidence/public_artifact_manifest.json",
    ]
    missing = [rel for rel in required if not (package_root / rel).exists()]
    if missing:
        raise FileNotFoundError(f"Missing public atlas files: {missing}")
    kg = read_json(package_root / "site/kg_browser_data.json")
    scope = read_json(package_root / "atlas/scope/experiment_scope.json")
    source_manifest = read_json(package_root / "atlas/provenance/artifact_manifest.json")
    hash_receipts = read_json(package_root / "atlas/provenance/hash_receipts.json")
    provenance_html = (package_root / "atlas/provenance/index.html").read_text(encoding="utf-8")
    routes = kg.get("research_map", [])
    for fragment in [
        "Provenance Receipt Explorer",
        'id="provenance-explorer"',
        'id="source-receipt-table"',
        'id="hash-receipt-table"',
        "fetch('hash_receipts.json')",
        "../../evidence/public_artifact_manifest.json",
    ]:
        if fragment not in provenance_html:
            raise ValueError(f"Provenance explorer fragment missing: {fragment}")
    payload = {
        "schema": "regression_cp_public_research_atlas_manifest_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "required_file_count": len(required),
        "kg_node_count": len(kg.get("nodes", [])),
        "kg_edge_count": len(kg.get("edges", [])),
        "route_count": len(routes),
        "completed_rows": scope.get("publication_scoped_completed_rows"),
        "source_artifact_count": source_manifest.get("summary", {}).get("source_artifact_count"),
        "hash_receipt_count": len(hash_receipts.get("files", [])),
        "routes": [
            {
                "route_id": route.get("route_id"),
                "title": route.get("title"),
                "anchor_count": len(route.get("node_ids") or []),
            }
            for route in routes
            if isinstance(route, dict)
        ],
    }
    if not payload["route_count"]:
        raise ValueError("KG browser has no guided routes")
    if not payload["source_artifact_count"]:
        raise ValueError("Provenance source manifest is empty")
    if payload["hash_receipt_count"] < 200:
        raise ValueError("Hash receipt manifest is unexpectedly small")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", default=".")
    parser.add_argument(
        "--out",
        default="atlas/ui_data/public_research_atlas_manifest.json",
        help="Path relative to the package root.",
    )
    args = parser.parse_args()
    root = Path(args.package_root).resolve()
    payload = build_manifest(root)
    atomic_write_json(root / args.out, payload)
    print(json.dumps({"status": payload["status"], "out": args.out}, sort_keys=True))


if __name__ == "__main__":
    main()
