import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_RELEASE = ROOT / "experiments/regression/public_release"
PACKAGE_ROOT = ROOT.parent / "regression-conformal-prediction-research-atlas-private"
PUBLIC_REPO = "regression-conformal-prediction-research-atlas"
NON_ENGLISH_PATTERNS = [
    re.compile(r"[çğıöşüÇĞİÖŞÜ]"),
    re.compile(r"\\u00(e7|f6|fc|c7|d6|dc)|\\u011f|\\u0131|\\u015f", re.IGNORECASE),
    re.compile(
        r"\b(Bu deneylerde|deneylerde|gözlendi|herşeye|şimdiden|istediğim|"
        r"lütfen|guclu|gozlemlendi|cikan|oldugu|cozumu|Hayir|makale|"
        r"tamamlaninca|kapali|yapalim)\b",
        re.IGNORECASE,
    ),
]


def load_manifest():
    return json.loads(
        (PUBLIC_RELEASE / "public_release_manifest.json").read_text(encoding="utf-8")
    )


def load_authorization():
    return json.loads(
        (PUBLIC_RELEASE / "user_release_authorization.json").read_text(
            encoding="utf-8"
        )
    )


def test_public_release_manifest_authorizes_release_without_method_promotion():
    manifest = load_manifest()
    summary = manifest["summary"]

    assert summary["overall_status"] == "public_release_manifest_ready"
    assert summary["public_release_authorized"] is True
    assert summary["github_pages_url"] == (
        f"https://detasar.github.io/{PUBLIC_REPO}/"
    )
    assert summary["public_repository_url"] == (
        f"https://github.com/detasar/{PUBLIC_REPO}"
    )
    assert summary["method_recommendation_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["working_repository_final_citable"] is False
    assert summary["failed_check_count"] == 0


def test_public_release_authorization_preserves_locked_scientific_wording():
    authorization = load_authorization()
    summary = authorization["summary"]

    assert summary["user_approval_received"] is True
    assert summary["public_repository_release_authorized"] is True
    assert summary["github_pages_publication_authorized"] is True
    assert summary["kg_citable_component_authorized"] is True
    assert summary["locked_empirical_wording"] == (
        "CQR/CV+ were observed as strong practical candidates in these experiments."
    )
    assert summary["locked_venn_abers_wording"] == (
        "The expected strong regression solution did not emerge in these experiments."
    )
    assert summary["method_recommendation_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False


def test_public_release_package_contains_compiled_report_and_supplement_pdfs():
    manifest = load_manifest()
    rows = {row["component_id"]: row for row in manifest["pdf_outputs"]}
    public_pdf_paths = {
        "main_article_pdf": PACKAGE_ROOT / "paper/article.pdf",
        "supplementary_document_pdf": PACKAGE_ROOT / "paper/supplement.pdf",
    }

    assert set(rows) == {"main_article_pdf", "supplementary_document_pdf"}
    for component_id, row in rows.items():
        pdf_path = public_pdf_paths[component_id]
        assert row["status"] == "pass"
        assert row["pdf_exists"] is True
        assert row["pdf_bytes"] > 10_000
        assert row["sha256"]
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 10_000
    for tex_path in [PACKAGE_ROOT / "paper/article.tex", PACKAGE_ROOT / "paper/supplement.tex"]:
        tex = tex_path.read_text(encoding="utf-8")
        assert "% public-pdf-table-layout-v1" in tex
        assert r">{\RaggedRight\arraybackslash}p{" in tex
        assert not re.search(r"\\begin\{longtable\}\{[lcr]{3,}\}", tex)


def test_public_release_reader_surfaces_are_english_only():
    checked_paths = [
        PUBLIC_RELEASE / "public_release_manifest.md",
        PUBLIC_RELEASE / "user_release_authorization.md",
        PUBLIC_RELEASE / "public_release_manifest.json",
        PUBLIC_RELEASE / "user_release_authorization.json",
        PACKAGE_ROOT / "README.md",
        PACKAGE_ROOT / "EVIDENCE_SCOPE.md",
        PACKAGE_ROOT / "site/index.html",
        PACKAGE_ROOT / "site/kg_browser.html",
        PACKAGE_ROOT / "site/kg_browser_data.json",
        PACKAGE_ROOT / "paper/research_document.md",
        PACKAGE_ROOT / "paper/article.html",
        PACKAGE_ROOT / "paper/supplement.html",
        PACKAGE_ROOT / "evidence/claim_evidence_matrix.md",
        PACKAGE_ROOT / "evidence/claim_evidence_matrix.json",
        PACKAGE_ROOT / "evidence/public_artifact_manifest.md",
        PACKAGE_ROOT / "evidence/public_artifact_manifest.json",
        PACKAGE_ROOT
        / "reproducibility/experiments/regression/scripts/"
        / "build_publication_authoring_decision_record.py",
    ]
    hits = []
    for path in checked_paths:
        text = path.read_text(encoding="utf-8")
        for pattern in NON_ENGLISH_PATTERNS:
            match = pattern.search(text)
            if match:
                hits.append({"path": path.as_posix(), "match": match.group(0)})

    assert hits == []


def test_public_release_site_uses_research_atlas_shell():
    index = (PACKAGE_ROOT / "site/index.html").read_text(encoding="utf-8")
    browser = (PACKAGE_ROOT / "site/kg_browser.html").read_text(encoding="utf-8")
    data = json.loads(
        (PACKAGE_ROOT / "site/kg_browser_data.json").read_text(encoding="utf-8")
    )

    assert "Regression CP Research Atlas" in index
    assert "Research Document and evidence map" in index
    assert "Paper PDF" in index
    assert "Supplement PDF" in index
    assert "Evidence Map" in index
    assert "CQR / CV+ Signal" in index
    assert "Release Boundary Ledger" not in index
    assert "Public Release Authorization" not in index
    assert "Regression CP Evidence Map" in browser
    assert "Research Routes" in browser
    assert "What is in this graph?" in browser
    assert "reader overview" in browser
    assert "state.selected=null; state.routeId=routeId" in browser
    assert "const start=params.get('node'); const preset=params.get('preset')" in browser
    assert "((data.research_map||[])[0]||{}).node_ids" not in browser
    assert "Knowledge graph canvas" in browser
    assert "Accessible Table" in browser
    assert "Provenance id" not in browser
    assert "source_key_hash" in (PACKAGE_ROOT / "site/kg_browser_data.json").read_text(
        encoding="utf-8"
    )
    assert data["schema"] == "regression_cp_evidence_graph_v2"
    assert data["summary"]["node_count"] == load_manifest()["summary"]["kg_node_count"]
    assert data["summary"]["edge_count"] == load_manifest()["summary"]["kg_edge_count"]
    assert len(data["research_map"]) == 6
    assert "cqr_backend_sensitivity" in {
        route["route_id"] for route in data["research_map"]
    }
    assert {route["title"] for route in data["research_map"]} == {
        "CQR / CV+ Practical Signal",
        "CQR Backend Sensitivity Check",
        "Venn-Abers Bridge Outcome",
        "Dataset Audits",
        "Evidence Scope",
        "Reproducibility Trail",
    }
    assert all(route["node_ids"] for route in data["research_map"])
    assert all("_" not in node["label"] for node in data["nodes"])


def test_public_package_has_install_test_flow_markers_and_ci():
    readme = (PACKAGE_ROOT / "README.md").read_text(encoding="utf-8")
    pyproject = (PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    pytest_ini = (PACKAGE_ROOT / "pytest.ini").read_text(encoding="utf-8")
    workflow = (PACKAGE_ROOT / ".github/workflows/public-ci.yml").read_text(
        encoding="utf-8"
    )
    smoke = (
        PACKAGE_ROOT
        / "reproducibility/tests/test_public_research_atlas_smoke.py"
    ).read_text(encoding="utf-8")

    install_command = 'python -m pip install -e ".[test]"'
    test_command = 'python -m pytest -m "unit or artifact_public or smoke"'
    help_command = "python -m experiments.regression.scripts.run_regression_pilot --help"

    assert install_command in readme
    assert test_command in readme
    assert help_command in readme
    assert 'name = "regression-conformal-prediction-research-atlas"' in pyproject
    assert 'package-dir = {"" = "reproducibility"}' in pyproject
    assert 'include = ["cpfi*", "experiments*"]' in pyproject
    assert "namespaces = true" in pyproject
    for marker in [
        "unit",
        "artifact_public",
        "smoke",
        "external_data",
        "private_artifact",
        "slow",
    ]:
        assert f"{marker}:" in pytest_ini
        assert f'"{marker}:' in pyproject
    assert install_command in workflow
    assert test_command in workflow
    assert help_command in workflow
    assert "-m \"slow" not in workflow
    assert "-m \"private_artifact" not in workflow
    assert "-m \"external_data" not in workflow
    assert "pytestmark = [pytest.mark.smoke, pytest.mark.artifact_public]" in smoke
    assert "test_public_root_command_help_runs" in smoke


def test_public_release_surfaces_do_not_expose_private_review_or_wrong_repo_name():
    checked_paths = [
        PACKAGE_ROOT / "README.md",
        PACKAGE_ROOT / "EVIDENCE_SCOPE.md",
        PACKAGE_ROOT / "pyproject.toml",
        PACKAGE_ROOT / "pytest.ini",
        PACKAGE_ROOT / ".github/workflows/public-ci.yml",
        PACKAGE_ROOT / "site/index.html",
        PACKAGE_ROOT / "site/kg_browser.html",
        PACKAGE_ROOT / "site/kg_browser_data.json",
        PACKAGE_ROOT / "paper/research_document.md",
        PACKAGE_ROOT / "paper/article.tex",
        PACKAGE_ROOT / "paper/article.html",
        PACKAGE_ROOT / "paper/supplement.tex",
        PACKAGE_ROOT / "paper/supplement.html",
        PACKAGE_ROOT / "evidence/claim_evidence_matrix.json",
        PACKAGE_ROOT / "evidence/claim_evidence_matrix.md",
        PACKAGE_ROOT / "evidence/kg_quality_summary.json",
        PACKAGE_ROOT / "evidence/public_artifact_manifest.json",
        PACKAGE_ROOT / "evidence/public_artifact_manifest.md",
    ]
    forbidden_patterns = [
        "Release Boundary Ledger",
        "Private final-prose review draft",
        "private final-prose review draft",
        "not final manuscript prose",
        "public submission",
        "Review boundary:",
        "not a release artifact",
        "does not authorize public release",
        "Public Release Authorization",
        "PUBLIC_RELEASE_MANIFEST",
        "PRIVATE_REVIEW_BOUNDARIES",
        "conformal-fairness-regression-publication",
        "CPFI Research Atlas",
        "manuscript_claim:",
        "methodology_control:",
        "paper_gate:",
        "report:publication_claim_evidence",
    ]

    hits = []
    for path in checked_paths:
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            if pattern in text:
                hits.append({"path": path.as_posix(), "pattern": pattern})

    assert not (PACKAGE_ROOT / "PUBLIC_RELEASE_AUTHORIZATION.md").exists()
    assert not (PACKAGE_ROOT / "PUBLIC_RELEASE_MANIFEST.md").exists()
    assert not (PACKAGE_ROOT / "PRIVATE_REVIEW_BOUNDARIES.md").exists()
    assert not (PACKAGE_ROOT / "PUBLIC_RELEASE_REVIEW_CHECKLIST.md").exists()
    assert not (PACKAGE_ROOT / "USER_REVIEW_HANDOFF.md").exists()
    assert not (PACKAGE_ROOT / "RELEASE_BOUNDARIES.md").exists()
    for removed_dir in [
        "audits",
        "citation",
        "governance",
        "knowledge_graph",
        "manuscript",
        "metadata",
        "provenance",
        "rendered_outputs",
        "release",
        "source_snapshots",
    ]:
        assert not (PACKAGE_ROOT / removed_dir).exists()
    assert hits == []


def test_public_artifact_manifest_covers_all_kg_source_and_evidence_paths():
    kg_data = json.loads(
        (PACKAGE_ROOT / "site/kg_browser_data.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (PACKAGE_ROOT / "evidence/public_artifact_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    manifest_keys = {row["artifact_key"] for row in manifest["artifacts"]}
    node_source_paths = [
        node["source_path"]
        for node in kg_data["nodes"]
        if isinstance(node, dict) and node.get("source_path")
    ]
    edge_evidence_paths = [
        edge["evidence_path"]
        for edge in kg_data["edges"]
        if isinstance(edge, dict) and edge.get("evidence_path")
    ]
    missing = [
        f"kg_node_source:{path}"
        for path in node_source_paths
        if f"kg_node_source:{path}" not in manifest_keys
    ]
    missing.extend(
        f"kg_edge_evidence:{path}"
        for path in edge_evidence_paths
        if f"kg_edge_evidence:{path}" not in manifest_keys
    )

    assert manifest["schema"] == "regression_cp_public_artifact_manifest_v1"
    assert manifest["strategy"] == "manifest_plus_summary_not_full_artifact_dump"
    assert manifest["summary"]["kg_source_and_evidence_path_coverage"] == 1.0
    assert manifest["summary"]["kg_referenced_artifact_count"] == len(manifest_keys)
    assert manifest["summary"]["summarized_artifact_count"] > 0
    assert missing == []
    assert all(node.get("source_resolution") for node in kg_data["nodes"] if node.get("source_path"))
    assert all(
        edge.get("evidence_resolution")
        for edge in kg_data["edges"]
        if edge.get("evidence_path")
    )
