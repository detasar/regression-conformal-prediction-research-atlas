from io import BytesIO
from zipfile import ZipFile

from experiments.regression.scripts import audit_brfss_2024_source_review as brfss


def codebook_zip_bytes() -> bytes:
    html = """
    <html><body>
    Label: Computed body mass index Section Name: Calculated Variables
    SAS Variable Name: _BMI5
    Label: Number of Days Physical Health Not Good Section Name: Healthy Days
    SAS Variable Name: PHYSHLTH
    Label: Number of Days Mental Health Not Good Section Name: Healthy Days
    SAS Variable Name: MENTHLTH
    Label: Poor Physical or Mental Health Section Name: Healthy Days
    SAS Variable Name: POORHLTH
    Label: General Health Section Name: Health Status
    SAS Variable Name: GENHLTH
    Label: Sex of respondent Section Name: Demographics
    SAS Variable Name: SEXVAR
    Label: Race group Section Name: Calculated Variables
    SAS Variable Name: _RACE
    </body></html>
    """
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("USCODE24_LLCP_082125.HTML", html)
    return buffer.getvalue()


def source_html() -> str:
    return """
    <html><body>
    <h1>2024 BRFSS Survey Data and Documentation</h1>
    There are 457,670 records for 2024. The data files are provided in ASCII
    and SAS Transport formats.
    <a href="/brfss/annual_data/2024/pdf/Overview_2024-508.pdf">
      2024 BRFSS Overview CDC [PDF - 213 KB]
    </a>
    <a href="/brfss/annual_data/2024/zip/codebook24_llcp-v2-508.zip">
      2024 BRFSS Codebook CDC [ZIP - 3 MB]
    </a>
    <a href="/brfss/annual_data/2024/pdf/2024-calculated-variables-version4-508.pdf">
      Calculated Variables in Data Files CDC [PDF - 801 KB]
    </a>
    <a href="/brfss/annual_data/2024/pdf/2024-DQR-508.pdf">
      2024 Summary Data Quality Report with Response Rates CDC [PDF - 543 KB]
    </a>
    <a href="/brfss/annual_data/2024/pdf/Complex-Sampling-Weights-and-Preparing-Module-Data-for-Analysis-2024-508.pdf">
      Complex Sampling Weights and Preparing Module Data for Analysis CDC
    </a>
    <a href="/brfss/annual_data/2024/pdf/2024_ResponseRates_Table-508.pdf">
      BRFSS Combined Landline and Cell Phone Weighted Response Rates by State, 2024 CDC
    </a>
    <a href="/brfss/annual_data/2024/pdf/Compare_2024-508.pdf">
      Comparability of Data CDC [PDF - 254 KB]
    </a>
    <a href="/brfss/annual_data/2024/summary_matrix_24.html">
      Summary - Matrix of Calculated Variables (CV) in the 2024 Data File
    </a>
    <a href="/brfss/annual_data/2024/pdf/2024-Weightning-Description-508.pdf">
      2024 Weighting Formula CDC [PDF - 249 KB]
    </a>
    <a href="/brfss/annual_data/2024/files/LLCP2024ASC.zip">
      2024 BRFSS Data (ASCII) [ZIP - 41.5 MB]
    </a>
    This file for the combined landline and cell phone data set is in ASCII
    format. It has a fixed record length of 2111 positions.
    <a href="/brfss/annual_data/2024/files/LLCP2024XPT.zip">
      2024 BRFSS Data (SAS Transport Format) [ZIP - 64.3 MB]
    </a>
    This file contains 345 variables.
    <a href="/brfss/annual_data/2024/llcp_varlayout_24_onecolumn.html">
      Variable Layout
    </a>
    Last Reviewed: September 17, 2025
    </body></html>
    """


def test_brfss_source_review_builds_blocked_source_audit():
    payload = brfss.build_payload(
        source_html=source_html(),
        source_url=brfss.SOURCE_URL,
        annual_index_url=brfss.ANNUAL_INDEX_URL,
        documentation_url=brfss.DOCUMENTATION_URL,
        codebook_zip=codebook_zip_bytes(),
        generated_at_utc="2026-07-04T00:00:00+00:00",
    )

    assert payload["dataset_id"] == "brfss_2024_llcp_source_review"
    assert payload["source"] == "CDC Behavioral Risk Factor Surveillance System"
    assert payload["source_url"] == brfss.SOURCE_URL
    assert payload["audit_status"] == "source_review_only_modeling_blocked"
    assert payload["summary"]["records_reported"] == 457670
    assert payload["summary"]["xpt_variable_count_reported"] == 345
    assert payload["summary"]["fixed_record_length_reported"] == 2111
    assert payload["summary"]["missing_required_source_link_count"] == 0
    assert payload["summary"]["modeling_approved"] is False
    assert payload["access_policy"]["raw_data_downloaded"] is False

    target_candidates = payload["target_policy"][
        "candidate_variables_verified_in_codebook"
    ]
    assert target_candidates["bmi_calculated"]["present_in_codebook"] is True
    assert target_candidates["bmi_calculated"]["label"] == "Computed body mass index"
    assert (
        target_candidates["physical_health_not_good_days"]["variable"]
        == "PHYSHLTH"
    )
    assert payload["group_policy"]["candidate_variables_checked"]["SEXVAR"] is True
    assert payload["group_policy"]["candidate_variables_checked"]["_RACE"] is True
    assert "raw data not downloaded or profiled" in payload["blockers"]


def test_brfss_markdown_keeps_non_claims_visible():
    payload = brfss.build_payload(
        source_html=source_html(),
        source_url=brfss.SOURCE_URL,
        annual_index_url=brfss.ANNUAL_INDEX_URL,
        documentation_url=brfss.DOCUMENTATION_URL,
        codebook_zip=codebook_zip_bytes(),
        generated_at_utc="2026-07-04T00:00:00+00:00",
    )
    markdown = brfss.render_markdown(payload)

    assert "Modeling approved: `False`" in markdown
    assert "This audit is not approval to run BRFSS models." in markdown
    assert "`bmi_calculated` -> `_BMI5`" in markdown
