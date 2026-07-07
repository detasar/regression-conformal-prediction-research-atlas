"""Resumable experiment utilities for regression studies."""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional


@dataclass(frozen=True)
class RunRecord:
    """Immutable metadata for one atomic experiment unit."""

    run_id: str
    dataset_id: str
    model_id: str
    cp_method: str
    split_seed: int
    alpha: float
    status: str = "queued"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    artifact_paths: Dict[str, str] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    cp_thresholds: Dict[str, float] = field(default_factory=dict)
    cp_metadata: Dict = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


def atomic_write_text(path: Path, text: str) -> None:
    """Write text atomically to avoid corrupt outputs on crashes."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def atomic_write_json(path: Path, payload: Dict) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def append_jsonl(path: Path, records: Iterable[Dict]) -> None:
    """Append JSONL records with fsync for durable progress ledgers."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def run_record_path(root: Path, run_id: str) -> Path:
    return root / "runs" / run_id[:2] / run_id / "record.json"


def checkpoint_run(root: Path, record: RunRecord) -> Path:
    """Persist a run record to its deterministic checkpoint path."""

    path = run_record_path(root, record.run_id)
    atomic_write_json(path, record.to_dict())
    return path


def load_run_record(root: Path, run_id: str) -> Optional[Dict]:
    path = run_record_path(root, run_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
