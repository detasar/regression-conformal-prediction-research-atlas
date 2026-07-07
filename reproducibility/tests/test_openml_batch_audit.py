import json

import pandas as pd

from experiments.regression.scripts import audit_openml_batch


def test_read_jsonl_skips_blank_lines(tmp_path):
    spec = tmp_path / "spec.jsonl"
    spec.write_text('{"openml_id": 1}\n\n{"openml_id": 2}\n', encoding="utf-8")

    rows = audit_openml_batch.read_jsonl(spec)

    assert [row["openml_id"] for row in rows] == [1, 2]


def test_materialize_record_writes_audit_and_profile(monkeypatch, tmp_path):
    df = pd.DataFrame(
        {
            "age": [10, 20, 30, 40],
            "feature": [1.0, 2.0, 4.0, 8.0],
            "target": [0.5, 1.5, 2.5, 3.5],
        }
    )

    monkeypatch.setattr(
        audit_openml_batch,
        "openml_metadata",
        lambda openml_id, description_chars: {
            "openml_id": openml_id,
            "name": "toy",
            "version": 1,
            "format": "arff",
            "default_target_attribute": "target",
            "openml_page": "https://www.openml.org/d/123",
            "url": "https://example.test/toy.arff",
            "licence": "Public",
            "description_excerpt": "toy",
            "qualities": {},
            "features": [],
        },
    )
    monkeypatch.setattr(
        audit_openml_batch,
        "load_openml_regression_frame",
        lambda openml_id, target: df,
    )

    output = audit_openml_batch.materialize_record(
        {
            "openml_id": 123,
            "target": "target",
            "dataset_id": "toy_openml",
            "group_columns": ["age"],
        },
        out_root=tmp_path,
        description_chars=100,
    )

    audit = json.loads((tmp_path / "toy_openml" / "audit.json").read_text())
    profile = json.loads((tmp_path / "toy_openml" / "profile.json").read_text())

    assert output["dataset_id"] == "toy_openml"
    assert audit["openml_id"] == 123
    assert audit["sensitive_candidates"] == ["age"]
    assert profile["group_profiles"][0]["column"] == "age"
