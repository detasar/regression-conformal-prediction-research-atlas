from experiments.regression.scripts import audit_ipums_cps_source_review as ipums


def page(*lines):
    return "\n".join(lines)


def sample_ids_html():
    return page(
        '<tr><td><span class="">cps1962_03s</span></td><td>IPUMS-CPS, ASEC 1962</td></tr>',
        '<tr><td><span class="">cps2025_12s</span></td><td>IPUMS-CPS, December 2025</td></tr>',
        '<tr><td><span class="">cps2026_05s</span></td><td>IPUMS-CPS, May 2026</td></tr>',
    )


def revisions_html():
    return page(
        "The May 2026 monthly data are now available via IPUMS CPS. "
        "October 2025 data were not collected during the U.S. federal government shutdown.",
        "June 11, 2026",
        "Added samples.",
        "Basic monthly variables are now available for the May 2026 sample.",
    )


def api_doc_html():
    return page(
        "IPUMS CPS Data Extracts",
        "Extracts rectangularized on person records",
        "Pre-selected variables included by default",
        "CSV or fixed-width data file output",
        "Formatted data files for Stata, SPSS, and SAS",
        "Hierarchical extracts",
        "Case Selection",
        "Attached Characteristics",
        "Data Quality Flags",
        "Adjustment of monetary values",
        "Currently unsupported features include:",
        "Custom sample sizes",
        "Longitudinal extracts",
        "no metadata support in the API for IPUMS microdata collections",
    )


def api_workflow_html():
    return page(
        "export IPUMS_API_KEY=YOUR_API_KEY_HERE",
        "https://api.ipums.org/extracts?collection=cps&version=2",
        "Authorization: $IPUMS_API_KEY",
    )


def variable_html(name, description, extra=""):
    return page(
        f"<h1>{name}</h1>",
        '<div id="description_section">',
        "<h2>Description</h2>",
        f"<p>{description}</p>",
        f"<p>{extra}</p>",
        '<div id="comparability_section">',
        "<h2>Comparability</h2>",
    )


def variable_pages():
    return {
        "hourly_wage": variable_html(
            "HOURWAGE",
            "HOURWAGE reports hourly earnings and is topcoded.",
            "Researchers should use the EARNWT weight. Users must adjust for inflation. 999.99 = N.I.U.",
        ),
        "weekly_earnings": variable_html(
            "EARNWEEK",
            "EARNWEEK reports usual weekly earnings.",
            "Researchers should use the EARNWT weight. Users must adjust for inflation. NIU.",
        ),
        "wage_salary_income": variable_html(
            "INCWAGE",
            "INCWAGE indicates pre-tax wage and salary income.",
            "This variable is topcoded and users must adjust for inflation. N.I.U.",
        ),
        "total_personal_income": variable_html(
            "INCTOT",
            "INCTOT indicates total pre-tax personal income.",
            "Values can be negative. Users must adjust for inflation. Missing.",
        ),
        "usual_hours_all_jobs": variable_html(
            "UHRSWORKT",
            "UHRSWORKT is the usual number of hours per week at all jobs.",
            "999 = Not in universe (NIU).",
        ),
    }


def build_fixture_payload():
    return ipums.build_payload(
        source_html="IPUMS CPS harmonized data",
        documentation_html="Variables Samples",
        instructions_html="The IPUMS-CPS data extraction system allows researchers to fashion extracts.",
        faq_html="Two variables constitute a unique identifier: YEAR and SERIAL.",
        sample_ids_html=sample_ids_html(),
        samples_html="Sample sizes and sample notes",
        variable_groups_html="Outgoing Rotation Groups Annual Social & Economic Supplement",
        revisions_html=revisions_html(),
        api_doc_html=api_doc_html(),
        api_workflow_html=api_workflow_html(),
        variable_pages=variable_pages(),
        generated_at_utc="2026-07-04T00:00:00+00:00",
    )


def test_ipums_cps_source_review_builds_blocked_source_audit():
    payload = build_fixture_payload()

    assert payload["dataset_id"] == "ipums_cps_source_review"
    assert payload["source"] == "IPUMS CPS harmonized Current Population Survey microdata"
    assert payload["source_url"] == ipums.SOURCE_URL
    assert payload["audit_status"] == "source_review_only_modeling_blocked"
    assert payload["summary"]["sample_id_count"] == 3
    assert payload["summary"]["latest_sample_id"] == "cps2026_05s"
    assert payload["summary"]["latest_revision_date"] == "June 11, 2026"
    assert payload["summary"]["revision_mentions_2025_shutdown_gap"] is True
    assert payload["summary"]["candidate_variable_present_count"] == 5
    assert payload["summary"]["api_supported_feature_count"] == 9
    assert payload["summary"]["api_unsupported_feature_count"] == 2
    assert payload["summary"]["api_key_required_documented"] is True
    assert payload["summary"]["metadata_api_gap_documented"] is True
    assert payload["summary"]["modeling_approved"] is False
    assert payload["access_policy"]["raw_extract_downloaded"] is False
    assert payload["access_policy"]["api_extract_submitted"] is False

    variables = payload["candidate_target_policy"][
        "sample_variables_verified_from_documentation"
    ]
    assert variables["hourly_wage"]["risk_keywords"]["topcoded"] is True
    assert variables["total_personal_income"]["risk_keywords"][
        "negative_values_possible"
    ] is True
    assert payload["group_policy"]["status"] == "not_publication_ready_fairness_dataset"
    assert "target variable not selected" in payload["blockers"]


def test_ipums_cps_markdown_keeps_non_claims_visible():
    payload = build_fixture_payload()
    markdown = ipums.render_markdown(payload)

    assert "Modeling approved: `False`" in markdown
    assert "This audit is not labor-market or wage-discrimination evidence." in markdown
    assert "`hourly_wage` -> `HOURWAGE`" in markdown
