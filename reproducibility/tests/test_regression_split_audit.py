from pathlib import Path

import pandas as pd

from experiments.regression.scripts import audit_regression_splits as audit


def test_profile_distinguishes_row_id_overlap_from_duplicate_content(monkeypatch):
    df = pd.DataFrame(
        {
            "y": [1.0, 2.0, 2.0, 4.0, 5.0],
            "group": ["a", "b", "b", "c", "d"],
            "feature": [10, 20, 20, 40, 50],
        }
    )

    def fake_load_dataset_frame(dataset_id):
        assert dataset_id == "toy_duplicate"
        return df.copy(), "y", "group"

    def fake_split_frame(source, **kwargs):
        return {
            "train": source.iloc[[0, 1]].copy(),
            "cal": source.iloc[[2]].copy(),
            "test": source.iloc[[3, 4]].copy(),
            "group_col": kwargs["group_col"],
            "split_group_col": kwargs.get("split_group_col"),
        }

    monkeypatch.setattr(audit, "load_dataset_frame", fake_load_dataset_frame)
    monkeypatch.setattr(audit, "split_frame", fake_split_frame)
    monkeypatch.setitem(
        audit.DATASET_LOADERS,
        "toy_duplicate",
        {"source": "unit", "feature_drop_columns": []},
    )

    profile = audit.profile_one_dataset(
        "toy_duplicate",
        {
            "random_seeds": [11],
            "splits": {"train": 0.4, "calibration": 0.2, "test": 0.4},
        },
    )

    seed_profile = profile["seeds"][0]
    assert seed_profile["all_row_id_overlaps_zero"] is True
    assert seed_profile["row_id_overlaps"] == {
        "train_cal": 0,
        "train_test": 0,
        "cal_test": 0,
    }
    assert seed_profile["row_signature_overlaps"]["train_cal"] == 1
    assert seed_profile["all_row_signature_overlaps_zero"] is False
    assert profile["model_visible_feature_drop_columns"] == ["y", "group"]
    assert seed_profile[
        "model_visible_feature_signature_cross_split_overlaps"
    ] == {
        "train_cal": 1,
        "train_test": 0,
        "cal_test": 0,
    }
    assert seed_profile[
        "model_visible_feature_plus_target_signature_cross_split_overlaps"
    ] == {
        "train_cal": 1,
        "train_test": 0,
        "cal_test": 0,
    }
    assert seed_profile["all_model_visible_feature_signature_overlaps_zero"] is False
    assert (
        seed_profile[
            "all_model_visible_feature_plus_target_signature_overlaps_zero"
        ]
        is False
    )
    assert seed_profile["sparse_primary_group_cell_count"] > 0
    assert any(
        cell["split"] == "cal" and cell["group"] == "b" and cell["count"] == 1
        for cell in seed_profile["sparse_primary_group_cells"]
    )


def test_build_payload_records_grouped_split_disjointness(monkeypatch):
    df = pd.DataFrame(
        {
            "y": [1.0, 2.0, 3.0, None, 5.0, 6.0, 7.0, 8.0],
            "primary_group": ["g1", "g1", "g2", "g2", "g3", "g3", "g4", "g4"],
            "batch": ["a", "a", "b", "b", "c", "c", "d", "d"],
            "feature": [1, 2, 3, 4, 5, 6, 7, 8],
        }
    )

    def fake_load_dataset_frame(dataset_id):
        assert dataset_id == "toy_grouped"
        return df.copy(), "y", "primary_group"

    monkeypatch.setattr(audit, "load_dataset_frame", fake_load_dataset_frame)
    monkeypatch.setitem(audit.DATASET_LOADERS, "toy_grouped", {"source": "unit"})

    payload = audit.build_payload(
        Path("toy_grouped.yaml"),
        {
            "experiment_id": "toy_grouped_v0",
            "random_seeds": [11],
            "target_transform": "identity",
            "datasets": ["toy_grouped"],
            "splits": {
                "train": 0.5,
                "calibration": 0.25,
                "test": 0.25,
                "group_col": "batch",
            },
        },
    )

    seed_profile = payload["seeds"][0]
    assert payload["schema"] == "cpfi_regression_split_profile_v2"
    assert payload["dataset_id"] == "toy_grouped"
    assert payload["profiles"][0]["target_missing_before_split"] == 1
    assert seed_profile["all_split_group_overlaps_zero"] is True
    assert seed_profile["all_row_id_overlaps_zero"] is True
    assert payload["profiles"][0]["model_visible_feature_drop_columns"] == [
        "y",
        "primary_group",
        "batch",
    ]
    assert sum(
        seed_profile["splits"][name]["rows"] for name in ("train", "cal", "test")
    ) == 7


