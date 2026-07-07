"""Migrate legacy pilot summary frontier keys.

Older regression reports used ``best_rows`` for the diagnostic frontier table.
That wording is too strong: these rows are triage candidates, not method
recommendations. This script updates committed ``pilot_summary.json`` sidecars
to the current ``candidate_frontier_rows`` schema while preserving values.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json


DEFAULT_NOTE = "Rows are sorted diagnostics for triage, not method recommendations."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report affected files without modifying them.",
    )
    return parser.parse_args()


def migrate_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    if "best_rows" not in payload:
        return payload, False
    migrated = dict(payload)
    legacy_rows = migrated.pop("best_rows")
    if "candidate_frontier_rows" in migrated:
        if migrated["candidate_frontier_rows"] != legacy_rows:
            raise ValueError("best_rows conflicts with candidate_frontier_rows")
    else:
        migrated["candidate_frontier_rows"] = legacy_rows
    migrated.setdefault("candidate_frontier_note", DEFAULT_NOTE)
    return migrated, True


def migrate_file(path: Path, *, dry_run: bool) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    migrated, changed = migrate_payload(payload)
    if changed and not dry_run:
        atomic_write_json(path, migrated)
    return changed


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    paths = sorted((root / "experiments/regression/reports").glob("**/pilot_summary.json"))
    changed_paths = []
    for path in paths:
        if migrate_file(path, dry_run=args.dry_run):
            changed_paths.append(str(path.relative_to(root)))
    print(
        json.dumps(
            {
                "status": "ok",
                "dry_run": bool(args.dry_run),
                "scanned": len(paths),
                "migrated": len(changed_paths),
                "paths": changed_paths,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
