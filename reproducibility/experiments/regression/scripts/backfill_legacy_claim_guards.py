"""Backfill legacy config claim-guard controls.

Older smoke configs predate the current claim-boundary controls. This script
adds only the controls implied by configured conformal methods:

- CQR rows are interpreted as fixed quantile-backend evidence.
- Venn-Abers regression rows are diagnostic/fallback evidence, not validated
  Venn-Abers regression evidence.

The script preserves the existing YAML layout by patching text rather than
round-tripping through a YAML serializer.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from cpfi.regression.experiment import atomic_write_json, atomic_write_text


SCHEMA = "cpfi_legacy_claim_guard_backfill_v1"
DEFAULT_CONFIG_GLOB = "experiments/regression/configs/*.yaml"
DEFAULT_OUT = (
    "experiments/regression/reports/methodology_sanity_audit_20260627/"
    "legacy_claim_guard_backfill.json"
)
CQR_GUARD = "interpret_cqr_as_fixed_quantile_backend"
VA_GUARD = "forbid_validated_venn_abers_regression_claims"
VA_METHODS = {"venn_abers_quantile", "venn_abers_split_fallback"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--config-glob", default=DEFAULT_CONFIG_GLOB)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--config-path", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def rel(path: Path, root: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    try:
        return str(resolved_path.relative_to(resolved_root))
    except ValueError:
        return str(resolved_path)


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def required_guards(config: dict[str, Any]) -> dict[str, bool]:
    methods = {str(method) for method in config.get("cp_methods", []) or []}
    required: dict[str, bool] = {}
    if "cqr" in methods:
        required[CQR_GUARD] = True
    if methods.intersection(VA_METHODS):
        required[VA_GUARD] = True
    return required


def missing_guards(config: dict[str, Any]) -> dict[str, bool]:
    controls = config.get("quality_controls", {}) or {}
    return {
        key: value
        for key, value in required_guards(config).items()
        if controls.get(key) is not value
    }


def _top_level_key(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and not line.startswith((" ", "\t")) and ":" in stripped


def patch_quality_controls(text: str, additions: dict[str, bool]) -> str:
    if not additions:
        return text
    lines = text.splitlines()
    rendered = [f"  {key}: {'true' if value else 'false'}" for key, value in additions.items()]

    for index, line in enumerate(lines):
        if line.strip() != "quality_controls:" or line.startswith((" ", "\t")):
            continue
        end = index + 1
        while end < len(lines):
            candidate = lines[end]
            if _top_level_key(candidate):
                break
            end += 1
        lines[end:end] = rendered
        return "\n".join(lines).rstrip() + "\n"

    insert_at = len(lines)
    for index, line in enumerate(lines):
        if line.strip() == "logging:" and not line.startswith((" ", "\t")):
            insert_at = index
            break
    block = ["quality_controls:", *rendered, ""]
    lines[insert_at:insert_at] = block
    return "\n".join(lines).rstrip() + "\n"


def config_paths(root: Path, config_glob: str, explicit_paths: list[str]) -> list[Path]:
    if explicit_paths:
        return sorted({resolve_path(root, value) for value in explicit_paths})
    return sorted(root.glob(config_glob))


def build_payload(
    *,
    root: Path,
    config_glob: str,
    explicit_paths: list[str],
    dry_run: bool,
) -> dict[str, Any]:
    rows = []
    status_counts: Counter[str] = Counter()
    guard_counts: Counter[str] = Counter()
    touched_configs = 0
    for path in config_paths(root, config_glob, explicit_paths):
        config = read_yaml(path)
        required = required_guards(config)
        missing = missing_guards(config)
        status = "unchanged"
        if missing:
            status = "planned" if dry_run else "updated"
            touched_configs += 1
            guard_counts.update(missing.keys())
            if not dry_run:
                patched = patch_quality_controls(path.read_text(encoding="utf-8"), missing)
                path.write_text(patched, encoding="utf-8")
        status_counts[status] += 1
        rows.append(
            {
                "config_path": rel(path, root),
                "experiment_id": config.get("experiment_id"),
                "cp_methods": list(config.get("cp_methods", []) or []),
                "required_guards": sorted(required.keys()),
                "backfilled_guards": sorted(missing.keys()),
                "status": status,
            }
        )

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dry_run": bool(dry_run),
        "config_glob": config_glob,
        "explicit_config_paths": explicit_paths,
        "summary": {
            "configs_scanned": len(rows),
            "configs_touched": touched_configs,
            "status_counts": dict(sorted(status_counts.items())),
            "guard_backfill_counts": dict(sorted(guard_counts.items())),
        },
        "rows": rows,
        "claim_boundaries": [
            "This artifact backfills claim-boundary controls only; it does not rerun models.",
            "CQR backfill means fixed quantile-backend CQR interpretation, not model-family-sensitive CQR superiority.",
            "Venn-Abers backfill means diagnostic/fallback regression evidence, not a Venn-Abers regression method with validated interval coverage.",
            "This artifact is not fairness, causal, legal, production, or final-model-selection evidence.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Legacy Claim Guard Backfill",
        "",
        f"- Generated UTC: {payload['generated_at_utc']}",
        f"- Dry run: {payload['dry_run']}",
        f"- Configs scanned: {summary['configs_scanned']}",
        f"- Configs touched: {summary['configs_touched']}",
        f"- Status counts: `{summary['status_counts']}`",
        f"- Guard backfill counts: `{summary['guard_backfill_counts']}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    lines.extend(f"- {boundary}" for boundary in payload["claim_boundaries"])
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| Config | Status | Backfilled guards |",
            "| --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        if row["status"] == "unchanged":
            continue
        guards = ", ".join(f"`{guard}`" for guard in row["backfilled_guards"])
        lines.append(f"| `{row['config_path']}` | {row['status']} | {guards} |")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    payload = build_payload(
        root=root,
        config_glob=args.config_glob,
        explicit_paths=[str(value) for value in args.config_path],
        dry_run=bool(args.dry_run),
    )
    out_path = resolve_path(root, args.out)
    atomic_write_json(out_path, payload)
    atomic_write_text(out_path.with_suffix(".md"), render_markdown(payload))
    print(json.dumps({"status": "ok", "out": rel(out_path, root), **payload["summary"]}, sort_keys=True))


if __name__ == "__main__":
    main()