def test_build_payload_records_duplicate_cluster_split_scope(monkeypatch):
    df = pd.DataFrame(
        {
            "y": [1.0, 1.0, 2.0, 3.0, 4.0, 4.0],
            "group": ["a", "b", "a", "b", "c", "d"],
            "feature": [10, 10, 20, 30, 40, 40],
        }
    )

    def fake_load_dataset_frame(dataset_id):
        assert dataset_id == "toy_duplicate_cluster"
        return df.copy(), "y", "group"

    monkeypatch.setattr(audit, "load_dataset_frame", fake_load_dataset_frame)
    monkeypatch.setitem(
        audit.DATASET_LOADERS,
        "toy_duplicate_cluster",
        {"source": "unit", "feature_drop_columns": []},
    )

    payload = audit.build_payload(
        Path("toy_duplicate_cluster.yaml"),
        {
            "experiment_id": "toy_duplicate_cluster_v0",
            "random_seeds": [11],
            "target_transform": "identity",
            "datasets": ["toy_duplicate_cluster"],
            "splits": {
                "train": 0.5,
                "calibration": 0.25,
                "test": 0.25,
                "duplicate_cluster_scope": "model_visible_features_plus_target",
            },
        },
    )

    profile = payload["profiles"][0]
    seed_profile = payload["seeds"][0]
    assert payload["split_config"]["duplicate_cluster_scope"] == (
        "model_visible_features_plus_target"
    )
    assert profile["split_group_col"] == audit.DUPLICATE_CLUSTER_SPLIT_COL
    assert profile["duplicate_cluster_split_col"] == audit.DUPLICATE_CLUSTER_SPLIT_COL
    assert profile["base_split_group_col"] is None
    assert seed_profile["all_split_group_overlaps_zero"] is True
    assert (
        seed_profile["all_model_visible_feature_plus_target_signature_overlaps_zero"]
        is True
    )


def test_render_markdown_includes_model_visible_overlap_fields(monkeypatch):
    df = pd.DataFrame(
        {
            "y": [1.0, 1.0, 2.0, 3.0, 4.0, 4.0],
            "group": ["a", "b", "a", "b", "c", "d"],
            "feature": [10, 10, 20, 30, 40, 40],
        }
    )

    def fake_load_dataset_frame(dataset_id):
        assert dataset_id == "toy_duplicate_cluster_markdown"
        return df.copy(), "y", "group"

    monkeypatch.setattr(audit, "load_dataset_frame", fake_load_dataset_frame)
    monkeypatch.setitem(
        audit.DATASET_LOADERS,
        "toy_duplicate_cluster_markdown",
        {"source": "unit", "feature_drop_columns": []},
    )

    payload = audit.build_payload(
        Path("toy_duplicate_cluster_markdown.yaml"),
        {
            "experiment_id": "toy_duplicate_cluster_markdown_v0",
            "random_seeds": [11],
            "target_transform": "identity",
            "datasets": ["toy_duplicate_cluster_markdown"],
            "splits": {
                "train": 0.5,
                "calibration": 0.25,
                "test": 0.25,
                "duplicate_cluster_scope": "model_visible_features_plus_target",
            },
        },
    )

    markdown = audit.render_markdown(payload)
    assert "model_visible_feature_signature_overlaps" in markdown
    assert "model_visible_feature_plus_target_signature_overlaps" in markdown
    assert '"train_cal": 0' in markdown


