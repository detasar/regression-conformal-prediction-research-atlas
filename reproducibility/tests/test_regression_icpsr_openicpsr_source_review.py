from experiments.regression.scripts import audit_icpsr_openicpsr_source_review as audit


def search_html(count):
    return f"<html><body>Showing 1 - 50 of {count:,} results.</body></html>"


def find_data_html():
    return """
    <html><body>
    ICPSR studies are packages containing one or more datasets plus metadata.
    Search results cover study level, variable level, and publications.
    The Social Science Variables Database supports variable search.
    Browse by Discipline. Thematic Collections.
    ICPSR raw data about individuals and organizations commonly include
    rectangular data files that can be downloaded in a variety of formats.
    </body></html>
    """


def metadata_records_html():
    return """
    <html><body>
    Metadata Export Application Programming Interface supports searches by
    study identifier, subject terms, geographic coverage area, and original
    release date. Formats include DCAT-US, MARCXML, Dublin Core, and
    DDI-Codebook. Individual studies expose an Export Metadata tab. Metadata
    are available under Creative Commons Attribution-NonCommercial 4.0, while
    study-specific ICPSR terms of use still apply.
    </body></html>
    """


def repository_operations_html():
    return """
    <html><body>
    Repository operations include Researcher Passport, a deposit agreement, a
    secure area for processing, checksums, and a Collection Development Policy.
    </body></html>
    """


def direct_openicpsr_probes():
    return [
        {
            "url": "https://www.openicpsr.org/",
            "fetch_status": "ok",
            "status_code": 200,
        },
        {
            "url": "https://www.openicpsr.org/openicpsr/about",
            "fetch_status": "ok",
            "status_code": 200,
        },
        {
            "url": "https://www.openicpsr.org/openicpsr/faqs",
            "fetch_status": "http_error_403",
            "status_code": 403,
        },
        {
            "url": "https://www.openicpsr.org/openicpsr/repository/",
            "fetch_status": "ok",
            "status_code": 200,
        },
    ]


def payload():
    return audit.build_payload(
        find_data_html=find_data_html(),
        study_search_html=search_html(28300),
        variable_search_html=search_html(1800000),
        publication_search_html=search_html(125885),
        openicpsr_archive_search_html=search_html(11231),
        metadata_records_html=metadata_records_html(),
        repository_operations_html=repository_operations_html(),
        candidate_query_html={
            "income": search_html(1341),
            "housing": search_html(381),
            "health": search_html(1463),
            "education": search_html(1533),
            "labor": search_html(1198),
        },
        direct_openicpsr_probes=direct_openicpsr_probes(),
        generated_at_utc="2026-07-04T00:00:00+00:00",
    )


def test_icpsr_openicpsr_source_review_payload_blocks_modeling():
    result = payload()

    assert result["dataset_id"] == "icpsr_openicpsr_source_review"
    assert result["source"] == "ICPSR and openICPSR research data repositories"
    assert result["audit_status"] == "source_review_only_modeling_blocked"
    assert result["summary"]["icpsr_study_search_result_count"] == 28300
    assert result["summary"]["icpsr_variable_search_result_count"] == 1800000
    assert result["summary"]["icpsr_publication_search_result_count"] == 125885
    assert result["summary"]["openicpsr_archive_result_count"] == 11231
    assert result["summary"]["candidate_query_with_results_count"] == 5
    assert result["summary"]["metadata_api_documented"] is True
    assert result["summary"]["metadata_format_count"] == 4
    assert result["summary"]["direct_openicpsr_probe_failure_count"] == 1
    assert result["access_policy"]["study_selected"] is False
    assert result["access_policy"]["raw_data_downloaded"] is False
    assert result["summary"]["modeling_approved"] is False
    assert result["summary"]["runner_config_approved"] is False
    assert result["candidate_study_policy"]["status"] == "not_selected"


def test_icpsr_openicpsr_source_review_markdown_states_non_claims():
    result = payload()
    markdown = audit.render_markdown(result)
    profile_markdown = audit.render_profile_markdown(audit.profile_from_payload(result))

    assert "Modeling approved: `False`" in markdown
    assert "This audit is not a modeled ICPSR/openICPSR dataset." in markdown
    assert "`income` -> `income`: openICPSR archive results `1341`" in markdown
    assert "Direct openICPSR probe failures: 1 / 4" in markdown
    assert "Study selected: `False`" in profile_markdown
    assert "Raw data downloaded: `False`" in profile_markdown
