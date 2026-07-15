"""Shared utilities for public Research Atlas rebuild scripts."""

from __future__ import annotations

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


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def preserve_generated_at(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if path.exists():
        try:
            prior = read_json(path)
        except (json.JSONDecodeError, OSError):
            prior = {}
        prior_generated_at = prior.get("generated_at_utc")
        if isinstance(prior_generated_at, str) and prior_generated_at:
            payload["generated_at_utc"] = prior_generated_at
    return payload


def missing_relative_paths(package_root: Path, relatives: list[str]) -> list[str]:
    return [rel for rel in relatives if not (package_root / rel).exists()]
