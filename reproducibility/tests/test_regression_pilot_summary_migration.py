import json

import pytest

from experiments.regression.scripts.migrate_pilot_summary_frontier_key import (
    DEFAULT_NOTE,
    migrate_file,
    migrate_payload,
)


def test_migrate_payload_renames_best_rows_to_candidate_frontier_rows():
    payload = {"rows": [{"coverage": 0.9}], "best_rows": [{"coverage": 0.9}]}

    migrated, changed = migrate_payload(payload)

    assert changed is True
    assert "best_rows" not in migrated
    assert migrated["candidate_frontier_rows"] == [{"coverage": 0.9}]
    assert migrated["candidate_frontier_note"] == DEFAULT_NOTE


def test_migrate_payload_rejects_conflicting_frontier_rows():
    payload = {
        "best_rows": [{"coverage": 0.9}],
        "candidate_frontier_rows": [{"coverage": 0.8}],
    }

    with pytest.raises(ValueError, match="conflicts"):
        migrate_payload(payload)


def test_migrate_file_dry_run_leaves_payload_unchanged(tmp_path):
    path = tmp_path / "pilot_summary.json"
    path.write_text(json.dumps({"best_rows": [{"model": "ridge"}]}), encoding="utf-8")

    changed = migrate_file(path, dry_run=True)

    assert changed is True
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "best_rows": [{"model": "ridge"}]
    }
