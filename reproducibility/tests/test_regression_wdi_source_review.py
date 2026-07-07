from experiments.regression.scripts import audit_wdi_source_review as wdi


def source_json():
    return [
        {"page": "1", "pages": "1", "per_page": "50", "total": "1"},
        [
            {
                "id": "2",
                "lastupdated": "2026-07-01",
                "name": "World Development Indicators",
                "code": "WDI",
                "description": "",
                "url": "",
                "dataavailability": "Y",
                "metadataavailability": "Y",
                "concepts": "3",
            }
        ],
    ]


def indicators_json():
    return [
        {"page": 1, "pages": 302, "per_page": "5", "total": 1510},
        [
            {
                "id": "NY.GDP.PCAP.KD",
                "name": "GDP per capita (constant 2015 US$)",
                "source": {"id": "2", "value": "World Development Indicators"},
            }
        ],
    ]


def country_json():
    return [
        {"page": 1, "pages": 59, "per_page": "5", "total": 295},
        [
            {
                "id": "ABW",
                "iso2Code": "AW",
                "name": "Aruba",
                "region": {"id": "LCN", "value": "Latin America & Caribbean"},
                "incomeLevel": {"id": "HIC", "value": "High income"},
            }
        ],
    ]


def indicator_payload(code, name, topic):
    return [
        {"page": 1, "pages": 1, "per_page": "50", "total": 1},
        [
            {
                "id": code,
                "name": name,
                "unit": "",
                "source": {"id": "2", "value": "World Development Indicators"},
                "sourceNote": f"{name} source note.",
                "sourceOrganization": "World Bank and official sources.",
                "topics": [{"id": "3", "value": topic}],
            }
        ],
    ]


def sample_indicator_json():
    names = {
        "NY.GDP.PCAP.KD": ("GDP per capita (constant 2015 US$)", "Economy & Growth"),
        "SP.DYN.LE00.IN": ("Life expectancy at birth, total (years)", "Health"),
        "SP.POP.TOTL": ("Population, total", "Health"),
        "EG.ELC.ACCS.ZS": ("Access to electricity (% of population)", "Energy"),
        "SE.SEC.ENRR": (
            "School enrollment, secondary (% gross)",
            "Education",
        ),
    }
    return {code: indicator_payload(code, name, topic) for code, (name, topic) in names.items()}


def test_wdi_source_review_builds_blocked_source_audit():
    payload = wdi.build_payload(
        source_json=source_json(),
        indicators_json=indicators_json(),
        country_json=country_json(),
        sample_indicator_json=sample_indicator_json(),
        generated_at_utc="2026-07-04T00:00:00+00:00",
    )

    assert payload["dataset_id"] == "world_bank_wdi_source_review"
    assert payload["source"] == "World Bank World Development Indicators"
    assert payload["source_url"] == wdi.SOURCE_URL
    assert payload["audit_status"] == "source_review_only_modeling_blocked"
    assert payload["summary"]["source_id"] == "2"
    assert payload["summary"]["source_code"] == "WDI"
    assert payload["summary"]["source_lastupdated"] == "2026-07-01"
    assert payload["summary"]["source_indicator_total_api"] == 1510
    assert payload["summary"]["country_total_api"] == 295
    assert payload["summary"]["sample_indicator_present_count"] == 5
    assert payload["summary"]["sample_indicator_source_id_consistent"] is True
    assert payload["summary"]["modeling_approved"] is False
    assert payload["access_policy"]["bulk_data_downloaded"] is False

    sample_indicators = payload["candidate_indicator_policy"][
        "sample_indicators_verified_by_api"
    ]
    assert sample_indicators["gdp_per_capita_constant_2015_usd"]["indicator_id"] == (
        "NY.GDP.PCAP.KD"
    )
    assert sample_indicators["gdp_per_capita_constant_2015_usd"]["source_id"] == "2"
    assert payload["group_policy"]["status"] == "not_individual_fairness_dataset"
    assert "target indicator not selected" in payload["blockers"]


def test_wdi_markdown_keeps_macro_non_claims_visible():
    payload = wdi.build_payload(
        source_json=source_json(),
        indicators_json=indicators_json(),
        country_json=country_json(),
        sample_indicator_json=sample_indicator_json(),
        generated_at_utc="2026-07-04T00:00:00+00:00",
    )
    markdown = wdi.render_markdown(payload)

    assert "Modeling approved: `False`" in markdown
    assert "This audit is not individual fairness evidence." in markdown
    assert "`gdp_per_capita_constant_2015_usd` -> `NY.GDP.PCAP.KD`" in markdown
