"""Validate and summarize the public Research Atlas release scope."""

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


def build_scope(package_root: Path) -> dict[str, Any]:
    scope_path = package_root / "atlas/scope/experiment_scope.json"
    kg_path = package_root / "site/kg_browser_data.json"
    manifest_path = package_root / "evidence/public_artifact_manifest.json"
    missing = [
        path.relative_to(package_root).as_posix()
        for path in (scope_path, kg_path, manifest_path)
        if not path.exists()
    ]
    if missing:
        raise FileNotFoundError(f"Missing Research Atlas files: {missing}")
    scope = read_json(scope_path)
    kg = read_json(kg_path)
    manifest = read_json(manifest_path)
    payload = {
        "schema": "regression_cp_public_release_scope_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "scope": {
            "completed_rows": scope.get("publication_scoped_completed_rows"),
            "dataset_count": scope.get("publication_dataset_count"),
            "dataset_alpha_cell_count": scope.get("publication_dataset_alpha_cell_count"),
            "method_label_count": scope.get("publication_method_label_count"),
            "kg_node_count": len(kg.get("nodes", [])),
            "kg_edge_count": len(kg.get("edges", [])),
            "artifact_manifest_coverage": manifest.get("summary", {}).get(
                "manifest_reference_resolution_rate"
            ),
        },
        "public_paths": {
            "scope": "atlas/scope/experiment_scope.json",
            "kg": "site/kg_browser_data.json",
            "artifact_manifest": "evidence/public_artifact_manifest.json",
        },
    }
    if payload["scope"]["kg_node_count"] != kg.get("summary", {}).get("node_count"):
        raise ValueError("KG node count mismatch")
    if payload["scope"]["kg_edge_count"] != kg.get("summary", {}).get("edge_count"):
        raise ValueError("KG edge count mismatch")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", default=".")
    parser.add_argument(
        "--out",
        default="atlas/provenance/public_release_scope.json",
        help="Path relative to the package root.",
    )
    args = parser.parse_args()
    root = Path(args.package_root).resolve()
    payload = build_scope(root)
    atomic_write_json(root / args.out, payload)
    print(json.dumps({"status": payload["status"], "out": args.out}, sort_keys=True))


if __name__ == "__main__":
    main()