def test_build_payload_records_row_signature_duplicate_cluster_scope(monkeypatch):
    df = pd.DataFrame(
        {
            "y": [1.0, 1.0, 1.0, 2.0, 3.0, 4.0],
            "group": ["a", "a", "b", "b", "c", "d"],
            "feature": [10, 10, 10, 20, 30, 40],
            "noise": [0, 0, 0, 1, 2, 3],
        }
    )

    def fake_load_dataset_frame(dataset_id):
        assert dataset_id == "toy_row_signature_duplicate_cluster"
        return df.copy(), "y", "group"

    monkeypatch.setattr(audit, "load_dataset_frame", fake_load_dataset_frame)
    monkeypatch.setitem(
        audit.DATASET_LOADERS,
        "toy_row_signature_duplicate_cluster",
        {"source": "unit", "feature_drop_columns": []},
    )

    payload = audit.build_payload(
        Path("toy_row_signature_duplicate_cluster.yaml"),
        {
            "experiment_id": "toy_row_signature_duplicate_cluster_v0",
            "random_seeds": [11],
            "target_transform": "identity",
            "datasets": ["toy_row_signature_duplicate_cluster"],
            "splits": {
                "train": 0.5,
                "calibration": 0.25,
                "test": 0.25,
                "duplicate_cluster_scope": "row_signature",
            },
        },
    )

    profile = payload["profiles"][0]
    seed_profile = payload["seeds"][0]
    assert payload["split_config"]["duplicate_cluster_scope"] == "row_signature"
    assert profile["split_group_col"] == audit.DUPLICATE_CLUSTER_SPLIT_COL
    assert seed_profile["all_split_group_overlaps_zero"] is True
    assert seed_profile["all_row_signature_overlaps_zero"] is True
    assert seed_profile["row_signature_overlaps"] == {
        "train_cal": 0,
        "train_test": 0,
        "cal_test": 0,
    }


def test_build_payload_drops_base_split_group_for_duplicate_cluster_scope(monkeypatch):
    df = pd.DataFrame(
        {
            "y": [1.0, 2.0, 1.0, 3.0, 4.0, 5.0, 6.0, 7.0],
            "primary_group": ["p", "p", "q", "q", "r", "r", "s", "s"],
            "household": ["h1", "h1", "h2", "h2", "h3", "h3", "h4", "h4"],
            "feature": [7, 8, 7, 9, 10, 11, 12, 13],
        }
    )

    def fake_load_dataset_frame(dataset_id):
        assert dataset_id == "toy_duplicate_cluster_with_base_group"
        return df.copy(), "y", "primary_group"

    monkeypatch.setattr(audit, "load_dataset_frame", fake_load_dataset_frame)
    monkeypatch.setitem(
        audit.DATASET_LOADERS,
        "toy_duplicate_cluster_with_base_group",
        {"source": "unit", "feature_drop_columns": []},
    )

    payload = audit.build_payload(
        Path("toy_duplicate_cluster_with_base_group.yaml"),
        {
            "experiment_id": "toy_duplicate_cluster_with_base_group_v0",
            "random_seeds": [11],
            "target_transform": "identity",
            "datasets": ["toy_duplicate_cluster_with_base_group"],
            "splits": {
                "train": 0.5,
                "calibration": 0.25,
                "test": 0.25,
                "group_col": "household",
                "duplicate_cluster_scope": "model_visible_features_plus_target",
            },
        },
    )

    profile = payload["profiles"][0]
    assert profile["base_split_group_col"] == "household"
    assert profile["split_group_col"] == audit.DUPLICATE_CLUSTER_SPLIT_COL
    assert profile["model_visible_feature_drop_columns"] == [
        "y",
        "primary_group",
        audit.DUPLICATE_CLUSTER_SPLIT_COL,
        "household",
    ]
