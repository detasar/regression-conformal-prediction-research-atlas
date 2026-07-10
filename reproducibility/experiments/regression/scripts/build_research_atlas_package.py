"""Validate the public Research Atlas package from a clean checkout."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def validate_package(package_root: Path) -> dict:
    required = {
        "README.md": "reader entry point",
        "CITATION.cff": "citation metadata",
        "paper/research_document.html": "integrated Research Document",
        "paper/article.pdf": "compact report PDF",
        "paper/supplement.pdf": "supplement PDF",
        "site/kg_browser.html": "knowledge graph browser",
        "site/kg_browser_data.json": "knowledge graph data",
        "evidence/claim_evidence_matrix.md": "claim-evidence matrix",
        "evidence/public_artifact_manifest.json": "artifact manifest",
        "atlas/index.html": "Research Atlas site",
        "pyproject.toml": "install metadata",
        "pytest.ini": "public test config",
    }
    rows = []
    for rel, role in required.items():
        path = package_root / rel
        rows.append({"path": rel, "role": role, "exists": path.exists()})
    missing = [row["path"] for row in rows if not row["exists"]]
    payload = {
        "schema": "regression_cp_public_research_atlas_package_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if not missing else "fail",
        "required_file_count": len(required),
        "missing": missing,
        "files": rows,
        "rebuild_commands": [
            "python -m experiments.regression.scripts.build_public_release_scope --package-root .",
            "python -m experiments.regression.scripts.build_public_research_atlas --package-root .",
            "python -m experiments.regression.scripts.build_research_atlas_package --package-root .",
            "python -m pytest -m \"unit or artifact_public or smoke\"",
        ],
    }
    if missing:
        raise FileNotFoundError(f"Missing public package files: {missing}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", default=".")
    parser.add_argument(
        "--out",
        default="atlas/provenance/public_rebuild_manifest.json",
        help="Path relative to the package root.",
    )
    args = parser.parse_args()
    root = Path(args.package_root).resolve()
    payload = validate_package(root)
    atomic_write_json(root / args.out, payload)
    print(json.dumps({"status": payload["status"], "out": args.out}, sort_keys=True))


if __name__ == "__main__":
    main()
