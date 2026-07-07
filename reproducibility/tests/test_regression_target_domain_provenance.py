from experiments.regression.scripts import build_target_domain_provenance_catalog as catalog


def touch_sources(root):
    for row in catalog.ROWS:
        for artifact in row.get("source_artifacts", []):
            path = root / artifact
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")


def test_target_domain_provenance_catalog_records_uci_wine_source_bounds(tmp_path):
    touch_sources(tmp_path)

    payload = catalog.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "target_domain_provenance_ready"
    assert payload["summary"]["failed_check_count"] == 0
    assert payload["summary"]["row_count"] == 5
    assert payload["summary"]["external_source_row_count"] == 1
    assert payload["summary"]["bounded_ordinal_row_count"] == 1
    wine = next(row for row in payload["rows"] if row["dataset_id"] == "uci_wine_quality")
    assert wine["target"] == "quality"
    assert wine["natural_lower"] == 0.0
    assert wine["natural_upper"] == 10.0
    assert wine["natural_bound_status"] == "bounded_ordinal_source_provenance_present"
    assert "https://archive.ics.uci.edu/dataset/186/wine%2Bquality" in wine["source_urls"]


def test_target_domain_provenance_markdown_lists_source_url(tmp_path):
    touch_sources(tmp_path)
    payload = catalog.build_payload(tmp_path)

    markdown = catalog.render_markdown(payload)

    assert "# Target Domain Provenance" in markdown
    assert "`uci_wine_quality`" in markdown
    assert "https://archive.ics.uci.edu/dataset/186/wine%2Bquality" in markdown


def test_target_domain_provenance_fails_when_local_artifact_is_missing(tmp_path):
    touch_sources(tmp_path)
    missing = tmp_path / catalog.ROWS[0]["source_artifacts"][0]
    missing.unlink()

    payload = catalog.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "target_domain_provenance_incomplete"
    assert "all_source_artifacts_present" in payload["failed_checks"]
