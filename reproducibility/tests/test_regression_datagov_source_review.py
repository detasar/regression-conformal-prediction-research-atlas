from experiments.regression.scripts import audit_datagov_source_review as audit


def v4_result(identifier, title, access="public", distributions=1):
    return {
        "identifier": identifier,
        "title": title,
        "organization": "General Services Administration",
        "theme": ["Economy"],
        "keyword": ["income", "survey"],
        "last_harvested_date": "2026-07-04T00:00:00Z",
        "dcat": {
            "@type": "dcat:Dataset",
            "identifier": identifier,
            "title": title,
            "accessLevel": access,
            "publisher": {"name": "Data.gov"},
            "distribution": [
                {
                    "@type": "dcat:Distribution",
                    "title": f"{title} CSV",
                    "format": "CSV",
                    "downloadURL": f"https://example.gov/{identifier}.csv",
                }
                for _ in range(distributions)
            ],
        },
    }


def v4_payload(query_id):
    return {
        "after": "cursor",
        "sort": "relevance",
        "results": [
            v4_result(f"{query_id}-1", f"{query_id.title()} dataset 1"),
            v4_result(f"{query_id}-2", f"{query_id.title()} dataset 2", distributions=2),
        ],
    }


def legacy_payload(count):
    return {
        "success": True,
        "result": {
            "count": count,
            "results": [
                {
                    "title": "Sample legacy dataset",
                    "license_title": "Creative Commons CCZero",
                    "metadata_created": "2026-01-01T00:00:00",
                    "metadata_modified": "2026-07-01T00:00:00",
                    "organization": {"title": "Sample agency"},
                }
            ],
        },
    }


def payload():
    v4 = {query_id: v4_payload(query_id) for query_id in audit.CANDIDATE_QUERIES}
    legacy = {
        query_id: legacy_payload(100 + offset)
        for offset, query_id in enumerate(audit.CANDIDATE_QUERIES)
    }
    return audit.build_payload(
        v4_query_json=v4,
        legacy_query_json=legacy,
        generated_at_utc="2026-07-04T00:00:00+00:00",
    )


def test_datagov_source_review_builds_blocked_metadata_audit():
    result = payload()

    assert result["dataset_id"] == "datagov_source_review"
    assert result["source"] == "Data.gov catalog metadata portal"
    assert result["audit_status"] == "source_review_only_modeling_blocked"
    assert result["summary"]["candidate_query_count"] == len(audit.CANDIDATE_QUERIES)
    assert result["summary"]["v4_positive_query_count"] == len(audit.CANDIDATE_QUERIES)
    assert result["summary"]["legacy_positive_query_count"] == len(
        audit.CANDIDATE_QUERIES
    )
    assert result["summary"]["v4_results_returned_total"] == 16
    assert result["summary"]["v4_public_access_result_count"] == 16
    assert result["summary"]["v4_downloadable_distribution_count_returned"] == 24
    assert result["summary"]["modeling_approved"] is False
    assert result["summary"]["raw_data_downloaded"] is False
    assert result["candidate_dataset_policy"]["status"] == "not_selected"
    assert result["access_policy"]["raw_data_committed_to_git"] is False
    assert "no individual Data.gov dataset record selected" in result["blockers"]


def test_datagov_markdown_and_profile_keep_non_claims_visible():
    result = payload()
    markdown = audit.render_markdown(result)
    profile = audit.profile_from_payload(result)
    profile_markdown = audit.render_profile_markdown(profile)

    assert "Modeling approved: `False`" in markdown
    assert "This audit is not a modeled Data.gov dataset." in markdown
    assert "`income` | `income`" in markdown
    assert profile["dataset_record_selected"] is False
    assert profile["primary_source_resolved"] is False
    assert "Dataset record selected: `False`" in profile_markdown
    assert "Raw data downloaded: `False`" in profile_markdown
